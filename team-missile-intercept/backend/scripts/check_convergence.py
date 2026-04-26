"""Parse training log for ep_rew_mean trajectory; decide if converged.

Convergence rule (matches Chen's spec):
  1. Need at least 3 logged ep_rew_mean values to judge (i.e., past 600k
     transitions assuming 200k log frequency).
  2. Range of last 3 ep_rew_mean values must be < 5.0 (absolute units;
     ep_rew_mean lives in -100..+50 range typically).
  3. Latest must NOT be a new global max (trend is flat, not still climbing).

Exit codes:
  0  converged — caller advances to next stage
  1  not converged yet — caller continues training
  2  log unparsable / no data — caller continues training
"""
import re
import sys
from pathlib import Path

CONVERGENCE_RANGE = 5.0


def parse_ep_rew_means(log_path: Path) -> list:
    """Return list of ep_rew_mean values in chronological order."""
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
        print(f"log not found: {log}", file=sys.stderr)
        sys.exit(2)
    values = parse_ep_rew_means(log)
    if len(values) < 3:
        print(f"not enough ep_rew_mean entries yet ({len(values)})", file=sys.stderr)
        sys.exit(1)
    last3 = values[-3:]
    span = max(last3) - min(last3)
    is_new_max = last3[-1] >= max(values)
    converged = (span < CONVERGENCE_RANGE) and (not is_new_max)
    print(f"last3={last3} span={span:.2f} new_max={is_new_max} converged={converged}")
    sys.exit(0 if converged else 1)


if __name__ == "__main__":
    main()
