"""Same heuristic as Blue megamodel."""
import re, sys
from pathlib import Path

CONVERGENCE_RANGE = 5.0


def parse_ep_rew_means(log_path):
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


def main():
    if len(sys.argv) != 2:
        print("usage: check_convergence.py <training.log>", file=sys.stderr)
        sys.exit(2)
    log = Path(sys.argv[1])
    if not log.exists():
        sys.exit(2)
    values = parse_ep_rew_means(log)
    # Require at least 6 ep_rew_mean samples before allowing convergence
    # to fire. The earliest 3-4 readings are dominated by cold-start
    # noise (agent barely moves the policy off random init), so the
    # last3 heuristic can plateau-trigger on -X, -X, -X' before any
    # real learning has happened.
    MIN_SAMPLES = 6
    if len(values) < MIN_SAMPLES:
        sys.exit(1)
    last3 = values[-3:]
    span = max(last3) - min(last3)
    is_new_max = last3[-1] >= max(values)
    converged = (span < CONVERGENCE_RANGE) and (not is_new_max)
    print(f"n={len(values)} last3={last3} span={span:.2f} new_max={is_new_max} converged={converged}")
    sys.exit(0 if converged else 1)


if __name__ == "__main__":
    main()
