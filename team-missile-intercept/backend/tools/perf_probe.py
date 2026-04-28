"""Backend hotspot profiling probe (W13 Phase 6).

Runs a headless default scenario under cProfile and dumps the top-N
functions by cumulative time. Use when the demo feels sluggish or
before landing a performance-sensitive refactor.

Usage (from backend/ or repo root — the sys.path tweak below finds
backend either way):

    cd team-missile-intercept/backend
    python tools/perf_probe.py                    # default: 600 s sim cap, top 20
    python tools/perf_probe.py --sim-s 1800       # longer profile window
    python tools/perf_probe.py --top 40           # deeper report
    python tools/perf_probe.py --out my.prof      # keep the raw prof file

The script prints a condensed report to stdout. Remove the .prof
output (or redirect --out) if you don't need it for snakeviz.
"""
from __future__ import annotations

import argparse
import cProfile
import pstats
import sys
from pathlib import Path

# Make `sim` importable whether invoked from backend/ or backend/tools/.
_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from sim.scenarios import build_default_scenario  # noqa: E402
from sim import config  # noqa: E402


def _run_match(sim_s: float) -> None:
    scn = build_default_scenario(auto_start=True)
    dt = config.DT
    total_ticks = int(sim_s / dt)
    for _ in range(total_ticks):
        scn.step(dt)
        if scn.winner is not None:
            break


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sim-s", type=float, default=600.0, help="Simulated seconds to run (default 600).")
    parser.add_argument("--top", type=int, default=20, help="Top-N rows in the cProfile report.")
    parser.add_argument("--out", default="", help="Optional path to dump the raw .prof file for snakeviz.")
    args = parser.parse_args()

    pr = cProfile.Profile()
    pr.enable()
    try:
        _run_match(args.sim_s)
    finally:
        pr.disable()

    stats = pstats.Stats(pr).strip_dirs().sort_stats("cumulative")
    print(f"\n=== Top {args.top} by cumulative time (sim_s={args.sim_s:.0f}) ===")
    stats.print_stats(args.top)
    print(f"\n=== Top {args.top} by internal time (self time, no callees) ===")
    stats.sort_stats("tottime").print_stats(args.top)

    if args.out:
        pr.dump_stats(args.out)
        print(f"\nWrote raw profile to {args.out}")


if __name__ == "__main__":
    main()
