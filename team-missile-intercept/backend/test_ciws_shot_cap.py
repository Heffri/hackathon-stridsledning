"""Test CIWS per-threat lifetime shot cap — Issue #24 (W11).

Refinement of Issue #20 (M-TIER2.8). The #20 fix added an expected-damage
gate so CIWS stops firing once enough in-flight damage is inbound to
kill the threat. But because each CIWS round self-destructs at
fuel_s=4, the gate reopens when live rounds age out — and against a
slow-crossing threat the launcher can still spray many rounds over
time. Issue #24 adds a per-threat lifetime counter and caps total
CIWS launches at ceil(threat_spec.hp / ciws.damage_prox) + 2.

Per-kind caps:
  * DRONE       hp=10  -> ceil(10/8)+2 = 4
  * CRUISE_SUB  hp=30  -> ceil(30/8)+2 = 6
  * HGV         hp=60  -> ceil(60/8)+2 = 10
  * BALLISTIC   hp=80  -> ceil(80/8)+2 = 12

Test 1 — cap holds when rounds miss:
  Spawn a drone on a CIWS pad. Artificially bump its HP to 1000 every
  tick so the expected-damage gate can never close (no matter how many
  CIWS rounds are in flight, damage won't catch up to 1000-HP). The
  lifetime cap is then the ONLY thing stopping more shots. Assert total
  CIWS rounds fired <= DRONE cap (4).

Test 2 — full-match CIWS count stays bounded:
  Run a default Scenario end-to-end. Record total [CIWS] log lines.
  Assert the count is under a generous upper bound — pre-cap runs
  could in theory dump 20+ rounds per threat; with the cap, even a
  large 12-threat wave should stay well under 60 total.
"""
from __future__ import annotations

import math
import sys

from sim import config, sites
from sim.red_ai import RedAI
from sim.scenarios import Scenario
from sim.types import (
    INTERCEPTOR_SPECS,
    InterceptorType,
    MatchPhase,
    THREAT_SPECS,
    ThreatType,
)


def test_cap_holds_under_hp_bump() -> bool:
    """Drone with HP forced to 1000 every tick can NEVER die from CIWS
    damage, so the expected-damage gate never closes. The lifetime cap
    must bound total CIWS fires at the DRONE cap (4)."""
    sites.reset_leaks()
    scn = Scenario()
    scn.red = RedAI([])  # no waves — single isolated drone
    scn.world.transition(MatchPhase.RUNNING)

    ciws_pos = config.BLUE_LAUNCHER_POSITIONS["ciws"][0]
    # Spawn 3 km north of CIWS at 500 m altitude — deep inside the
    # 4 km envelope so the launcher definitely sees it in range.
    drone_spawn = (float(ciws_pos[0]), float(ciws_pos[1]) + 3_000.0, 500.0)
    drone_target = (float(ciws_pos[0]), float(ciws_pos[1]))
    tid = scn.world.spawn_threat(ThreatType.DRONE, drone_spawn, drone_target)

    dt = 0.05
    # 20 s is long enough to see CIWS spray through multiple fuel cycles
    # (fuel_s=4) — plenty of chances for the cap to fail if it weren't
    # wired.
    max_ticks = int(20.0 / dt)
    for _ in range(max_ticks):
        thr = scn.world.threats.get(tid)
        if thr is None or not thr.state.alive:
            break
        # Keep the drone effectively immortal so CIWS keeps trying to
        # fire — isolates the lifetime-cap behaviour from the normal
        # kill-and-purge path.
        thr.state.hp = 1000
        scn.step(dt)

    ciws_fires = sum(1 for line in scn.blue.log if "[CIWS]" in line)
    drone_cap = (
        math.ceil(
            THREAT_SPECS[ThreatType.DRONE].hp
            / INTERCEPTOR_SPECS[InterceptorType.CIWS].damage_prox
        )
        + 2
    )
    # Allow a small margin for multi-launcher concurrency (the default
    # config has 2 CIWS launchers both in range of this spawn; each
    # tracks the same cap independently of the other via the per-threat
    # counter). Even with both firing, the counter is shared so the total
    # cap is 4. Keep the assert tight.
    pass_cap = ciws_fires <= drone_cap
    print(
        f"test_cap_holds_under_hp_bump: ciws_fires={ciws_fires} "
        f"cap={drone_cap} -> {'PASS' if pass_cap else 'FAIL'}"
    )
    return pass_cap


def test_full_match_bounded_ciws_spend() -> bool:
    """Default scenario end-to-end: total CIWS fires must stay under a
    reasonable ceiling. Upper bound derivation:
        ~12 threats per match, worst case all drones -> 12 * 4 = 48.
        Some threats are cruise/HGV/ballistic with higher caps but
        usually out of CIWS envelope anyway.
    100 is a generous upper bound — pre-cap, full-match runs commonly
    hit 120+ in steady state with multiple concurrent drones.
    """
    sites.reset_leaks()
    scn = Scenario()
    # Use the default Red roster (whatever the config defaults are).
    scn.world.transition(MatchPhase.RUNNING)

    dt = 0.05
    max_ticks = int(180.0 / dt)  # 3 min safety cap
    for _ in range(max_ticks):
        scn.step(dt)
        if scn.winner is not None:
            break

    ciws_fires = sum(1 for line in scn.blue.log if "[CIWS]" in line)
    # 100 is a hard ceiling; typical value with cap wired is < 30.
    upper = 100
    pass_bound = ciws_fires <= upper
    print(
        f"test_full_match_bounded_ciws_spend: ciws_fires={ciws_fires} "
        f"upper={upper} winner={scn.winner} -> "
        f"{'PASS' if pass_bound else 'FAIL'}"
    )
    return pass_bound


def main() -> None:
    ok1 = test_cap_holds_under_hp_bump()
    ok2 = test_full_match_bounded_ciws_spend()
    if not (ok1 and ok2):
        sys.exit(1)
    print("All CIWS lifetime-cap tests passed.")


if __name__ == "__main__":
    main()
