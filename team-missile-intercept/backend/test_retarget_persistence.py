"""Bug 8 regression — retargeted interceptors persist and keep firing.

Root cause (2026-04-24): `Interceptor.target_id` (driving PN guidance,
written by `World.step`'s retarget hook) and `EntityState.target_id`
(read by snapshot / HUD / `LearnedBlueAI` orphan cleanup) were two
separate attributes. The orphan cleanup marked any interceptor whose
`state.target_id` pointed at a dead threat as `state.alive = False`.
Because retargeting only wrote to `inter.target_id`, not
`inter.state.target_id`, freshly retargeted interceptors visibly
swung onto a new threat and then vanished within a few frames.

Fix was two-fold:
  * Remove the orphan cleanup from `LearnedBlueAI.step`.
  * Mirror `state.target_id` in `World.step`'s retargeting branch.

This regression test asserts the second: a retargeted interceptor
survives, its `target_id` AND `state.target_id` both point at the new
threat, and it stays alive long enough to engage. Framing: arcade-game
hackathon demo.
"""
from __future__ import annotations

import sys

from sim.types import InterceptorType, ThreatType
from sim.world import World


DT = 0.05


def test_retarget_syncs_state_target_id_and_interceptor_persists() -> None:
    """Two drones A and B within IRIS-T SLS max_range (12 km). Fire
    an SLS at A, kill A mid-flight, single-step the world.

    Expect on the post-retarget tick:
      * interceptor still alive (was not killed by a stale-target hook)
      * `inter.target_id` == B's id (PN guidance sees new target)
      * `inter.state.target_id` == B's id (snapshot mirror stays in sync)

    Single-step to isolate the retarget + mirror write from any
    downstream engagement (B is close enough that a 10 s run would
    let the interceptor actually detonate on B, conflating "survives
    retarget" with "kills the new target").
    """
    world = World()
    tA = world.spawn_threat(
        ThreatType.DRONE,
        start_xy=(5_000.0, 5_000.0, 500.0),
        target_xy=(0.0, 0.0),
        validate_location=False,
    )
    tB = world.spawn_threat(
        ThreatType.DRONE,
        start_xy=(5_300.0, 5_000.0, 500.0),  # inside SLS 12 km range
        target_xy=(0.0, 0.0),
        validate_location=False,
    )
    iid = world.spawn_interceptor(
        InterceptorType.IRIS_T_SLS,
        launch_pos=(5_000.0, 4_900.0, 0.0),
        initial_dir=(0.0, 1.0, 1.0),
        target_id=tA,
    )

    # Artificially kill A mid-flight (simulates a different interceptor
    # getting the kill, or A self-destructing on ground-impact).
    world.threats[tA].state.alive = False

    # Single step — retarget hook should fire at the top of block 2.
    world.step(DT)

    assert iid in world.interceptors, (
        "interceptor was pruned — retarget hook should have kept it alive"
    )
    inter = world.interceptors[iid]
    assert inter.state.alive, (
        "interceptor marked dead on the same tick A died — possible stale-"
        "target cleanup regression"
    )
    assert inter.target_id == tB, (
        f"expected inter.target_id to swap to B ({tB}), got {inter.target_id}"
    )
    assert inter.state.target_id == tB, (
        f"expected inter.state.target_id mirrored to B ({tB}), "
        f"got {inter.state.target_id} — snapshot / HUD / RL obs will show stale target"
    )


def test_retarget_state_target_id_mirror_matches_interceptor_target_id() -> None:
    """Single-step sanity: after one world.step where A died, verify
    both target_id attributes agree. Catches regressions where the
    mirror write in World.step gets removed."""
    world = World()
    tA = world.spawn_threat(
        ThreatType.DRONE,
        start_xy=(4_000.0, 5_000.0, 500.0),
        target_xy=(0.0, 0.0),
        validate_location=False,
    )
    tB = world.spawn_threat(
        ThreatType.DRONE,
        start_xy=(4_300.0, 5_000.0, 500.0),
        target_xy=(0.0, 0.0),
        validate_location=False,
    )
    iid = world.spawn_interceptor(
        InterceptorType.IRIS_T_SLS,
        launch_pos=(4_000.0, 4_900.0, 0.0),
        initial_dir=(0.0, 1.0, 1.0),
        target_id=tA,
    )
    world.threats[tA].state.alive = False
    world.step(DT)
    inter = world.interceptors[iid]
    assert inter.target_id == inter.state.target_id, (
        f"target_id mirror drift: inter.target_id={inter.target_id}, "
        f"state.target_id={inter.state.target_id}"
    )
    assert inter.target_id == tB


def main() -> int:
    print("=== Retarget persistence regression (Bug 8) ===")
    tests = [
        test_retarget_syncs_state_target_id_and_interceptor_persists,
        test_retarget_state_target_id_mirror_matches_interceptor_target_id,
    ]
    for fn in tests:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\nAll {len(tests)} retarget-persistence tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
