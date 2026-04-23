"""Headless balance sweep: run the current scenario N times and print the
Blue/Red/Draw tally. Used to tune wave timing, ammo loadouts, and AOE
mechanic calibration so Blue doesn't cruise at 100% win rate.

Milestone I hybrid classifier — combines `scenario.winner` (the real
game-loop outcome) with a leak-count nuance so the three-bucket spec
target "30-55 / 30-50 / 10-30 Blue / Draw / Red" remains measurable:

  * Red   if `scenario.winner == 'red'`  (site HP or budget hit 0).
  * Blue  if `scenario.winner == 'blue'` AND `leaks <= 5`.
  * Draw  if `scenario.winner == 'blue'` AND `leaks >= 6`.
  * (Cap fallback: if the per-match sim cap fires without a winner,
    classify by leak count — <=1 → blue, 2 → draw, >=3 → red.)

CLI:
    python test_balance.py                 # 20 matches, default waves
    python test_balance.py --matches 20 --layout current --red scripted
    python test_balance.py --matches 10 --layout C --red scripted \
        --layouts-pool-json rl/top3_layouts_CD.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sim.scenarios import build_default_scenario


def _classify_by_leaks(leaked: int) -> str:
    if leaked <= 1:
        return "blue"
    if leaked >= 3:
        return "red"
    return "draw"


def _classify(winner, leaked: int) -> str:
    if winner == "red":
        return "red"
    if winner == "blue":
        return "blue" if leaked <= 5 else "draw"
    return _classify_by_leaks(leaked)


def _load_layout_override(
    layout_slot: str,
    layouts_json_path: str,
):
    """Return a roster dict for the named slot, or None for 'current'."""
    if layout_slot.lower() == "current":
        return None
    data = json.loads(Path(layouts_json_path).read_text())
    for entry in data.get("layouts", []):
        if str(entry.get("slot", "")).upper() == layout_slot.upper():
            roster = entry.get("roster", {})
            return {
                kind: [tuple(pos) for pos in positions]
                for kind, positions in roster.items()
            }
    raise SystemExit(
        f"[test_balance] slot '{layout_slot}' not found in "
        f"{layouts_json_path}; available: "
        f"{[L.get('slot') for L in data.get('layouts', [])]}"
    )


def _build_scenario(
    layout_slot: str,
    red_mode: str,
    layouts_json_path: str,
    red_budget: int | None,
    blue_budget: int | None,
):
    override = _load_layout_override(layout_slot, layouts_json_path)
    scn = build_default_scenario(layout_override=override, auto_start=False)
    if red_mode == "scripted":
        from sim.red_ai import ScriptedRedAI
        scn.red = ScriptedRedAI(scn)
    if red_budget is not None:
        scn.world.red_budget = int(red_budget)
        scn.world.red_budget_max = int(red_budget)
    if blue_budget is not None:
        scn.world.blue_budget = int(blue_budget)
        scn.world.blue_budget_max = int(blue_budget)
    from sim.types import MatchPhase
    scn.world.transition(MatchPhase.RUNNING)
    return scn


def run_once_verbose(
    sim_cap: float,
    layout_slot: str,
    red_mode: str,
    layouts_json_path: str,
    red_budget: int | None,
    blue_budget: int | None,
    trace_leaks=None,
) -> tuple[str, int, int, int]:
    scn = _build_scenario(
        layout_slot, red_mode, layouts_json_path, red_budget, blue_budget,
    )
    dt = 0.05
    max_ticks = int(sim_cap / dt) + 10
    for _ in range(max_ticks):
        scn.step(dt)
        if trace_leaks is not None:
            for ev in scn.world.events:
                if ev.get("type") == "leak":
                    trace_leaks.append(
                        (round(scn.world.t, 1), ev.get("kind", "?"))
                    )
        if scn.done:
            break

    snap = scn.snapshot()
    leaked = snap["stats"]["leaked"]
    spawned = snap["stats"]["spawned"]
    intercepts = snap["stats"]["intercepts"]
    return _classify(scn.winner, leaked), spawned, intercepts, leaked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--matches", type=int, default=20)
    ap.add_argument("--layout", default="current",
                    help="Blue layout slot: 'current' or a letter (C/D/E/...)")
    ap.add_argument("--red", default="default",
                    choices=["default", "scripted"],
                    help="Red AI variant: default (wave-based) or scripted")
    ap.add_argument("--layouts-pool-json",
                    default="rl/top3_layouts_CD.json",
                    help="path to layouts JSON (used only when --layout != current)")
    ap.add_argument("--sim-cap", type=float, default=3000.0,
                    help="per-match sim-time cap (s)")
    ap.add_argument("--red-budget", type=int, default=None)
    ap.add_argument("--blue-budget", type=int, default=None)
    args = ap.parse_args()

    n = args.matches
    tally = {"blue": 0, "red": 0, "draw": 0}
    spawned_list = []
    intercept_list = []
    leak_list = []
    leak_kinds = {}
    for i in range(n):
        leaks_trace = []
        res, spawned, intercepts, leaked = run_once_verbose(
            sim_cap=args.sim_cap,
            layout_slot=args.layout,
            red_mode=args.red,
            layouts_json_path=args.layouts_pool_json,
            red_budget=args.red_budget,
            blue_budget=args.blue_budget,
            trace_leaks=leaks_trace,
        )
        tally[res] += 1
        spawned_list.append(spawned)
        intercept_list.append(intercepts)
        leak_list.append(leaked)
        for _, k in leaks_trace:
            leak_kinds[k] = leak_kinds.get(k, 0) + 1
        print(
            f"[{i+1:3d}/{n}] {res:5s} spawn={spawned} int={intercepts} leaks={leaked}",
            flush=True,
        )
    print(
        f"Blue win {tally['blue']}/{n}, "
        f"draw {tally['draw']}/{n}, "
        f"Red win {tally['red']}/{n}"
    )
    print(
        f"  avg spawned={sum(spawned_list)/n:.1f}  "
        f"avg intercepts={sum(intercept_list)/n:.1f}  "
        f"avg leaks={sum(leak_list)/n:.1f}  "
        f"leak range={min(leak_list)}..{max(leak_list)}"
    )
    if leak_kinds:
        print(f"  leaks by kind: {leak_kinds}")


if __name__ == "__main__":
    main()
