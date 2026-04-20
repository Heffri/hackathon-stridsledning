"""Test CIWS saturation — Issue #20 (M-TIER2.8).

Before fix: CIWS point-defense bypassed the expected_damage gate and
fired every tick while any threat was inside its 4 km envelope. Against
a 10-HP drone this could dump 20-30 rounds ($40-$60k of ammo) at a
$30k target.

After fix: CIWS still bypasses MAX_SIMULTANEOUS_PER_THREAT (rapid-fire
is the whole point of a cannon) but DOES respect the expected-damage
gate — stops firing once in-flight damage (summed across CIWS +
non-CIWS assigned interceptors) is >= threat.hp.

Test spawns a single drone at 500 m altitude, 3 km due north of the
default CIWS launcher at (75_000, 5_000). Only the CIWS can reach it
(drone altitude well within CIWS envelope; other launchers are too far
or point at a different threat type). No Red waves. Counts CIWS fire
events from blue.log and asserts a sane cap.

PASS criteria:
  * drone is killed
  * CIWS rounds fired <= 15 (pre-fix routinely hit 25+ in steady-state)
"""
from __future__ import annotations

import sys

from sim import config, sites
from sim.red_ai import RedAI
from sim.scenarios import Scenario
from sim.types import MatchPhase, ThreatType


def main() -> None:
    sites.reset_leaks()
    scn = Scenario()
    scn.red = RedAI([])  # no waves — single threat only
    scn.world.transition(MatchPhase.RUNNING)

    ciws_pos = config.BLUE_LAUNCHER_POSITIONS["ciws"][0]
    drone_spawn = (float(ciws_pos[0]), float(ciws_pos[1]) + 3_000.0, 500.0)
    drone_target = (float(ciws_pos[0]), float(ciws_pos[1]))
    tid = scn.world.spawn_threat(ThreatType.DRONE, drone_spawn, drone_target)

    dt = 0.05
    max_ticks = int(30.0 / dt)
    t_end = None
    for _ in range(max_ticks):
        scn.step(dt)
        thr = scn.world.threats.get(tid)
        if thr is None or not thr.state.alive:
            t_end = float(scn.world.t)
            break

    drone_killed = (
        tid not in scn.world.threats
        or not scn.world.threats[tid].state.alive
    )

    ciws_fires = sum(1 for line in scn.blue.log if "[CIWS]" in line)
    ciws_spend_usd = ciws_fires * 2_000  # from INTERCEPTOR_SPECS
    drone_cost_usd = 30_000

    print(
        f"drone_killed={drone_killed}  ciws_rounds_fired={ciws_fires}  "
        f"t_end={t_end}  "
        f"cost: ${ciws_spend_usd:,} on a ${drone_cost_usd:,} target"
    )

    pass_kill = drone_killed
    pass_cap = ciws_fires <= 15
    # Also soft-assert cost-effectiveness: ammo spend ≤ target value.
    pass_economy = ciws_spend_usd <= drone_cost_usd

    print(
        f"Verdict: "
        f"killed={'PASS' if pass_kill else 'FAIL'}  "
        f"round_cap={'PASS' if pass_cap else 'FAIL'} "
        f"({ciws_fires} <= 15)  "
        f"cost_effective={'PASS' if pass_economy else 'WARN'} "
        f"(${ciws_spend_usd:,} vs ${drone_cost_usd:,})"
    )

    # The two PASS criteria must hold; cost-effective is a nice-to-have.
    if not (pass_kill and pass_cap):
        sys.exit(1)


if __name__ == "__main__":
    main()
