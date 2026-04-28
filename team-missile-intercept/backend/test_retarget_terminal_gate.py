"""Bug 4 regression: retargeting terminal-phase gate (<2s to CPA skip).

Spec §3.5: `No retargeting for interceptors already in terminal
approach (< 2s to predicted CPA)`. Pre-fix this gate was missing —
interceptors 1s from impact on a dead target would swerve toward a new
threat they physically couldn't reach under turn-radius limits, and
coast out uselessly.

After fix: when the interceptor's target dies with < 2s to predicted
CPA, the interceptor keeps its stale target_id and coasts on the
already-computed trajectory.
"""
from __future__ import annotations

import sys

import numpy as np

from sim.types import InterceptorType, ThreatType
from sim.world import World


def _build_terminal_phase_world() -> tuple:
    """Interceptor ~1s out from target (vertical descent 1000 m/s)."""
    world = World()
    # Primary target near ground
    t1 = world.spawn_threat(
        ThreatType.DRONE,
        start_xy=(75_000.0, 5_100.0),
        target_xy=(75_000.0, 5_000.0),
        validate_location=False,
    )
    # Second drone inside the same launcher's range (SLS max ~12km)
    t2 = world.spawn_threat(
        ThreatType.DRONE,
        start_xy=(79_000.0, 5_100.0),  # 4km east of t1 — within SLS range
        target_xy=(75_000.0, 5_000.0),
        validate_location=False,
    )
    iid = world.spawn_interceptor(
        InterceptorType.IRIS_T_SLS,
        launch_pos=(75_000.0, 5_000.0, 0.0),
        initial_dir=(0.0, 0.0, 1.0),
        target_id=t1,
    )
    inter = world.interceptors[iid]
    # Place interceptor 1000m above target, descending at 1000 m/s → CPA = 1s.
    inter.state.pos = np.array([75_000.0, 5_100.0, 1_000.0])
    inter.state.vel = np.array([0.0, 0.0, -1000.0])
    # Target velocity ≈ 0 (drone hovering) so relative velocity is inter.vel
    target = world.threats[t1]
    target.state.pos = np.array([75_000.0, 5_100.0, 0.0])
    target.state.vel = np.array([0.0, 0.0, 0.0])
    return world, iid, t1, t2


def _build_non_terminal_world() -> tuple:
    """Interceptor ~5s out from target (so gate should NOT skip retarget)."""
    world = World()
    t1 = world.spawn_threat(
        ThreatType.DRONE,
        start_xy=(75_000.0, 5_100.0),
        target_xy=(75_000.0, 5_000.0),
        validate_location=False,
    )
    t2 = world.spawn_threat(
        ThreatType.DRONE,
        start_xy=(79_000.0, 5_100.0),
        target_xy=(75_000.0, 5_000.0),
        validate_location=False,
    )
    iid = world.spawn_interceptor(
        InterceptorType.IRIS_T_SLS,
        launch_pos=(75_000.0, 5_000.0, 0.0),
        initial_dir=(0.0, 0.0, 1.0),
        target_id=t1,
    )
    inter = world.interceptors[iid]
    # 5000m up, descending 1000 m/s → CPA = 5s (well outside the 2s gate).
    inter.state.pos = np.array([75_000.0, 5_100.0, 5_000.0])
    inter.state.vel = np.array([0.0, 0.0, -1000.0])
    target = world.threats[t1]
    target.state.pos = np.array([75_000.0, 5_100.0, 0.0])
    target.state.vel = np.array([0.0, 0.0, 0.0])
    return world, iid, t1, t2


def test_terminal_phase_no_retarget() -> None:
    """CPA=1s, target dies → interceptor keeps stale target_id."""
    world, iid, t1, t2 = _build_terminal_phase_world()
    # Set up prev_pos / prev_vel on the target so the gate can compute CPA
    # (world.step block 1 normally sets these). We do it manually because
    # we're killing the target out-of-band before the next step.
    target = world.threats[t1]
    target._prev_pos = target.state.pos.copy()
    target._prev_vel = target.state.vel.copy()
    # Kill target (simulate AOE collateral or another interceptor hit).
    target.state.alive = False
    world.step(0.05)
    inter = world.interceptors[iid]
    assert inter.target_id == t1, (
        f"terminal-phase gate failed: expected target_id to stay on dead "
        f"t1={t1}, but got {inter.target_id} (live t2={t2})"
    )
    print("ok  test_terminal_phase_no_retarget")


def test_non_terminal_does_retarget() -> None:
    """CPA=5s, target dies → interceptor DOES retarget to alive t2."""
    world, iid, t1, t2 = _build_non_terminal_world()
    target = world.threats[t1]
    target._prev_pos = target.state.pos.copy()
    target._prev_vel = target.state.vel.copy()
    target.state.alive = False
    world.step(0.05)
    inter = world.interceptors[iid]
    assert inter.target_id == t2, (
        f"non-terminal retarget failed: expected swap to t2={t2}, "
        f"got {inter.target_id}"
    )
    print("ok  test_non_terminal_does_retarget")


def test_missing_target_retargets_normally() -> None:
    """If the target entry is already None (pruned), no CPA info exists
    → the gate falls through to normal retarget."""
    world = World()
    t1 = world.spawn_threat(
        ThreatType.DRONE,
        start_xy=(75_000.0, 5_100.0),
        target_xy=(75_000.0, 5_000.0),
        validate_location=False,
    )
    t2 = world.spawn_threat(
        ThreatType.DRONE,
        start_xy=(79_000.0, 5_100.0),
        target_xy=(75_000.0, 5_000.0),
        validate_location=False,
    )
    iid = world.spawn_interceptor(
        InterceptorType.IRIS_T_SLS,
        launch_pos=(75_000.0, 5_000.0, 0.0),
        initial_dir=(0.0, 0.0, 1.0),
        target_id=t1,
    )
    inter = world.interceptors[iid]
    inter.state.pos = np.array([75_000.0, 5_100.0, 1_000.0])
    inter.state.vel = np.array([0.0, 0.0, -1000.0])
    # Remove t1 entirely (simulates post-prune state).
    del world.threats[t1]
    world.step(0.05)
    inter = world.interceptors[iid]
    assert inter.target_id == t2, (
        f"pruned-target retarget failed: expected t2={t2}, got "
        f"{inter.target_id}"
    )
    print("ok  test_missing_target_retargets_normally")


def main() -> None:
    test_terminal_phase_no_retarget()
    test_non_terminal_does_retarget()
    test_missing_target_retargets_normally()
    print("\nAll 3 retarget-terminal-gate tests passed.")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
