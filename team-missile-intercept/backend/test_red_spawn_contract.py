"""Test W14 (Issue #30) — Red spawn contract.

Formalises the spatial spawn rules that Boyu's future Red AI will
consume when it replaces the wave spawner with tactical spawn
decisions. Today `RedAI.step` routes every spawn through
`_spawn_point` / `_sample_spawn`, which happen to produce valid
locations by construction. The future Red AI will call
`world.spawn_threat` directly with its own `(x, y, z)`, so the
runtime validates per kind:

  * Drone / Cruise — (x, y) must lie on north-side land
    (`terrain.point_on_north_land`). Red mainland or islands.
  * Ballistic / HGV — y must be >= `config.STRATEGIC_Y_FLOOR`
    (gives Blue at least ~20+ s of engagement window).
  * Altitude is NOT validated — Red AI's choice; bad altitude is
    gameplay feedback, not a spawn-contract violation.

Cases covered (see CONTRACT_SEAMS.md §9):

  A1. `terrain.point_on_north_land` basic sanity — known north-side
      launcher positions are on land, strait centre is sea.
  A2. `config.STRATEGIC_Y_FLOOR` exists, positive, inside arena.
  C1. Valid spawns per kind — succeed, return int id.
  C2. Drone / cruise in the strait — ValueError with "north-side land".
  C3. Drone / cruise on south-side land — ValueError.
  C4. Ballistic / HGV below the Y floor — ValueError mentioning floor.
  C5. Boundary: y exactly at floor succeeds; y == floor - 1 rejects.
  C6. Default scenario still runs end-to-end — the existing wave
      spawner produces coords the contract accepts (regression).
"""
from __future__ import annotations

import sys

from sim import config, sites, terrain
from sim.scenarios import build_default_scenario
from sim.types import MatchPhase, ThreatType
from sim.world import World


def _fresh_world() -> World:
    """Empty world, transitioned to RUNNING so spawn_threat is live.
    Sites are reset per call because `spawn_threat` doesn't touch sites
    but later regression tests build full scenarios that do."""
    sites.reset_leaks()
    w = World()
    w.transition(MatchPhase.RUNNING)
    return w


# A couple of clearly-invalid coords reused across cases.
_STRAIT_MID = (75_000.0, 120_000.0)         # world x mid, strait centreline
_STRAIT_EAST = (10_000.0, 110_000.0)        # strait, slightly off-centre
_BLUE_BASE_XY = (
    float(config.BLUE_BASE_POS[0]),
    float(config.BLUE_BASE_POS[1]),
)
# Known valid ballistic / HGV spawn (inside STRATEGIC_Y_BAND).
_VALID_STRATEGIC_XY = (75_000.0, 240_000.0)


# --- Subtask A: prerequisites -----------------------------------------

def test_north_land_helper_basic() -> None:
    """Known north-side launcher positions report True; the strait
    centre reports False. Sanity-check that the pre-existing
    `point_on_north_land` matches the CSV polygon data the rest of
    the runtime uses (same pattern as BLUE validation)."""
    for kind, positions in config.RED_LAUNCHER_POSITIONS.items():
        for (x, y) in positions:
            assert terrain.point_on_north_land(x, y), (
                f"RED_LAUNCHER_POSITIONS[{kind!r}] ({x}, {y}) should "
                f"report as north-side land but does not"
            )
    # Strait centre (x mid, y = strait centreline) — sea.
    strait_x = config.ARENA_X * 0.5
    strait_y = config.STRAIT_CENTER_Y
    assert not terrain.point_on_north_land(strait_x, strait_y), (
        f"strait centre ({strait_x}, {strait_y}) should be sea"
    )
    # Blue base — south-side land, not north.
    bx, by, _ = config.BLUE_BASE_POS
    assert not terrain.point_on_north_land(bx, by), (
        f"Blue base ({bx}, {by}) should be south land, not north"
    )
    print("ok  test_north_land_helper_basic")


def test_strategic_y_floor_is_configured() -> None:
    """`STRATEGIC_Y_FLOOR` exists, positive, inside the arena, and
    at least 150 km north of the origin (so Blue AI has real flight
    time before terminal phase)."""
    assert hasattr(config, "STRATEGIC_Y_FLOOR"), (
        "config.STRATEGIC_Y_FLOOR missing"
    )
    floor = config.STRATEGIC_Y_FLOOR
    assert isinstance(floor, (int, float))
    assert floor >= 150_000.0, (
        f"STRATEGIC_Y_FLOOR={floor} is below 150 km — Blue AI would "
        f"not have enough reaction time vs Mach-17 HGV"
    )
    assert floor <= config.ARENA_Y, (
        f"STRATEGIC_Y_FLOOR={floor} is outside the arena "
        f"(ARENA_Y={config.ARENA_Y})"
    )
    print(f"ok  test_strategic_y_floor_is_configured "
          f"({floor / 1000:.0f} km)")


