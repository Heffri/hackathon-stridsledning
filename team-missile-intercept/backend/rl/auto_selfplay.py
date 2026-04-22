"""Autonomous multi-round self-play driver — long-running loop.

Runs alternating Blue / Red training rounds with opponent-pool sampling
until a wall-clock budget is exhausted. Each round:

  1. Train Blue_N vs an opponent pool of (rule RedAI + all Red
     checkpoints produced so far). Latest Red checkpoint carries the
     heaviest weight, historical Red split evenly at a smaller weight,
     rule carries a small exploration weight. Default mix 50/30/20 —
     see `_build_pool_weights` for the exact formula.
  2. Train Red_N vs the symmetric Blue opponent pool, warmstarted from
     Red_{N-1}. Round 3 warmstart falls back to the Red2 baseline
     checkpoint so the loop can be bootstrapped from a cold start.
  3. Every `--eval-every-n-rounds` rounds, run a checkpoint tournament
     over a small Red × Blue subset (latest + baselines) and write a
     JSON summary. Main loop continues while the eval is running in
     the same process — eval is a blocking subprocess call.

Robustness behaviour:

  * Training subprocess failures (non-zero exit) are re-raised —
    auto_selfplay exits non-zero so the outer shell (Tee-Object) sees
    the error. No silent retry. Incomplete round dirs remain on disk
    for post-mortem.
  * A disk-space guard bails before starting a round if free space
    drops below `--min-free-gb` (default 5). Each round is roughly
    ~80 MB of outputs.
  * Per-round CSV log (`--log-csv`) records timestamp, elapsed wall
    time, round number, Blue/Red model paths, and pool sizes. Append-
    only; auto-creates the file + header on first write.

Usage (36-hour overnight run):

    python -m rl.auto_selfplay ^
        --max-wall-clock-hours 36 ^
        --timesteps-per-train 500000 ^
        --start-round 3 ^
        2>&1 | Tee-Object -FilePath rl/auto_selfplay.log

Smoke test (~10 min total):

    python -m rl.auto_selfplay ^
        --max-wall-clock-hours 0.2 ^
        --timesteps-per-train 5000

Invoked from the `backend/` directory so the `python -m rl.*`
subprocess calls resolve. All paths are relative to cwd.
"""
from __future__ import annotations

import argparse
import csv
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple


# ---------------------------------------------------------------------------
# Baseline checkpoints — used to seed opponent pools and as the round-3 Red
# warmstart. These paths are the ones bundled on the `live-demo` branch /
# already present under rl/models + rl/runs at the time of writing.
# ---------------------------------------------------------------------------
BASELINE_RED_CHECKPOINTS = [
    "rl/runs/red_20260421_205051/model.zip",  # Red1 (vs rule Blue)
    "rl/runs/red_20260421_234425/model.zip",  # Red2 (warmstarted from Red1)
]
BASELINE_BLUE_CHECKPOINTS = [
    "rl/models/blue_ai_1m_1xpenalty/model.zip",  # Blue1
    "rl/models/blue_ai_1m_2xpenalty/model.zip",  # Blue2
]

# Default round-3 Red warmstart when there's no Red_{N-1} yet on disk.
DEFAULT_RED_ROUND3_WARMSTART = "rl/runs/red_20260421_234425/model.zip"


# ---------------------------------------------------------------------------
# Pool builders
# ---------------------------------------------------------------------------
def _collect_existing_red_models(round_n: int) -> List[str]:
    """Return all Red round checkpoints produced up to (but excluding)
    `round_n`. Order: ascending round number. Baseline Red1/Red2 are
    prepended as the earliest "history" entries.

    Missing files are skipped silently — training may have been
    interrupted mid-round, leaving an empty dir without a model.zip.
    """
    out: List[str] = [p for p in BASELINE_RED_CHECKPOINTS if Path(p).exists()]
    for n in range(3, round_n):
        p = Path(f"rl/runs/red_{n}/model.zip")
        if p.exists():
            out.append(str(p).replace("\\", "/"))
    return out


