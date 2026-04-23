"""Unit test: fragmentation AOE applies flat damage within radius.

Verifies the §3.3 model:
  * tight drone cluster + IRIS-T SLS (r=100, dmg=35): all drones dead
  * tight drone cluster + CIWS (r=30, dmg=12): only drones in radius die

Calls `resolve_aoe` directly — no flight sim. Each drone has hp=10.
"""
from __future__ import annotations

import numpy as np

from sim.types import INTERCEPTOR_SPECS, InterceptorType, THREAT_SPECS, ThreatType
from sim.world import World, resolve_aoe


def _place_drone(world: World, xy: tuple[float, float]) -> int:
    """Spawn a drone at (x, y, alt) via world.spawn_threat. Uses the
    cruise-alt default from the spec."""
    return world.spawn_threat(
        ThreatType.DRONE,
        start_xy=(xy[0], xy[1]),
        target_xy=(0.0, 0.0),
        validate_location=False,
    )


def test_iris_t_sls_clears_3_drone_cluster() -> None:
    world = World()
    # 3 drones within 50m of each other, centred at (10000, 10000)
    t1 = _place_drone(world, (10000.0, 10000.0))
    t2 = _place_drone(world, (10030.0, 10000.0))
    t3 = _place_drone(world, (10000.0, 10040.0))
    # IRIS-T SLS detonates at t1's position → r=100, dmg=35
    spec = INTERCEPTOR_SPECS[InterceptorType.IRIS_T_SLS]
    detonation_pos = world.threats[t1].state.pos.copy()
    aoe = resolve_aoe(spec, detonation_pos, world.threats)
    # All 3 drones within 50m of detonation → all in 100m radius
    assert t1 in aoe and aoe[t1] == 35
    assert t2 in aoe and aoe[t2] == 35
    assert t3 in aoe and aoe[t3] == 35
    # Apply damage, all drones should die (hp=10 < dmg=35)
    for tid, dmg in aoe.items():
        world.threats[tid].state.hp = max(0, world.threats[tid].state.hp - dmg)
    assert world.threats[t1].state.hp == 0
    assert world.threats[t2].state.hp == 0
    assert world.threats[t3].state.hp == 0


def test_ciws_small_radius_only_nearest() -> None:
    world = World()
    # Drones spaced 40m apart — CIWS r=30 catches only the primary
    t1 = _place_drone(world, (10000.0, 10000.0))
    t2 = _place_drone(world, (10040.0, 10000.0))
    t3 = _place_drone(world, (10000.0, 10050.0))
    spec = INTERCEPTOR_SPECS[InterceptorType.CIWS]
    detonation_pos = world.threats[t1].state.pos.copy()
    aoe = resolve_aoe(spec, detonation_pos, world.threats)
    # t1 is at distance 0 (primary), inside r=30 → dmg=12
    # t2 at 40m, t3 at 50m → outside r=30
    assert t1 in aoe
    assert t2 not in aoe, f"t2 at 40m should be outside CIWS r=30 radius, got {aoe}"
    assert t3 not in aoe


def test_aoe_dead_threats_ignored() -> None:
    """Dead threats inside radius don't get more damage (they're dead).

    Regression guard: resolve_aoe iterates `threats.values()` but the
    `not alive` filter must exclude them from the returned damage map.
    """
    world = World()
    t1 = _place_drone(world, (10000.0, 10000.0))
    t2 = _place_drone(world, (10020.0, 10000.0))
    world.threats[t2].state.alive = False
    spec = INTERCEPTOR_SPECS[InterceptorType.IRIS_T_SLS]
    detonation_pos = world.threats[t1].state.pos.copy()
    aoe = resolve_aoe(spec, detonation_pos, world.threats)
    assert t1 in aoe
    assert t2 not in aoe


if __name__ == "__main__":
    tests = [
        test_iris_t_sls_clears_3_drone_cluster,
        test_ciws_small_radius_only_nearest,
        test_aoe_dead_threats_ignored,
    ]
    for fn in tests:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\nAll {len(tests)} AOE damage tests passed.")