# --- Subtask C: valid spawns succeed (regression guard) ---------------

def test_valid_drone_spawns_at_every_red_launcher() -> None:
    """Every entry in `RED_LAUNCHER_POSITIONS['drone']` is a legal
    drone spawn. Returns an int id, no raise."""
    target = _BLUE_BASE_XY
    count = 0
    for (x, y) in config.RED_LAUNCHER_POSITIONS["drone"]:
        w = _fresh_world()
        tid = w.spawn_threat(
            ThreatType.DRONE, (float(x), float(y), 2_000.0), target
        )
        assert isinstance(tid, int) and tid > 0
        assert tid in w.threats
        count += 1
    print(f"ok  test_valid_drone_spawns_at_every_red_launcher "
          f"({count} positions)")


def test_valid_cruise_spawns_at_every_red_launcher() -> None:
    """Every entry in `RED_LAUNCHER_POSITIONS['cruise_sub']` is a legal
    cruise spawn."""
    target = _BLUE_BASE_XY
    count = 0
    for (x, y) in config.RED_LAUNCHER_POSITIONS["cruise_sub"]:
        w = _fresh_world()
        tid = w.spawn_threat(
            ThreatType.CRUISE_SUB, (float(x), float(y), 3_000.0), target
        )
        assert isinstance(tid, int) and tid > 0
        count += 1
    print(f"ok  test_valid_cruise_spawns_at_every_red_launcher "
          f"({count} positions)")


def test_valid_ballistic_spawn_above_floor() -> None:
    """Ballistic at y=240 km (inside STRATEGIC_Y_BAND) is legal."""
    w = _fresh_world()
    spawn = (_VALID_STRATEGIC_XY[0], _VALID_STRATEGIC_XY[1], 40_000.0)
    tid = w.spawn_threat(ThreatType.BALLISTIC, spawn, _BLUE_BASE_XY)
    assert isinstance(tid, int) and tid > 0
    print("ok  test_valid_ballistic_spawn_above_floor")


def test_valid_hgv_spawn_above_floor() -> None:
    """HGV at y=240 km is legal."""
    w = _fresh_world()
    spawn = (_VALID_STRATEGIC_XY[0], _VALID_STRATEGIC_XY[1], 35_000.0)
    tid = w.spawn_threat(ThreatType.HGV, spawn, _BLUE_BASE_XY)
    assert isinstance(tid, int) and tid > 0
    print("ok  test_valid_hgv_spawn_above_floor")


# --- Subtask C: drone / cruise off north land → rejected --------------

def test_drone_in_strait_rejected() -> None:
    """Drone spawn at the strait centre — not on north land — raises."""
    w = _fresh_world()
    spawn = (_STRAIT_MID[0], _STRAIT_MID[1], 2_000.0)
    try:
        w.spawn_threat(ThreatType.DRONE, spawn, _BLUE_BASE_XY)
    except ValueError as e:
        assert "north-side land" in str(e), (
            f"expected 'north-side land' in error, got: {e!r}"
        )
        print(f"ok  test_drone_in_strait_rejected "
              f"(msg: {str(e)[:70]}...)")
        return
    raise AssertionError("expected ValueError, none raised")


def test_cruise_in_strait_rejected() -> None:
    """Cruise spawn in strait — raises."""
    w = _fresh_world()
    spawn = (_STRAIT_EAST[0], _STRAIT_EAST[1], 3_000.0)
    try:
        w.spawn_threat(ThreatType.CRUISE_SUB, spawn, _BLUE_BASE_XY)
    except ValueError as e:
        assert "north-side land" in str(e)
        print("ok  test_cruise_in_strait_rejected")
        return
    raise AssertionError("expected ValueError, none raised")


def test_drone_on_south_land_rejected() -> None:
    """Drone spawn at the Blue base — south-side land, not north.
    Should never happen in practice (sanity guard)."""
    w = _fresh_world()
    spawn = (_BLUE_BASE_XY[0], _BLUE_BASE_XY[1], 2_000.0)
    try:
        w.spawn_threat(ThreatType.DRONE, spawn, _BLUE_BASE_XY)
    except ValueError as e:
        assert "north-side land" in str(e)
        print("ok  test_drone_on_south_land_rejected")
        return
    raise AssertionError("expected ValueError, none raised")


