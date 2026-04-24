"""Bug 6 regression — ScriptedRedAI mop-up drone phase.

After the initial 3-chain × 3-round schedule exhausts, Red may still
have leftover budget (HGV / ballistic / cruise gated by expensive cost
checks). Before the fix, Red idled and the match ran to MAX_SIM_TIME
= 3600 s → draw. The mop-up phase spawns 1 drone every 30 s toward a
random alive military site until budget drops below drone cost.

Two cases:
  1. Drain budget low-but-above-drone-cost → mop-up fires repeatedly.
  2. Drain budget below drone cost → mop-up ends without spawning,
     and `done` eventually latches once in-flight threats resolve.

Framing: arcade-game hackathon demo, not a military product. Drones
/ sites / budget values are public encyclopedia-level balance numbers.
"""
from __future__ import annotations

import sys

from sim import config
from sim.red_ai import ScriptedRedAI, MOPUP_INTERVAL_S
from sim.scenarios import build_default_scenario
from sim.types import THREAT_SPECS, ThreatType


DT = config.DT
DRONE_COST = THREAT_SPECS[ThreatType.DRONE].usd_cost


def _advance(scn, sim_seconds: float) -> None:
    steps = int(sim_seconds / DT)
    for _ in range(steps):
        scn.step(DT)


def _drain_red_budget_to(scn, target_usd: int) -> None:
    """Directly set world.red_budget. Used to fast-forward the
    expensive branches without needing to actually fire the whole
    schedule — the mop-up hook only cares about the budget + the
    triggers queue, not the spending history."""
    scn.world.red_budget = int(target_usd)


def _count_mopup_log_lines(scn) -> int:
    return sum(1 for line in scn.red.log if "mop-up drone" in line and "rejected" not in line)


def _force_schedule_drained(scn) -> None:
    """Flush the ScriptedRed trigger queue so the schedule looks
    exhausted. The mop-up activation gate is `_initialized and not
    _triggers`; draining the queue + marking initialised simulates
    the natural end-of-schedule state without running 1500 sim s."""
    scn.red._triggers = []
    # Mark initialised so the gate evaluates correctly. The real
    # init also fires d1 spawns — not needed for this unit test.
    scn.red._initialized = True


def test_mopup_fires_when_schedule_drained_and_budget_low() -> None:
    """Case 1: Red has $500k (below HGV/ballistic/cruise, above drone).
    Force schedule drain + advance 120 s → expect ≥ 3 mop-up drones
    (one every MOPUP_INTERVAL_S = 30 s)."""
    scn = build_default_scenario(auto_start=True)
    scn.red = ScriptedRedAI(scn)
    _force_schedule_drained(scn)
    _drain_red_budget_to(scn, 500_000)

    _advance(scn, 120.0)

    n_spawns = _count_mopup_log_lines(scn)
    assert n_spawns >= 3, (
        f"expected ≥3 mop-up spawns at 30 s cadence over 120 s, got {n_spawns}"
    )
    assert scn.red._mopup_active, "mop-up should still be active while budget holds"
    print(
        f"ok  test_mopup_fires_when_schedule_drained_and_budget_low "
        f"(n_spawns={n_spawns}, budget=${scn.world.red_budget:,})"
    )


def test_mopup_ends_when_budget_below_drone_cost() -> None:
    """Case 2: Red has $20k (below drone cost $30k). Force schedule
    drain + advance 120 s → expect 0 mop-up spawns, mop-up deactivated,
    and `done` latches once in-flight threats resolve."""
    scn = build_default_scenario(auto_start=True)
    scn.red = ScriptedRedAI(scn)
    _force_schedule_drained(scn)
    # Kill any in-flight threats (since _force_schedule_drained didn't
    # spawn any, but defensive) to let `done` latch cleanly.
    for thr in scn.world.threats.values():
        thr.state.alive = False
    _drain_red_budget_to(scn, 20_000)
    assert scn.world.red_budget < DRONE_COST

    _advance(scn, 120.0)

    n_spawns = _count_mopup_log_lines(scn)
    assert n_spawns == 0, (
        f"expected 0 mop-up spawns with budget < drone cost, got {n_spawns}"
    )
    assert not scn.red._mopup_active, "mop-up should have deactivated"
    assert scn.red.done, (
        f"ScriptedRed should be done: triggers={scn.red._triggers}, "
        f"mopup_active={scn.red._mopup_active}, "
        f"alive_threats={sum(1 for t in scn.world.threats.values() if t.state.alive)}"
    )
    print("ok  test_mopup_ends_when_budget_below_drone_cost")


def main() -> int:
    print("=== ScriptedRed mop-up regression (Bug 6) ===")
    test_mopup_fires_when_schedule_drained_and_budget_low()
    test_mopup_ends_when_budget_below_drone_cost()
    print("\nAll 2 mop-up tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
