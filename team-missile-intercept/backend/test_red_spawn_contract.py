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
from sim.types import ThreatType
from sim.world import World


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


def main() -> None:
    test_north_land_helper_basic()
    test_strategic_y_floor_is_configured()
    print("\nAll 2 Red-spawn-contract prereq tests passed.")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