# --- Subtask C: ballistic / HGV below the Y floor → rejected ----------

def test_ballistic_below_floor_rejected() -> None:
    """Ballistic at y=50 km — far below STRATEGIC_Y_FLOOR — raises
    with a message naming the floor."""
    w = _fresh_world()
    spawn = (75_000.0, 50_000.0, 30_000.0)
    try:
        w.spawn_threat(ThreatType.BALLISTIC, spawn, _BLUE_BASE_XY)
    except ValueError as e:
        assert "STRATEGIC_Y_FLOOR" in str(e), (
            f"expected 'STRATEGIC_Y_FLOOR' in error, got: {e!r}"
        )
        print(f"ok  test_ballistic_below_floor_rejected "
              f"(msg: {str(e)[:70]}...)")
        return
    raise AssertionError("expected ValueError, none raised")


def test_hgv_one_metre_below_floor_rejected() -> None:
    """HGV at y = STRATEGIC_Y_FLOOR - 1 — boundary case, exactly one
    metre below the floor — rejected."""
    w = _fresh_world()
    spawn = (75_000.0, config.STRATEGIC_Y_FLOOR - 1.0, 35_000.0)
    try:
        w.spawn_threat(ThreatType.HGV, spawn, _BLUE_BASE_XY)
    except ValueError as e:
        assert "STRATEGIC_Y_FLOOR" in str(e)
        print("ok  test_hgv_one_metre_below_floor_rejected")
        return
    raise AssertionError("expected ValueError, none raised")


def test_hgv_exactly_at_floor_accepted() -> None:
    """HGV at y = STRATEGIC_Y_FLOOR — boundary, inclusive floor —
    succeeds."""
    w = _fresh_world()
    spawn = (75_000.0, float(config.STRATEGIC_Y_FLOOR), 35_000.0)
    tid = w.spawn_threat(ThreatType.HGV, spawn, _BLUE_BASE_XY)
    assert isinstance(tid, int) and tid > 0
    print("ok  test_hgv_exactly_at_floor_accepted")


# --- Subtask C: default scenario regression ---------------------------

def test_default_scenario_runs_all_waves_without_contract_violation() -> None:
    """The existing wave spawner (`_spawn_point` + `_sample_spawn`)
    produces coords the new validation always accepts. Building a
    default scenario and stepping 250 s (enough for every wave) must
    run to `red.done` with `threats_spawned == 26` and zero
    ValueError propagating out. Regression guard for the case where
    the validation is somehow too tight for the wave spawner's
    random samples."""
    sites.reset_leaks()
    scn = build_default_scenario(auto_start=True)
    dt = 0.05
    try:
        for _ in range(int(250.0 / dt)):
            scn.step(dt)
            if scn.red.done:
                break
    except ValueError as e:
        raise AssertionError(
            f"default scenario wave spawner produced a coord the "
            f"Red-spawn-contract rejected: {e!r}"
        )
    assert scn.red.done, (
        f"red.done never fired after 250 s — wave spawner regressed?"
    )
    # The default wave spec (build_demo_waves) totals 26 threats:
    # 3+3+2+4+2+1+2+2+2+3+2 = 26. red_ai also skips 0 under default
    # budget, so threats_spawned should be exactly 26.
    assert scn.world.threats_spawned == 26, (
        f"expected 26 threats spawned under default scenario, got "
        f"{scn.world.threats_spawned}"
    )
    print(f"ok  test_default_scenario_runs_all_waves_without_contract_violation "
          f"(spawned={scn.world.threats_spawned}, red.done={scn.red.done})")


def main() -> None:
    # Subtask A — prerequisites
    test_north_land_helper_basic()
    test_strategic_y_floor_is_configured()
    # Subtask C — valid spawns succeed
    test_valid_drone_spawns_at_every_red_launcher()
    test_valid_cruise_spawns_at_every_red_launcher()
    test_valid_ballistic_spawn_above_floor()
    test_valid_hgv_spawn_above_floor()
    # Subtask C — drone / cruise off-land rejections
    test_drone_in_strait_rejected()
    test_cruise_in_strait_rejected()
    test_drone_on_south_land_rejected()
    # Subtask C — ballistic / HGV below-floor rejections + boundary
    test_ballistic_below_floor_rejected()
    test_hgv_one_metre_below_floor_rejected()
    test_hgv_exactly_at_floor_accepted()
    # Subtask C — default scenario regression
    test_default_scenario_runs_all_waves_without_contract_violation()
    print("\nAll 13 Red-spawn-contract tests passed.")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
