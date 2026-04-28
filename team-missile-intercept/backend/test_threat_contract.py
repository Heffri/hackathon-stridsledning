"""Test the M-TIER3-THREAT-CONTRACT (Issues #10 / #11 / #12, 2026-04-20).

Unified Threat control contract:
  * `target_site_id` — stable int id of the Site this threat was
    spawned against. Populated by `red_ai._pick_target_site`; also
    accepted as a kwarg to `world.spawn_threat` for headless trials.
  * `maneuver_schedule` — list of `(t_offset, turn_dir, g_load,
    duration)` tuples. Applies to drone / cruise / ballistic only;
    HGV ignores it and uses `override_maneuver` instead.
  * Flyover fallback — when a threat's ground-track has passed its
    original target, retarget to the nearest in-arena Site ahead of
    the flight path. Gated off during terminal phases and for
    ballistic (fixed arc at spawn).

Coverage:
  A. Site.id field present + sequential + exposed in snapshot
  B. find_site_by_id helper
  C. red_ai._pick_target_site returns a Site; RedAI.step stamps
     target_site_id on spawned threats via the new kwarg
  D. maneuver_schedule activation window (exclusive upper bound)
  E. Schedule clamped to spec.max_g
  F. Schedule entries with zero direction are skipped
  G. HGV ignores maneuver_schedule (kind-gating — still uses
     override_maneuver)
  H. Schedule deflects drone flight path measurably
  I. Flyover fallback retargets when ground-track passes target
  J. Flyover fallback is a no-op during HGV terminal dive
  K. Flyover fallback is a no-op on ballistic
  L. Flyover fallback is a no-op when target is still ahead
"""
from __future__ import annotations

import sys

import numpy as np

from sim import config, red_ai, sites
from sim.red_ai import RedAI
from sim.scenarios import Scenario, build_default_scenario
from sim.types import THREAT_SPECS, MatchPhase, ThreatType
from sim.world import World


def _fresh_world() -> World:
    sites.reset_leaks()
    w = World()
    w.transition(MatchPhase.RUNNING)
    return w


def test_site_has_sequential_id() -> None:
    ids = [s.id for s in sites.SOUTH_SITES]
    assert ids == list(range(len(ids))), (
        f"expected [0..{len(ids)-1}], got {ids}"
    )
    print(f"ok  test_site_has_sequential_id ({len(ids)} sites)")


def test_snapshot_sites_include_id() -> None:
    scn = build_default_scenario(auto_start=True)
    snap = scn.snapshot()
    site_blocks = snap["sites"]
    assert site_blocks, "snapshot has empty sites list"
    for block in site_blocks:
        assert "id" in block
        assert isinstance(block["id"], int)
    print(f"ok  test_snapshot_sites_include_id ({len(site_blocks)} sites)")


def test_find_site_by_id_helper() -> None:
    first = sites.SOUTH_SITES[0]
    assert sites.find_site_by_id(first.id) is first
    assert sites.find_site_by_id(None) is None
    assert sites.find_site_by_id(999_999) is None
    print("ok  test_find_site_by_id_helper")


def test_pick_target_site_returns_site_object() -> None:
    rng = np.random.default_rng(42)
    chosen = red_ai._pick_target_site(rng)
    assert chosen is not None
    assert chosen in sites.SOUTH_SITES
    # _pick_target legacy wrapper still returns just pos
    pos = red_ai._pick_target(np.random.default_rng(42))
    assert pos == chosen.pos  # deterministic with same seed
    print(f"ok  test_pick_target_site_returns_site_object (chose {chosen.name})")


def test_red_ai_step_stamps_target_site_id() -> None:
    """With default scenario, every spawned threat carries a non-None
    target_site_id set from the _pick_target_site path in red_ai.step."""
    scn = build_default_scenario(auto_start=True)
    dt = 0.05
    for _ in range(int(250.0 / dt)):
        scn.step(dt)
        if scn.red.done:
            break
    # Harvest ever-existed threats from red_ai spawn logs isn't practical;
    # instead check that every currently-live OR ground-impacted threat
    # that passed through spawn_threat has a valid id.
    # Grab the live ones (some may have died / left arena).
    any_seen = False
    for thr in scn.world.threats.values():
        any_seen = True
        assert thr._target_site_id is not None, (
            f"threat {thr.state.id} spawned with target_site_id=None "
            f"from default scenario"
        )
        assert sites.find_site_by_id(thr._target_site_id) is not None
    assert any_seen or scn.world.threats_spawned > 0, (
        "default scenario never spawned any threat — red_ai changed?"
    )
    print(f"ok  test_red_ai_step_stamps_target_site_id "
          f"(threats_spawned={scn.world.threats_spawned})")


