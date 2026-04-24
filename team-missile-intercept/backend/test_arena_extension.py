"""Bug 9 regression — ARENA_Y extended 250 km → 350 km.

Ballistic / HGV spawn via `STRATEGIC_Y_BAND = (ARENA_Y - 15k, ARENA_Y
- 5k)`, so the pre-fix 250 km arena placed their spawn at 235-245 km
— only ~160 km north of the northernmost military site. Mach-13
ballistic at 4459 m/s covered that in 35 s, leaving PAC-3 a 15.7 s
intercept window vs a 10-15 s fly-out → ~1-5 s margin, typically no
intercept.

Bumping ARENA_Y to 350 km pushes the strategic band to 335-345 km,
giving Mach-13 ballistic a 59 s flight time to Spear Point — a
2-3× safety margin on PAC-3 intercept.

Framing: arcade-game hackathon demo. 150 km vs 350 km are arcade
arena numbers; Mach-13 / Mach-17 speeds are public encyclopedia-level
balance stats.
"""
from __future__ import annotations

import sys

import numpy as np

from sim import config
from sim.red_ai import STRATEGIC_Y_BAND, RedAI
from sim.types import ThreatType


def test_arena_y_is_350km() -> None:
    """Top-level arena constant locked at 350 km."""
    assert config.ARENA_Y == 350_000.0, (
        f"expected ARENA_Y=350_000 for strategic-rear spawn zone, "
        f"got {config.ARENA_Y}"
    )


def test_strategic_band_is_far_north() -> None:
    """STRATEGIC_Y_BAND is `ARENA_Y - 15k .. ARENA_Y - 5k`."""
    lo, hi = STRATEGIC_Y_BAND
    assert lo >= 335_000.0, (
        f"STRATEGIC_Y_BAND low edge should be >= 335_000, got {lo}"
    )
    assert hi <= 345_000.0, (
        f"STRATEGIC_Y_BAND high edge should be <= 345_000, got {hi}"
    )
    assert lo < hi, f"band must be non-empty: lo={lo} hi={hi}"


def test_strategic_floor_fits_inside_new_arena() -> None:
    """STRATEGIC_Y_FLOOR (180 km) still sits comfortably inside the
    new arena. The spawn contract (`world.spawn_threat` ValueError
    on y < floor for ballistic/HGV) is unchanged."""
    assert config.STRATEGIC_Y_FLOOR == 180_000.0
    assert config.STRATEGIC_Y_FLOOR <= config.ARENA_Y


def test_ballistic_spawn_lands_in_far_north_strip() -> None:
    """Sample 100 ballistic spawn points via RedAI._spawn_point;
    every one must fall inside STRATEGIC_Y_BAND, which is now at
    335-345 km instead of the pre-fix 235-245 km."""
    red = RedAI([])
    base_x = config.BLUE_BASE_POS[0]
    base_y = config.BLUE_BASE_POS[1]
    spawns = [
        red._spawn_point(ThreatType.BALLISTIC, base_x, base_y)
        for _ in range(100)
    ]
    lo, hi = STRATEGIC_Y_BAND
    ys = np.array([s[1] for s in spawns])
    assert float(ys.min()) >= lo, (
        f"a ballistic sample was below STRATEGIC_Y_BAND low ({lo}): min={ys.min()}"
    )
    assert float(ys.max()) <= hi, (
        f"a ballistic sample was above STRATEGIC_Y_BAND high ({hi}): max={ys.max()}"
    )
    # Sanity: every sample is at or above the old ARENA_Y=250k band edge
    # (the whole point of the bump). Old band top was 245 km; new band
    # bottom is 335 km, so every sample must be >= 335 km.
    assert float(ys.min()) >= 335_000.0, (
        f"at least one sample y={ys.min()} is not in the new far-north strip"
    )


def test_hgv_spawn_lands_in_far_north_strip() -> None:
    """Same check for HGV — it shares `STRATEGIC_Y_BAND`."""
    red = RedAI([])
    base_x = config.BLUE_BASE_POS[0]
    base_y = config.BLUE_BASE_POS[1]
    spawns = [
        red._spawn_point(ThreatType.HGV, base_x, base_y)
        for _ in range(100)
    ]
    lo, hi = STRATEGIC_Y_BAND
    ys = np.array([s[1] for s in spawns])
    assert float(ys.min()) >= lo
    assert float(ys.max()) <= hi
    # HGV altitude floor is 30 km (HGV_MIN_Z).
    zs = np.array([s[2] for s in spawns])
    assert float(zs.min()) >= 30_000.0


def test_red_spawn_y_constant_follows_arena() -> None:
    """`RED_SPAWN_Y = ARENA_Y - 5_000` auto-adjusts with the arena
    bump (no hardcoded value)."""
    assert config.RED_SPAWN_Y == config.ARENA_Y - 5_000.0
    assert config.RED_SPAWN_Y == 345_000.0


def main() -> int:
    print("=== ARENA_Y extension regression (Bug 9) ===")
    tests = [
        test_arena_y_is_350km,
        test_strategic_band_is_far_north,
        test_strategic_floor_fits_inside_new_arena,
        test_ballistic_spawn_lands_in_far_north_strip,
        test_hgv_spawn_lands_in_far_north_strip,
        test_red_spawn_y_constant_follows_arena,
    ]
    for fn in tests:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\nAll {len(tests)} arena-extension tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
