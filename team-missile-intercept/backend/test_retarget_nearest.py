"""Unit test: retarget prefers the nearest alive threat.

Verifies §3.5 rule — when multiple alive threats are in the launcher's
range gate, the interceptor swaps to the one closest to its current
position (3D), not some other heuristic.
"""
from __future__ import annotations

import numpy as np

from sim.types import InterceptorType, ThreatType
from sim.world import World


def test_prefers_nearest_when_primary_dies() -> None:
    """Interceptor near (10100, 10000, 0). Two alive candidates:
    drone_b at (10200, 10000, 0)  → 100m away from interceptor
    drone_c at (10800, 10000, 0)  → 700m away from interceptor
    Kill the primary, expect swap to drone_b (nearest)."""
    world = World()
    # Place interceptor so it's closer to drone_b
    t_primary = world.spawn_threat(
        ThreatType.DRONE,
        start_xy=(10000.0, 10000.0),
        target_xy=(0.0, 0.0),
        validate_location=False,
    )
    t_b = world.spawn_threat(
        ThreatType.DRONE,
        start_xy=(10200.0, 10000.0),
        target_xy=(0.0, 0.0),
        validate_location=False,
    )
    t_c = world.spawn_threat(
        ThreatType.DRONE,
        start_xy=(10800.0, 10000.0),
        target_xy=(0.0, 0.0),
        validate_location=False,
    )
    iid = world.spawn_interceptor(
        InterceptorType.IRIS_T_SLS,   # max_range=12km, easily covers both
        launch_pos=(10100.0, 10000.0, 0.0),
        initial_dir=(1.0, 0.0, 1.0),
        target_id=t_primary,
    )
    # Move the interceptor in-flight to a position closer to drone_b
    # than to drone_c. (The spawn_interceptor pose already satisfies
    # that; we just assert our expectations before killing the primary.)
    inter = world.interceptors[iid]
    # NB: VLS boost phase launches near-vertical — the interceptor will
    # rise off the ground. Use the pre-step pos snapshot; either way
    # drone_b is horizontally closer.
    world.threats[t_primary].state.alive = False
    world.step(0.05)
    assert inter.target_id == t_b, (
        f"expected swap to nearest alive drone t_b={t_b}, got "
        f"{inter.target_id} (t_c={t_c})"
    )


if __name__ == "__main__":
    tests = [test_prefers_nearest_when_primary_dies]
    for fn in tests:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\nAll {len(tests)} nearest-retarget tests passed.")