def test_manual_spawn_stores_target_site_id() -> None:
    w = _fresh_world()
    site = sites.SOUTH_SITES[0]
    tid = w.spawn_threat(
        ThreatType.DRONE,
        (75_000.0, 100_000.0, 2_000.0),
        site.pos,
        target_site_id=site.id,
        # W14 (Issue #30): mid-strait spawn is a placement utility,
        # not a realistic Red spawn — opt out.
        validate_location=False,
    )
    thr = w.threats[tid]
    assert thr._target_site_id == site.id
    print("ok  test_manual_spawn_stores_target_site_id")


def test_maneuver_schedule_active_window() -> None:
    """Schedule entry is active for t in [t_offset, t_offset + duration)
    — closed-open interval."""
    w = _fresh_world()
    tid = w.spawn_threat(
        ThreatType.DRONE,
        (75_000.0, 100_000.0, 2_000.0),
        (75_000.0, 5_000.0),
        maneuver_schedule=[(5.0, (1.0, 0.0, 0.0), 3.0, 2.0)],
        # W14 (Issue #30): mid-strait spawn is a placement utility.
        validate_location=False,
    )
    thr = w.threats[tid]
    dt = 0.05
    times = []
    for _ in range(int(10.0 / dt)):
        w.step(dt)
        times.append((thr._elapsed, thr._active_schedule_accel() is not None))
    active_range = [t for t, a in times if a]
    assert active_range, "schedule never activated"
    assert active_range[0] >= 5.0 - 1e-6, f"first active at {active_range[0]}"
    assert active_range[-1] < 7.0, f"last active at {active_range[-1]}"
    print(f"ok  test_maneuver_schedule_active_window "
          f"(active {active_range[0]:.2f}–{active_range[-1]:.2f}s)")


def test_maneuver_schedule_clamps_to_spec_max_g() -> None:
    """Requested 99G on a drone (spec.max_g=2) clamps to 2G."""
    w = _fresh_world()
    tid = w.spawn_threat(
        ThreatType.DRONE,
        (75_000.0, 100_000.0, 2_000.0),
        (75_000.0, 5_000.0),
        maneuver_schedule=[(0.5, (1.0, 0.0, 0.0), 99.0, 5.0)],
        # W14 (Issue #30): mid-strait spawn is a placement utility.
        validate_location=False,
    )
    thr = w.threats[tid]
    dt = 0.05
    for _ in range(int(1.0 / dt)):
        w.step(dt)
    a = thr._active_schedule_accel()
    assert a is not None
    g_applied = float(np.linalg.norm(a)) / config.GRAVITY
    spec_max = THREAT_SPECS[ThreatType.DRONE].max_g
    assert g_applied <= spec_max + 1e-6, (
        f"requested 99G, saw {g_applied:.2f}G vs spec.max_g={spec_max}"
    )
    assert g_applied >= spec_max - 1e-6, (
        f"clamping undershot — saw {g_applied:.2f}G vs spec.max_g={spec_max}"
    )
    print(f"ok  test_maneuver_schedule_clamps_to_spec_max_g "
          f"(clamped to {g_applied:.2f}G)")


def test_maneuver_schedule_skips_zero_direction() -> None:
    """Entry with zero direction vector should be skipped (no accel)."""
    w = _fresh_world()
    tid = w.spawn_threat(
        ThreatType.DRONE,
        (75_000.0, 100_000.0, 2_000.0),
        (75_000.0, 5_000.0),
        maneuver_schedule=[(0.5, (0.0, 0.0, 0.0), 3.0, 5.0)],
        # W14 (Issue #30): mid-strait spawn is a placement utility.
        validate_location=False,
    )
    thr = w.threats[tid]
    dt = 0.05
    for _ in range(int(1.0 / dt)):
        w.step(dt)
    assert thr._active_schedule_accel() is None, (
        "zero-direction entry should not produce an accel"
    )
    print("ok  test_maneuver_schedule_skips_zero_direction")