def _collect_existing_blue_models(round_n: int) -> List[str]:
    """Symmetric Blue-side pool scan. Baselines + per-round
    rl/runs/blue_local/blue_N/model.zip up to (exclusive of) round_n.
    """
    out: List[str] = [p for p in BASELINE_BLUE_CHECKPOINTS if Path(p).exists()]
    for n in range(3, round_n):
        p = Path(f"rl/runs/blue_local/blue_{n}/model.zip")
        if p.exists():
            out.append(str(p).replace("\\", "/"))
    return out


def _build_pool_weights(n_history: int, latest_weight: float,
                        rule_weight: float) -> Tuple[List[str], List[float]]:
    """Compose the pool string (rule + history + latest sentinel) and
    the matching weight list.

    Inputs:
      * n_history — number of historical opponent paths (excluding the
        latest, which takes the dedicated latest_weight).
      * latest_weight — weight for the single latest opponent.
      * rule_weight — weight for the rule sentinel.

    The history weight = 1 - latest_weight - rule_weight, split evenly
    across history entries. When n_history == 0 (first round with no
    history), the history weight is folded back into latest_weight so
    the 3-entry pool semantics (rule + history + latest) always hold
    numerically.

    Returns a tuple of (pool_entries, weights) — both as lists to be
    joined with commas by the caller when shelling out.
    """
    if n_history < 0:
        raise ValueError("n_history must be >= 0")
    history_weight = max(0.0, 1.0 - latest_weight - rule_weight)
    if n_history == 0:
        latest_weight = latest_weight + history_weight
        history_weight = 0.0
        per_history = 0.0
    else:
        per_history = history_weight / n_history
    weights: List[float] = [rule_weight]
    weights.extend([per_history] * n_history)
    weights.append(latest_weight)
    # Sanity — weights sum to 1 within float tolerance.
    total = sum(weights)
    if abs(total - 1.0) > 1e-6:
        raise RuntimeError(f"pool weights did not normalize ({total=})")
    return (["rule"] + ["__history__"] * n_history + ["__latest__"], weights)


def _build_blue_opponent_pool(round_n: int, latest_w: float,
                              rule_w: float) -> Tuple[str, str]:
    """Build the Red opponent pool for training Blue_N.

    Latest = the Red checkpoint from round (round_n - 1) if present,
    else the most-recent available baseline (Red2 in practice). This
    handles the round-3 bootstrap where no "previous round" Red exists
    so the baseline doubles as both history and latest.

    Returns (pool_csv, weights_csv) ready to pass to `--opponent-pool`
    and `--opponent-weights`.
    """
    all_red = _collect_existing_red_models(round_n)
    if not all_red:
        raise RuntimeError(
            "No Red checkpoints available — baselines missing and no "
            "round checkpoints on disk. Cannot start auto_selfplay."
        )
    # The "latest" is just the last entry; everything prior is history.
    latest = all_red[-1]
    history = all_red[:-1]
    _, weights = _build_pool_weights(len(history), latest_w, rule_w)
    entries = ["rule"] + history + [latest]
    pool_csv = ",".join(entries)
    weights_csv = ",".join(f"{w:.6f}" for w in weights)
    return pool_csv, weights_csv


def _build_red_opponent_pool(round_n: int, latest_w: float,
                             rule_w: float) -> Tuple[str, str]:
    """Symmetric Blue-opponent-pool builder for training Red_N."""
    all_blue = _collect_existing_blue_models(round_n)
    if not all_blue:
        raise RuntimeError(
            "No Blue checkpoints available — baselines missing and no "
            "round checkpoints on disk. Cannot start auto_selfplay."
        )
    latest = all_blue[-1]
    history = all_blue[:-1]
    _, weights = _build_pool_weights(len(history), latest_w, rule_w)
    entries = ["rule"] + history + [latest]
    pool_csv = ",".join(entries)
    weights_csv = ",".join(f"{w:.6f}" for w in weights)
    return pool_csv, weights_csv


