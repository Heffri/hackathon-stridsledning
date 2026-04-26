"""Parse training log for ep_rew_mean trajectory; decide if converged.

Convergence rule (hardened 2026-04-26 after the SB3 logger
display-precision artifact fooled the original 3-entry / span-5 rule
during S1: SB3's logged value is the moving mean over ~100 episodes,
so consecutive iterations can show identical raw floats just because
the buffer hasn't refreshed — not because the policy converged):

  1. Need at least MIN_ENTRIES (=5) logged ep_rew_mean values.
  2. Range of last MIN_ENTRIES values must be < CONVERGENCE_RANGE (=20).
  3. Latest must NOT be a new global max (trend is flat, not climbing).
  4. There must be at least 1 distinct *raw* value in the last
     MIN_ENTRIES — guards against the buffer-stagnation case where N
     consecutive iterations report identical floats because no new
     episodes ended (which can happen when ep_len grows past
     n_steps × n_envs / n_episodes_per_buffer).

Reads the raw float from the TB event file when available (no display
rounding); falls back to the stdout regex.

Exit codes:
  0  converged
  1  not converged yet
  2  log unparsable / no data
"""
import glob
import re
import sys
from pathlib import Path

CONVERGENCE_RANGE = 20.0
MIN_ENTRIES = 5


def parse_ep_rew_means_from_log(log_path: Path) -> list:
    """Parse ep_rew_mean values from the SB3 stdout log (display-rounded)."""
    pattern = re.compile(r"ep_rew_mean\s*\|\s*([-\d.eE+]+)")
    values = []
    with log_path.open("r") as f:
        for line in f:
            m = pattern.search(line)
            if m:
                try:
                    values.append(float(m.group(1)))
                except ValueError:
                    pass
    return values


def parse_ep_rew_means_from_tb(log_path: Path) -> list:
    """Try to read raw ep_rew_mean from a colocated TB event file.

    Each train.py invocation creates a run-dir named after --run-name.
    The TB event file lives at ``rl/runs/<run_name>/tb/ppo_*/events*``.
    We don't know <run_name> from the log path directly, so we look up
    sibling rl/runs/* dirs and pick the latest matching the consolidated
    log's tail content.

    If multiple TB files match, returns the union of values from all.
    Returns [] if none found.
    """
    backend = Path(__file__).resolve().parent.parent     # .../backend
    runs = backend / "rl" / "runs"
    if not runs.exists():
        return []
    # Heuristic: find tb event files modified within the time window of the log.
    # Simpler approach — scan all blue_megamodel_* run dirs.
    candidates = sorted(glob.glob(str(runs / "blue_megamodel_*" / "tb" / "*" / "events*")))
    if not candidates:
        return []
    # Match against the log's stem to find the relevant run-dir
    log_stem = log_path.stem  # e.g. "S1_training" -> infer run_name "blue_megamodel_S1"
    stage = log_stem.split("_")[0]  # "S1"
    matching = [c for c in candidates if f"blue_megamodel_{stage}/" in c]
    if not matching:
        return []
    try:
        from tensorboard.backend.event_processing.event_accumulator \
            import EventAccumulator
    except ImportError:
        return []
    values = []
    for path in matching:
        try:
            ea = EventAccumulator(path)
            ea.Reload()
            if "rollout/ep_rew_mean" in ea.Tags()["scalars"]:
                for ev in ea.Scalars("rollout/ep_rew_mean"):
                    values.append(ev.value)
        except Exception:
            continue
    return values


def main():
    if len(sys.argv) != 2:
        print("usage: check_convergence.py <training.log>", file=sys.stderr)
        sys.exit(2)
    log = Path(sys.argv[1])
    if not log.exists():
        print(f"log not found: {log}", file=sys.stderr)
        sys.exit(2)

    values = parse_ep_rew_means_from_tb(log)
    source = "tb"
    if not values:
        values = parse_ep_rew_means_from_log(log)
        source = "log"

    if len(values) < MIN_ENTRIES:
        print(f"not enough ep_rew_mean entries yet ({len(values)} < {MIN_ENTRIES})",
              file=sys.stderr)
        sys.exit(1)

    last_n = values[-MIN_ENTRIES:]
    span = max(last_n) - min(last_n)
    is_new_max = last_n[-1] >= max(values)
    distinct = len(set(round(v, 4) for v in last_n))
    span_ok = span < CONVERGENCE_RANGE
    not_new_max = not is_new_max
    enough_distinct = distinct >= 2  # buffer is refreshing

    converged = span_ok and not_new_max and enough_distinct
    print(
        f"src={source} last_n={[round(v,2) for v in last_n]} "
        f"span={span:.2f} (range<{CONVERGENCE_RANGE}={span_ok}) "
        f"new_max={is_new_max} distinct={distinct}/{MIN_ENTRIES} "
        f"converged={converged}"
    )
    sys.exit(0 if converged else 1)


if __name__ == "__main__":
    main()
