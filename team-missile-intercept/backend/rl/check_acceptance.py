"""Acceptance-check wrapper around per_layout_eval.

Reads a per_layout_eval JSON output and reports pass/fail against the
three blue_aoe_mixed acceptance criteria:

1. Every (layout, Red) cell must have mean_intercepts > 5.
2. Every (layout × scripted-Red) cell must have ciws > 0 AND rbs_70 > 0
   in the per-kind fires total (not mean).
3. (Informational) current × scripted must keep or improve on the v2
   baseline — this one is reported but can't be automatically checked
   without a v2 reference JSON.

Exit code 0 if every blocker passed, 1 otherwise.

Usage:
  python -m rl.check_acceptance <eval_output.json>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


BLOCKER_REDS = {"scripted"}
KIND_CIWS = "ciws"
KIND_RBS70 = "rbs_70"
MIN_INTERCEPTS_THRESHOLD = 5.0


def _short_key(cell: dict) -> str:
    return f"{cell.get('layout')}×{cell.get('red')}"


def check(payload: dict) -> int:
    cells = payload.get("cells", {})
    if not cells:
        print("FAIL: no cells in eval payload")
        return 1
    failures = []
    for key, cell in cells.items():
        s = cell.get("summary", {})
        mi = s.get("mean_intercepts", 0.0)
        short = _short_key(cell)
        if mi <= MIN_INTERCEPTS_THRESHOLD:
            failures.append(
                f"  #1 {short}: mean_intercepts={mi:.2f} "
                f"(required >{MIN_INTERCEPTS_THRESHOLD})"
            )
        red = cell.get("red", "")
        if red in BLOCKER_REDS:
            pk = s.get("per_kind_fires_total", {})
            ciws = int(pk.get(KIND_CIWS, 0))
            rbs70 = int(pk.get(KIND_RBS70, 0))
            if ciws <= 0:
                failures.append(
                    f"  #2 {short}: ciws total fires = {ciws} (required > 0)"
                )
            if rbs70 <= 0:
                failures.append(
                    f"  #2 {short}: rbs_70 total fires = {rbs70} (required > 0)"
                )
    print("=== Acceptance check ===")
    for key, cell in cells.items():
        s = cell.get("summary", {})
        pk = s.get("per_kind_fires_total", {})
        short = _short_key(cell)
        print(
            f"  {short:<20s}  intercepts={s.get('mean_intercepts', 0.0):6.2f}  "
            f"blueWR={s.get('blue_winrate', 0.0)*100:5.1f}%  "
            f"leaks={s.get('mean_leaked', 0.0):4.1f}  "
            f"ciws={int(pk.get(KIND_CIWS, 0)):3d}  "
            f"rbs70={int(pk.get(KIND_RBS70, 0)):3d}  "
            f"slm={int(pk.get('iris_t_slm', 0)):3d}  "
            f"pac2={int(pk.get('pac_2', 0)):3d}  "
            f"pac3={int(pk.get('pac_3', 0)):3d}"
        )
    if failures:
        print(f"\nFAIL — {len(failures)} issue(s):")
        for f in failures:
            print(f)
        return 1
    print("\nPASS — all blocker criteria satisfied.")
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <eval_output.json>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    if not path.exists():
        print(f"no such file: {path}", file=sys.stderr)
        return 2
    payload = json.loads(path.read_text())
    return check(payload)


if __name__ == "__main__":
    sys.exit(main())