# ---------------------------------------------------------------------------
# CSV logging
# ---------------------------------------------------------------------------
CSV_HEADER = [
    "timestamp_iso", "round", "wall_elapsed_s", "phase",
    "blue_model", "red_model", "blue_pool_size", "red_pool_size", "status",
]


def _append_csv_row(log_path: Path, row: dict) -> None:
    new_file = not log_path.exists()
    with log_path.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_HEADER)
        if new_file:
            w.writeheader()
        # Keep only known keys so a caller passing extras doesn't break.
        w.writerow({k: row.get(k, "") for k in CSV_HEADER})


# ---------------------------------------------------------------------------
# Disk guard
# ---------------------------------------------------------------------------
def _check_disk_free_gb(min_free_gb: float) -> None:
    free_bytes = shutil.disk_usage(".").free
    free_gb = free_bytes / (1024 ** 3)
    if free_gb < min_free_gb:
        raise RuntimeError(
            f"Disk free space {free_gb:.1f} GB below minimum "
            f"{min_free_gb:.1f} GB — aborting before starting a new round."
        )


# ---------------------------------------------------------------------------
# Subprocess wrappers
# ---------------------------------------------------------------------------
def _run(cmd: List[str]) -> None:
    """Stream subprocess output to parent stdout/stderr. `check=True`
    raises subprocess.CalledProcessError on non-zero exit — propagates
    out of the loop so the operator sees failure immediately."""
    print(f"\n[auto_selfplay] $ {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, check=True)


def _train_blue(round_n: int, pool_csv: str, weights_csv: str,
                timesteps: int, extra_args: List[str],
                layouts_pool: Optional[str] = None) -> Path:
    out_dir = Path(f"rl/runs/blue_local/blue_{round_n}")
    cmd = [
        sys.executable, "-m", "rl.blue_train",
        "--opponent-pool", pool_csv,
        "--opponent-weights", weights_csv,
        "--timesteps", str(timesteps),
        "--output-dir", str(out_dir),
    ]
    if layouts_pool is not None:
        cmd.extend(["--layouts-pool", layouts_pool])
    cmd.extend(extra_args)
    _run(cmd)
    return out_dir / "model.zip"


def _train_red(round_n: int, pool_csv: str, weights_csv: str,
               timesteps: int, warmstart: str,
               extra_args: List[str],
               layouts_pool: Optional[str] = None) -> Path:
    out_dir = Path(f"rl/runs/red_{round_n}")
    cmd = [
        sys.executable, "-m", "rl.red_train",
        "--opponent-pool", pool_csv,
        "--opponent-weights", weights_csv,
        "--total-steps", str(timesteps),
        "--warmstart", warmstart,
        "--run-name", f"red_{round_n}",
    ]
    if layouts_pool is not None:
        cmd.extend(["--layouts-pool", layouts_pool])
    cmd.extend(extra_args)
    _run(cmd)
    return out_dir / "model.zip"


def _run_checkpoint_eval(round_n: int, n_seeds: int) -> None:
    """Run a small Red × Blue tournament — latest + Red2/Blue2 baselines,
    `n_seeds` episodes per pair. Writes rl/checkpoint_eval_round_<N>.json
    alongside an .md summary for human reading. Non-fatal: a failed eval
    logs and continues rather than crashing the training loop (checkpoint
    tournaments are diagnostic, not critical-path).

    The 3x3 spec list (rule + latest + one baseline per side) × n_seeds
    keeps total episode count ~O(n_seeds * 9). At 600s sim / ~20s wall
    per episode, n_seeds=5 -> ~15 min eval; n_seeds=15 -> ~45 min. Tune
    via `--eval-seeds` in the main CLI.
    """
    out_json = f"rl/checkpoint_eval_round_{round_n}.json"
    out_md = f"rl/checkpoint_eval_round_{round_n}.md"
    # Smaller spec matrix than BASELINE_*_CHECKPOINTS — use only the
    # most recent pre-training baseline (Red2 / Blue2) so the diagnostic
    # stays fast. Chen can run the full cross_eval_tournament manually
    # at a milestone if needed.
    latest_red = Path(f"rl/runs/red_{round_n}/model.zip")
    latest_blue = Path(f"rl/runs/blue_local/blue_{round_n}/model.zip")
    red_specs = ["rule"]
    if latest_red.exists():
        red_specs.append(str(latest_red).replace("\\", "/"))
    if BASELINE_RED_CHECKPOINTS:
        red_specs.append(BASELINE_RED_CHECKPOINTS[-1])  # most recent baseline
    blue_specs = ["rule"]
    if latest_blue.exists():
        blue_specs.append(str(latest_blue).replace("\\", "/"))
    if BASELINE_BLUE_CHECKPOINTS:
        blue_specs.append(BASELINE_BLUE_CHECKPOINTS[-1])
    seed_range = f"1000-{1000 + n_seeds - 1}"
    cmd = [
        sys.executable, "-m", "rl.cross_eval_tournament",
        "--seeds", seed_range,
        "--red-policies", ",".join(red_specs),
        "--blue-policies", ",".join(blue_specs),
        "--out-json", out_json,
        "--out-md", out_md,
        "--quiet",
    ]
    print(
        f"[auto_selfplay] checkpoint eval round {round_n} "
        f"({len(red_specs)}x{len(blue_specs)} @ {n_seeds} seeds)",
        flush=True,
    )
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(
            f"[auto_selfplay] WARNING: checkpoint eval failed "
            f"(exit {e.returncode}) — continuing training loop.",
            flush=True,
        )


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(
        description="Autonomous multi-round self-play driver."
    )
    ap.add_argument("--max-wall-clock-hours", type=float, default=36.0)
    ap.add_argument("--timesteps-per-train", type=int, default=500_000)
    ap.add_argument("--start-round", type=int, default=3)
    ap.add_argument("--eval-every-n-rounds", type=int, default=2)
    ap.add_argument("--eval-seeds", type=int, default=5,
                    help="Episodes per pair for checkpoint eval. "
                         "3x3 matrix * n_seeds = total episode count.")
    ap.add_argument("--log-csv", type=str,
                    default="rl/auto_selfplay_history.csv")
    ap.add_argument("--latest-weight", type=float, default=0.5,
                    help="Sampling weight for the latest opponent.")
    ap.add_argument("--rule-weight", type=float, default=0.2,
                    help="Sampling weight for rule-based opponent.")
    ap.add_argument("--min-free-gb", type=float, default=5.0,
                    help="Abort before a new round if free disk < this.")
    ap.add_argument("--red-warmstart", type=str,
                    default=DEFAULT_RED_ROUND3_WARMSTART,
                    help="Red warmstart for `--start-round` when no "
                         "preceding Red round exists on disk.")
    ap.add_argument("--layouts-pool", type=str, default=None,
                    help="Path to top3_layouts.json. Forwarded verbatim "
                         "to blue_train / red_train so every episode in "
                         "every round samples a Blue layout from the pool.")
    ap.add_argument("--extra-blue-args", type=str, default="",
                    help="Extra args forwarded verbatim to blue_train "
                         "(shell-split on whitespace).")
    ap.add_argument("--extra-red-args", type=str, default="",
                    help="Extra args forwarded verbatim to red_train.")
    args = ap.parse_args()

    log_csv = Path(args.log_csv)
    log_csv.parent.mkdir(parents=True, exist_ok=True)

    extra_blue = args.extra_blue_args.split() if args.extra_blue_args else []
    extra_red = args.extra_red_args.split() if args.extra_red_args else []

    t_start = time.time()
    round_n = args.start_round
    last_successful_round: Optional[int] = None

    print(
        f"=== auto_selfplay start ===\n"
        f"  budget       : {args.max_wall_clock_hours:.2f} h\n"
        f"  steps/train  : {args.timesteps_per_train:,}\n"
        f"  start-round  : {round_n}\n"
        f"  weights      : latest={args.latest_weight:.2f} "
        f"rule={args.rule_weight:.2f} "
        f"(history = {max(0.0, 1 - args.latest_weight - args.rule_weight):.2f})\n"
        f"  eval every   : {args.eval_every_n_rounds} rounds\n"
        f"  csv log      : {log_csv}\n",
        flush=True,
    )

    try:
        while True:
            elapsed_h = (time.time() - t_start) / 3600.0
            remaining_h = args.max_wall_clock_hours - elapsed_h
            if remaining_h <= 0:
                print(
                    f"[auto_selfplay] wall-clock budget exhausted "
                    f"(elapsed {elapsed_h:.2f} h). Stopping.",
                    flush=True,
                )
                break
            _check_disk_free_gb(args.min_free_gb)

            # --- Blue round first (opponent pool = Red history + baselines).
            blue_pool_csv, blue_weights_csv = _build_blue_opponent_pool(
                round_n, args.latest_weight, args.rule_weight,
            )
            blue_pool_size = len(blue_pool_csv.split(","))
            print(
                f"\n[auto_selfplay] ROUND {round_n} BLUE "
                f"(elapsed {elapsed_h:.2f} h, pool={blue_pool_size}) "
                f"pool={blue_pool_csv}",
                flush=True,
            )
            blue_path = _train_blue(
                round_n, blue_pool_csv, blue_weights_csv,
                args.timesteps_per_train, extra_blue,
                layouts_pool=args.layouts_pool,
            )

            # --- Red round (opponent pool = Blue history + baselines,
            # including the just-produced Blue_N from this round).
            red_pool_csv, red_weights_csv = _build_red_opponent_pool(
                round_n + 1, args.latest_weight, args.rule_weight,
            )
            red_pool_size = len(red_pool_csv.split(","))
            # Red warmstart: Red_{N-1} if available, else the configured
            # --red-warmstart baseline (Red2 by default). This keeps
            # single-opponent Red_3 out of the warmstart chain if the
            # loop is re-starting round 3 as a pool-based round.
            red_prev = Path(f"rl/runs/red_{round_n - 1}/model.zip")
            if red_prev.exists() and round_n > args.start_round:
                warmstart = str(red_prev).replace("\\", "/")
            else:
                warmstart = args.red_warmstart
            print(
                f"\n[auto_selfplay] ROUND {round_n} RED "
                f"(pool={red_pool_size}, warmstart={warmstart}) "
                f"pool={red_pool_csv}",
                flush=True,
            )
            red_path = _train_red(
                round_n, red_pool_csv, red_weights_csv,
                args.timesteps_per_train, warmstart, extra_red,
                layouts_pool=args.layouts_pool,
            )

            # --- CSV log + optional checkpoint eval.
            _append_csv_row(log_csv, {
                "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "round": round_n,
                "wall_elapsed_s": f"{time.time() - t_start:.1f}",
                "phase": "complete",
                "blue_model": str(blue_path).replace("\\", "/"),
                "red_model": str(red_path).replace("\\", "/"),
                "blue_pool_size": blue_pool_size,
                "red_pool_size": red_pool_size,
                "status": "ok",
            })
            last_successful_round = round_n
            if (round_n % args.eval_every_n_rounds) == 0:
                _run_checkpoint_eval(round_n, n_seeds=args.eval_seeds)
            round_n += 1
    except KeyboardInterrupt:
        print(
            f"\n[auto_selfplay] interrupted by user at round {round_n} "
            f"(last successful = {last_successful_round})",
            flush=True,
        )
        return 130
    except subprocess.CalledProcessError as e:
        print(
            f"\n[auto_selfplay] training subprocess failed at round "
            f"{round_n} (exit {e.returncode}). Aborting.",
            flush=True,
        )
        _append_csv_row(log_csv, {
            "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "round": round_n,
            "wall_elapsed_s": f"{time.time() - t_start:.1f}",
            "phase": "failed",
            "status": f"subprocess_exit_{e.returncode}",
        })
        return 1
    except RuntimeError as e:
        print(f"\n[auto_selfplay] aborting: {e}", flush=True)
        return 1

    print(
        f"\n[auto_selfplay] done. last successful round = "
        f"{last_successful_round} (finished at round {round_n - 1}).",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
