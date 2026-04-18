"""Land-mask helper — check whether a world-coord (x, y) sits on the
southern mainland / islands in Saab's Boreal Passage scenario.

Used by config.py at module load to assert every `BLUE_LAUNCHER_POSITIONS`
entry lands on visible land rather than in a coastal-pocket sea. A
future placement AI can call `point_on_south_land` directly.

Coordinate systems
------------------
- **Saab**: (x_km, y_km). X east-positive (0..1667). Y *south-positive*
  (0..1300, north coast ≈ 280, south coast ≈ 1080 in the rendered crop).
  The CSV polygons live in this space.
- **World**: (wx, wy) in metres. X east, Y north (base at (75_000, 5_000)).
- **Scene** (frontend only, not used here): see scene.js.

The inverse transform `_world_to_saab` mirrors scene.js's
`worldToSceneXY ∘ saabToScene⁻¹`. Derivation kept in the docstring so
future edits can sanity-check it:

    scene_x = (wx - 75_000) / 1_000                (from worldToSceneXY)
    scene_z = -(wy - 5_000)  / 1_000
    scene_x = (saab_x / 1667 - 0.5) * 150          (from saabToScene)
    scene_z = -245 + (saab_y - 280) / 800 * 250

Solving:

    saab_x = 1667 * ((wx - 75_000) / 150_000 + 0.5)
    saab_y = 1064 - 0.0032 * (wy - 5_000)
"""
from __future__ import annotations

import ast
import csv
import os
from typing import List, Tuple

# Path resolution: this file lives at backend/sim/terrain.py. The CSV is
# copied into the active project's canonical source-data home under
# team-missile-intercept/common-info/source-data/... relative to the repo
# root so the runtime no longer depends on the archived legacy tree.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", "..", ".."))
_CSV_PATH = os.path.join(
    _REPO_ROOT,
    "team-missile-intercept",
    "common-info",
    "source-data",
    "saab-provided",
    "Boreal_passage_coordinates.csv",
)


def _parse_polygons(side: str) -> List[Tuple[str, List[Tuple[float, float]]]]:
    """Parse the Saab CSV, return [(subtype, [(x, y), ...]), ...] for
    every terrain polygon on the given `side` ('south' or 'north').
    `ast.literal_eval` handles the `[[x, y], [x, y], ...]` coordinate-
    list encoding safely.
    """
    polys: List[Tuple[str, List[Tuple[float, float]]]] = []
    with open(_CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["record_type"] != "terrain":
                continue
            if row["side"] != side:
                continue
            raw = row["coordinates_km"].strip()
            if not raw:
                continue
            pts = ast.literal_eval(raw)
            polys.append((row["subtype"], [(float(x), float(y)) for x, y in pts]))
    return polys


_SOUTH_POLYGONS: List[Tuple[str, List[Tuple[float, float]]]] = _parse_polygons("south")
_NORTH_POLYGONS: List[Tuple[str, List[Tuple[float, float]]]] = _parse_polygons("north")


def _world_to_saab(wx: float, wy: float) -> Tuple[float, float]:
    """World (m) → Saab (km). See module docstring for derivation."""
    saab_x = 1667.0 * ((wx - 75_000.0) / 150_000.0 + 0.5)
    saab_y = 1064.0 - 0.0032 * (wy - 5_000.0)
    return saab_x, saab_y


def _point_in_polygon(px: float, py: float, poly: List[Tuple[float, float]]) -> bool:
    """Standard ray-casting point-in-polygon (even/odd rule). Handles
    non-convex polygons such as the indented south_mainland coastline.
    """
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        intersects = ((yi > py) != (yj > py)) and (
            px < (xj - xi) * (py - yi) / (yj - yi) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def point_on_south_land(wx: float, wy: float) -> bool:
    """True if world-coord (wx, wy) falls inside any south-side land
    polygon from the Saab CSV. Used by config.py to validate
    `BLUE_LAUNCHER_POSITIONS`.
    """
    sx, sy = _world_to_saab(wx, wy)
    for _subtype, poly in _SOUTH_POLYGONS:
        if _point_in_polygon(sx, sy, poly):
            return True
    return False


def point_on_north_land(wx: float, wy: float) -> bool:
    """True if world-coord (wx, wy) falls inside any north-side land
    polygon from the Saab CSV. Milestone H Part 3: used to validate
    `RED_LAUNCHER_POSITIONS` so visible Red drone / cruise launcher
    boxes sit on north mainland / islands, not in the strait.
    """
    sx, sy = _world_to_saab(wx, wy)
    for _subtype, poly in _NORTH_POLYGONS:
        if _point_in_polygon(sx, sy, poly):
            return True
    return False