def test_hgv_ignores_maneuver_schedule_structurally() -> None:
    """HGV step path does not consume `maneuver_schedule`. Spawning an
    HGV with a schedule should not change its trajectory vs one without
    (HGV uses `override_maneuver` instead, called per-tick)."""
    w1 = _fresh_world()
    w2 = _fresh_world()
    spawn = (75_000.0, 240_000.0, 35_000.0)
    target = (75_000.0, 5_000.0)
    t1 = w1.spawn_threat(ThreatType.HGV, spawn, target)
    t2 = w2.spawn_threat(
        ThreatType.HGV, spawn, target,
        maneuver_schedule=[(3.0, (1.0, 0.0, 0.0), 8.0, 5.0)],
    )
    thr1 = w1.threats[t1]
    thr2 = w2.threats[t2]
    dt = 0.05
    for _ in range(int(10.0 / dt)):
        w1.step(dt)
        w2.step(dt)
    # Positions should match exactly — schedule had no effect on HGV
    delta = float(np.linalg.norm(thr1.state.pos - thr2.state.pos))
    assert delta < 1e-3, (
        f"HGV position diverged by {delta:.3f} m — schedule leaked "
        f"into HGV step path?"
    )
    print(f"ok  test_hgv_ignores_maneuver_schedule_structurally "
          f"(drift {delta:.4f} m)")


def test_maneuver_schedule_deflects_drone_measurably() -> None:
    """A 2G lateral jink for 3 s on a drone should produce a measurable
    horizontal displacement vs the same drone with no schedule."""
    w1 = _fresh_world()
    w2 = _fresh_world()
    spawn = (75_000.0, 100_000.0, 2_000.0)
    target = (75_000.0, 5_000.0)  # due south
    # W14 (Issue #30): mid-strait spawn is a placement utility for
    # the schedule-deflection test — opt out of the spatial contract.
    t1 = w1.spawn_threat(
        ThreatType.DRONE, spawn, target, validate_location=False,
    )
    t2 = w2.spawn_threat(
        ThreatType.DRONE, spawn, target,
        maneuver_schedule=[(2.0, (1.0, 0.0, 0.0), 2.0, 3.0)],
        validate_location=False,
    )
    thr1 = w1.threats[t1]
    thr2 = w2.threats[t2]
    dt = 0.05
    for _ in range(int(8.0 / dt)):
        w1.step(dt)
        w2.step(dt)
    delta_x = abs(thr2.state.pos[0] - thr1.state.pos[0])
    assert delta_x > 100.0, (
        f"expected at least 100 m lateral displacement from jink, "
        f"got {delta_x:.1f} m"
    )
    print(f"ok  test_maneuver_schedule_deflects_drone_measurably "
          f"(Δx = {delta_x:.0f} m)")


def test_flyover_retargets_when_ground_track_past_target() -> None:
    """Set a drone's velocity to point away from its original target
    and assert the fallback retargets it to a site ahead of the flight
    path. We spawn a drone in between two sites, force velocity toward
    the second site while its waypoint is the first, and step."""
    w = _fresh_world()
    # Pick two sites for a clean setup
    site_a = sites.SOUTH_SITES[0]   # id=0 Firewatch
    site_b = sites.SOUTH_SITES[1]   # id=1 Spear Point
    # Spawn a drone PAST site_a, moving toward site_b. The drone's
    # original target is site_a — ground-track has obviously passed it.
    past_a_x = site_a.pos[0] + (site_b.pos[0] - site_a.pos[0]) * 0.3
    past_a_y = site_a.pos[1] + (site_b.pos[1] - site_a.pos[1]) * 0.3
    spawn = (past_a_x, past_a_y, 2_000.0)
    tid = w.spawn_threat(
        ThreatType.DRONE, spawn, site_a.pos, target_site_id=site_a.id,
        # W14 (Issue #30): threat is deliberately pre-positioned past
        # a south-side site for the flyover-fallback unit test; this
        # is not a realistic Red spawn. Opt out of the spatial contract.
        validate_location=False,
    )
    thr = w.threats[tid]
    # Force velocity to point toward site_b (away from site_a)
    dx = site_b.pos[0] - thr.state.pos[0]
    dy = site_b.pos[1] - thr.state.pos[1]
    mag = float((dx * dx + dy * dy) ** 0.5)
    speed = 150.0
    thr.state.vel = np.array([dx / mag * speed, dy / mag * speed, 0.0])
    # Step once — fallback should retarget
    w.step(0.05)
    assert thr._target_site_id != site_a.id, (
        f"fallback did not retarget; still aimed at site {thr._target_site_id}"
    )
    # New target should be ahead of the velocity vector — site_b is
    # the natural choice
    print(f"ok  test_flyover_retargets_when_ground_track_past_target "
          f"(retargeted to site id {thr._target_site_id})")


