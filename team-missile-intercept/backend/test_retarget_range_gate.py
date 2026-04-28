"""Unit test: retarget range gate uses launcher position.

Verifies §3.5 constraint: the 2D ground distance from the
interceptor's LAUNCHER (fixed position) to a candidate threat must be
within `spec.max_range`. An interceptor that has already flown into
another threat's airspace doesn't get "free" longer range via its
current position.
"""
from __future__ import annotations

import numpy as np

from sim.types import InterceptorType, ThreatType
from sim.world import World


def test_candidate_outside_launcher_range_is_not_retargeted() -> None:
    """CIWS launcher at (0, 0). Primary threat at (2000, 0) (inside
    CIWS 4 km range). Candidate at (5000, 0) — just outside range from
    launcher but would be in range if measured from the interceptor
    at (1500, 0) (distance 3500 m). Retargeter must use the launcher's
    fixed pos and skip the out-of-range candidate."""
    world = World()
    t_primary = world.spawn_threat(
        ThreatType.DRONE,
        start_xy=(2000.0, 0.0),
        target_xy=(0.0, 0.0),
        validate_location=False,
    )
    t_candidate = world.spawn_threat(
        ThreatType.DRONE,
        start_xy=(5000.0, 0.0),
        target_xy=(0.0, 0.0),
        validate_location=False,
    )
    iid = world.spawn_interceptor(
        InterceptorType.CIWS,
        launch_pos=(0.0, 0.0, 0.0),   # launcher at origin
        initial_dir=(1.0, 0.0, 0.5),
        target_id=t_primary,
    )
    # Move the interceptor mid-flight to where the candidate would
    # be in range if the gate used interceptor position.
    inter = world.interceptors[iid]
    inter.state.pos = np.array([1500.0, 0.0, 300.0])
    # Primary dies — retarget attempt fires next world.step
    world.threats[t_primary].state.alive = False
    world.step(0.05)
    # Launcher-pos distance to candidate = 5000 m > CIWS max_range 4000
    # → no retarget. Interceptor keeps dead primary and coasts.
    assert inter.target_id == t_primary, (
        f"expected CIWS to reject candidate outside launcher range; got "
        f"target_id={inter.target_id} (candidate={t_candidate})"
    )


def test_candidate_inside_launcher_range_is_retargeted() -> None:
    """Symmetry check: if the candidate IS inside launcher range, the
    retargeter picks it (otherwise the above test is vacuous)."""
    world = World()
    t_primary = world.spawn_threat(
        ThreatType.DRONE,
        start_xy=(2000.0, 0.0),
        target_xy=(0.0, 0.0),
        validate_location=False,
    )
    t_candidate = world.spawn_threat(
        ThreatType.DRONE,
        start_xy=(3500.0, 0.0),   # INSIDE CIWS 4km range from (0,0)
        target_xy=(0.0, 0.0),
        validate_location=False,
    )
    iid = world.spawn_interceptor(
        InterceptorType.CIWS,
        launch_pos=(0.0, 0.0, 0.0),
        initial_dir=(1.0, 0.0, 0.5),
        target_id=t_primary,
    )
    world.threats[t_primary].state.alive = False
    world.step(0.05)
    inter = world.interceptors[iid]
    assert inter.target_id == t_candidate, (
        f"expected CIWS to accept in-range candidate t_candidate="
        f"{t_candidate}; got target_id={inter.target_id}"
    )


if __name__ == "__main__":
    tests = [
        test_candidate_outside_launcher_range_is_not_retargeted,
        test_candidate_inside_launcher_range_is_retargeted,
    ]
    for fn in tests:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\nAll {len(tests)} range-gate retarget tests passed.")
