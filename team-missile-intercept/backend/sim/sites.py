"""Blue-side Saab locations the Red force can target.

Up to Milestone F the only target was the single base at `BLUE_BASE_POS`.
Milestone G expands the target list to include every south-side named
location from the Saab Boreal Passage map (air bases, capital, major
cities) plus the legacy base. Each site carries its own leak counter
so the HUD can show which Saab assets Red is hurting.

Coordinates are converted from Saab km (CSV + `BOREAL_LOCATIONS` on
the frontend) into world metres using the same affine transform as
scene.js. Importing scene.js into Python is not possible; the 4-line
math is ported here and kept in sync manually.

    scene_x = (saab_x / 1667 - 0.5) * 150          (saabToScene)
    scene_z = -245 + (saab_y - 280) / 800 * 250

    scene_x = (wx - 75_000) / 1_000                (worldToSceneXY)
    scene_z = -(wy - 5_000) / 1_000

Solving for (wx, wy):

    wx = 75_000 + (saab_x / 1667 - 0.5) * 150_000
    wy =  5_000 + (245 - (saab_y - 280) / 3.2) * 1_000

The base at (75_000, 5_000) maps to Saab (833.5, 1064) — the Milestone
E acceptance anchor. Some southern locations (Southern Redoubt,
Meridia, Callhaven, Solano) sit at Saab Y > 1080 and therefore land at
world_y < 0 — south of the nominal arena. Milestone H Part 2 filters
those out at module load so threats don't chase phantom targets past
the base. A one-line notice is printed listing the dropped sites.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

from . import config


def _saab_to_world(saab_x_km: float, saab_y_km: float) -> Tuple[float, float]:
    """Inverse of the frontend scene.js transform — see module docstring."""
    wx = 75_000.0 + (saab_x_km / 1667.0 - 0.5) * 150_000.0
    wy = 5_000.0 + (245.0 - (saab_y_km - 280.0) / 3.2) * 1_000.0
    return wx, wy


@dataclass
class Site:
    """One Red-targetable location on the Blue side of the strait."""

    name: str
    subtype: str                    # 'air_base' | 'capital' | 'major_city' | 'base'
    pos: Tuple[float, float]         # world (x, y) metres
    hp: int = config.SITE_HP_START   # Milestone I: decremented per-leak
    hp_max: int = config.SITE_HP_START
    leaks: int = 0                   # threats that crossed hit radius


# Saab CSV south-side named locations. Order matters only for stable
# iteration (HUD sort / site-colour mapping). Keep alphabetised inside
# each subtype for ease of reading.
_SAAB_SOUTH_LOCATIONS: List[Tuple[str, str, float, float]] = [
    ("Firewatch Station",   "air_base",   1398.3, 1071.7),
    ("Meridia (Capital Y)", "capital",    1225.0, 1208.3),
    ("Southern Redoubt",    "air_base",    321.7, 1238.3),
    ("Spear Point Base",    "air_base",    918.3,  835.0),
    ("Callhaven",           "major_city",   96.7, 1150.0),
    ("Solano",              "major_city",  576.7, 1236.7),
]


def _in_arena(wx: float, wy: float) -> bool:
    """True iff world-coord `(wx, wy)` is physically inside the rendered
    arena (0 ≤ y ≤ ARENA_Y AND 0 ≤ x ≤ ARENA_X). Milestone H Part 2:
    the Saab CSV south-side named locations include several at
    `saab_y > 1080` which fall outside the 280..1080 Y-crop window the
    scene renders; their inverse-affine produces `world_y < 0`. Threats
    targeting those phantom sites fly past the base southward forever.
    """
    return 0.0 <= wy <= config.ARENA_Y and 0.0 <= wx <= config.ARENA_X


def _build_south_sites() -> List[Site]:
    sites: List[Site] = []
    dropped: List[str] = []
    for name, subtype, sx, sy in _SAAB_SOUTH_LOCATIONS:
        wx, wy = _saab_to_world(sx, sy)
        if not _in_arena(wx, wy):
            dropped.append(
                f"{name} (saab=({sx:.1f},{sy:.1f}) world=({wx:.0f},{wy:.0f}))"
            )
            continue
        sites.append(Site(name=name, subtype=subtype, pos=(wx, wy)))
    # Legacy base — retained as a site (subtype 'base') so the previous
    # leak geometry still has a named target in the list and weighted-
    # random target selection can still pick it.
    bx, by = config.BLUE_BASE_POS[0], config.BLUE_BASE_POS[1]
    sites.append(Site(name="Main Base", subtype="base", pos=(bx, by)))
    if dropped:
        # One-line module-load notice so future placements or CSV
        # additions are visibly filtered. Not a warning — the filter is
        # the intended behaviour for the 150×250 km arena crop.
        print(
            f"[sites] dropped {len(dropped)} out-of-arena Saab site(s): "
            + "; ".join(dropped)
        )
    return sites


SOUTH_SITES: List[Site] = _build_south_sites()


def reset_leaks() -> None:
    """Zero every site's leak counter AND restore full HP. Called by
    Scenario at construction so a fresh run starts with a clean HUD
    and no damage carried over from the previous match."""
    for s in SOUTH_SITES:
        s.leaks = 0
        s.hp = config.SITE_HP_START
        s.hp_max = config.SITE_HP_START