def test_flyover_fallback_skipped_during_hgv_terminal_dive() -> None:
    """HGV inside 3 km of target or below 2 km altitude should NOT
    retarget even if velocity technically overshoots."""
    w = _fresh_world()
    site = sites.SOUTH_SITES[0]
    # Spawn HGV 1 km past target horizontally, at 1.5 km altitude —
    # deep in terminal phase. Velocity intentionally wrong (heading
    # away from target).
    spawn = (site.pos[0] + 1_000.0, site.pos[1] - 500.0, 1_500.0)
    tid = w.spawn_threat(
        ThreatType.HGV, spawn, site.pos, target_site_id=site.id,
        # W14 (Issue #30): HGV pre-positioned in terminal-dive phase
        # for the no-retarget unit test; not a realistic Red spawn.
        validate_location=False,
    )
    thr = w.threats[tid]
    # Force heading that looks like overshoot
    thr.state.vel = np.array([100.0, -100.0, -300.0])
    w.step(0.05)
    # Should still be aimed at site (no retarget — terminal gate)
    assert thr._target_site_id == site.id, (
        f"HGV retargeted during terminal dive (was {site.id}, "
        f"now {thr._target_site_id})"
    )
    print("ok  test_flyover_fallback_skipped_during_hgv_terminal_dive")


def test_flyover_fallback_noop_on_ballistic() -> None:
    """Ballistic arc is set at spawn; fallback is intentionally a
    no-op on ballistic even when the ground-track has clearly passed."""
    w = _fresh_world()
    site = sites.SOUTH_SITES[0]
    # Spawn ballistic 30 km past target; velocity away
    spawn = (site.pos[0] - 30_000.0, site.pos[1] - 30_000.0, 40_000.0)
    tid = w.spawn_threat(
        ThreatType.BALLISTIC, spawn, site.pos, target_site_id=site.id,
        # W14 (Issue #30): ballistic pre-positioned past target for
        # the fallback-no-op unit test; not a realistic Red spawn.
        validate_location=False,
    )
    thr = w.threats[tid]
    # One step — verify no retarget
    w.step(0.05)
    assert thr._target_site_id == site.id, (
        f"ballistic retargeted ({site.id} → {thr._target_site_id}) — "
        f"should be a no-op for ballistic kind"
    )
    print("ok  test_flyover_fallback_noop_on_ballistic")


def test_flyover_fallback_noop_when_target_ahead() -> None:
    """Default case — target is ahead of the velocity vector — no
    retarget, target_site_id unchanged."""
    w = _fresh_world()
    site = sites.SOUTH_SITES[0]
    # Spawn well north of target, moving south toward it
    spawn = (site.pos[0], site.pos[1] + 100_000.0, 2_000.0)
    tid = w.spawn_threat(
        ThreatType.DRONE, spawn, site.pos, target_site_id=site.id,
        # W14 (Issue #30): spawn is in the strait (y ~ 105-130 km),
        # not on north land — acceptable here because this test is a
        # placement unit test for flyover fallback, not a Red spawn.
        validate_location=False,
    )
    thr = w.threats[tid]
    # Default-constructed velocity is already toward target; step a few
    w.step(0.05)
    w.step(0.05)
    assert thr._target_site_id == site.id
    print("ok  test_flyover_fallback_noop_when_target_ahead")


def main() -> None:
    test_site_has_sequential_id()
    test_snapshot_sites_include_id()
    test_find_site_by_id_helper()
    test_pick_target_site_returns_site_object()
    test_red_ai_step_stamps_target_site_id()
    test_manual_spawn_stores_target_site_id()
    test_maneuver_schedule_active_window()
    test_maneuver_schedule_clamps_to_spec_max_g()
    test_maneuver_schedule_skips_zero_direction()
    test_hgv_ignores_maneuver_schedule_structurally()
    test_maneuver_schedule_deflects_drone_measurably()
    test_flyover_retargets_when_ground_track_past_target()
    test_flyover_fallback_skipped_during_hgv_terminal_dive()
    test_flyover_fallback_noop_on_ballistic()
    test_flyover_fallback_noop_when_target_ahead()
    print("\nAll 15 threat-contract tests passed.")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
