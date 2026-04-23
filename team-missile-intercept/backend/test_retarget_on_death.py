"""Unit test: interceptor reacquires a new target when its primary dies.

Verifies §3.5 environment behaviour — the retarget hook in World.step
block 2. If the original target is gone and another alive threat is in
the interceptor's launcher max_range, the interceptor's target_id is
swapped. If no candidate is in range, target_id stays on the dead threat
and the interceptor coasts to stall / timeout.
"""
from __future__ import annotations

import numpy as np

from sim.types import INTERCEPTOR_SPECS, InterceptorType, THREAT_SPECS, ThreatType
from sim.world import World


def test_retargets_when_target_dies() -> None:
    """Two drones, one interceptor. Kill the target; the interceptor's
    next step retargets to the surviving drone."""
    world = World()
    t1 = world.spawn_threat(
        ThreatType.DRONE,
        start_xy=(5000.0, 5000.0),
        target_xy=(0.0, 0.0),
        validate_location=False,
    )
    t2 = world.spawn_threat(
        ThreatType.DRONE,
        start_xy=(5200.0, 5000.0),   # inside IRIS-T SLS max_range (12 km)
        target_xy=(0.0, 0.0),
        validate_location=False,
    )
    iid = world.spawn_interceptor(
        InterceptorType.IRIS_T_SLS,
        launch_pos=(5000.0, 4900.0, 0.0),  # close to both threats
        initial_dir=(0.0, 1.0, 1.0),
        target_id=t1,
    )
    # Kill t1 — simulate it being lost to something else
    world.threats[t1].state.alive = False
    # Step the world; retarget hook fires at the top of block 2
    world.step(0.05)
    inter = world.interceptors[iid]
    assert inter.target_id == t2, (
        f"expected target swap to t2={t2}, got {inter.target_id}"
    )


def test_no_retarget_when_no_alive_threats_in_range() -> None:
    """CIWS (max_range=4km) parked alone — no target, stays on dead id."""
    world = World()
    t1 = world.spawn_threat(
        ThreatType.DRONE,
        start_xy=(5000.0, 5000.0),
        target_xy=(0.0, 0.0),
        validate_location=False,
    )
    # Second drone FAR AWAY — well outside CIWS 4km range
    t2 = world.spawn_threat(
        ThreatType.DRONE,
        start_xy=(50000.0, 50000.0),
        target_xy=(0.0, 0.0),
        validate_location=False,
    )
    iid = world.spawn_interceptor(
        InterceptorType.CIWS,
        launch_pos=(5000.0, 4900.0, 0.0),  # near t1, far from t2
        initial_dir=(0.0, 1.0, 1.0),
        target_id=t1,
    )
    world.threats[t1].state.alive = False
    world.step(0.05)
    inter = world.interceptors[iid]
    # t2 is outside CIWS max_range from launcher → no valid reacquire.
    # Interceptor retains t1 as target_id (a dead threat) and coasts.
    assert inter.target_id == t1, (
        f"expected CIWS to stay on dead t1={t1}, got {inter.target_id}"
    )


if __name__ == "__main__":
    tests = [
        test_retargets_when_target_dies,
        test_no_retarget_when_no_alive_threats_in_range,
    ]
    for fn in tests:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\nAll {len(tests)} retarget-on-death tests passed.")
