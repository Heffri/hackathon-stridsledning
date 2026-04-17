"""Red AI — scripted wave spawner with randomised border-line spawning.

Every wave spawns its threats from a single fixed "border" line ~60 km north
of the defended base. Per-spawn X is randomised across the full border
width and Z is randomised within an envelope tuned to each threat type.
Cruise missiles additionally receive 1-2 intermediate waypoints to fly an
S-shape instead of a straight line. Random samples are drawn at spawn time
inside RedAI.step (not at module import) so every demo run looks different.
"""
from typing import List

import numpy as np

from . import config, sites
from .types import ThreatType, WaveSpec


# --- Target selection weights (Milestone G) ---
# Red AI picks a target site per threat via weighted random choice.
# Capital > base > air_base > major_city, modelling Red's preference
# for maximum strategic damage. A future "Smart Red AI" could pattern
# weights per wave (wave 5 saturates the capital, wave 1 goes for an
# airbase, etc.) — currently every threat rolls independently.
_TARGET_WEIGHTS = {
    "capital":    4.0,
    "base":       3.0,
    "air_base":   2.0,
    "major_city": 1.0,
}


def _pick_target(rng: np.random.Generator) -> tuple:
    """Return (x, y) in world metres for a weighted-random site. Falls
    back to the legacy base if the site list is somehow empty."""
    site_list = sites.SOUTH_SITES
    if not site_list:
        return (config.BLUE_BASE_POS[0], config.BLUE_BASE_POS[1])
    w = np.array(
        [_TARGET_WEIGHTS.get(s.subtype, 1.0) for s in site_list],
        dtype=np.float64,
    )
    w /= w.sum()
    idx = int(rng.choice(len(site_list), p=w))
    return site_list[idx].pos


# --- Border-line geometry (Milestone G: relative to STRAIT_CENTER_Y) ---
# Pre-G these were offsets from the base (5 km south), which put drones
# at y = 35_000 — visibly INSIDE Blue's own southern mainland — and
# made every spawn look narratively absurd. Milestone G anchors spawn
# Y to the strait centerline instead, so every threat starts physically
# north of the water. Offsets below are "distance NORTH of strait
# centre" (positive = deeper into Red territory).
STRAIT_OFFSET_DRONE     = 10_000   # just over the strait, close-in attack
STRAIT_OFFSET_CRUISE    = 25_000   # further back — cruise is faster
STRAIT_OFFSET_BALLISTIC = 50_000   # deep Red territory
STRAIT_OFFSET_HGV       = 70_000   # deepest — 70 km buffer back from HGV line
# Resulting spawn Y values with STRAIT_CENTER_Y = 120_000:
#   drone 130 km, cruise 145 km, ballistic 170 km, HGV 190 km
# All still inside the 250 km arena (HGV keeps ~60 km buffer).
BORDER_HALF_WIDTH = 30_000.0    # X spans ±30 km around base axis

# --- Per-kind spawn altitude envelopes (m AGL) ---
# Three visual tiers on the 150 km × 150 km arena:
#   - high  (25–40 km): ballistic re-entry, HGV cruise
#   - mid   ( 1– 6 km): subsonic cruise with pop-up at terminal
#   - low   (0.5–4 km): drones
# Cruise is deliberately set above drones so operators can tell the "mid"
# band from the "low" band at a glance during the demo.
DRONE_ALT_RANGE = (500.0, 4_000.0)
CRUISE_ALT_RANGE = (1_000.0, 6_000.0)
BALLISTIC_ALT_RANGE = (30_000.0, 40_000.0)
HGV_ALT_RANGE = (30_000.0, 40_000.0)


def build_demo_waves() -> List[WaveSpec]:
    """5 escalating waves tuned so Blue is not guaranteed to hold —
    wave 5's saturation attack regularly gets at least 1 threat through.
    """
    # Cruise count doubled (4 → 8) and ballistic count doubled (2 → 4)
    # per the "more volume" brief. Drones still spawn from 30 km so
    # SHORT_SAM / CIWS actually engage them.
    waves = [
        WaveSpec(
            time=2.0,
            threats=[ThreatType.DRONE] * 3,
            label="Wave 1: Drones",
        ),
        WaveSpec(
            time=25.0,
            threats=[ThreatType.DRONE] * 3 + [ThreatType.CRUISE_SUB] * 2,
            label="Wave 2: Drones + cruise",
        ),
        WaveSpec(
            time=55.0,
            threats=[ThreatType.CRUISE_SUB] * 4 + [ThreatType.BALLISTIC] * 2,
            label="Wave 3: Cruise + ballistic",
        ),
        WaveSpec(
            time=95.0,
            threats=[ThreatType.HGV] + [ThreatType.DRONE] * 2,
            label="Wave 4: HGV + drones",
        ),
        WaveSpec(
            time=145.0,
            threats=(
                [ThreatType.BALLISTIC] * 2
                + [ThreatType.HGV] * 2
                + [ThreatType.DRONE] * 3
                + [ThreatType.CRUISE_SUB] * 2
            ),
            label="Wave 5: Saturation attack",
        ),
    ]
    return waves


def _sample_spawn(kind: ThreatType, rng: np.random.Generator, base_x: float, base_y: float):
    """Pick (x, y, z) north of the strait centerline for one threat.

    All threats' Y is anchored to `config.STRAIT_CENTER_Y` plus a per-
    kind offset (positive = deeper into Red territory). X is sampled
    ±30 km around the base X axis. Z is per-kind so drones cluster low
    over the northern land / strait, cruise hugs the deck, and
    ballistic / HGV re-enter from the upper atmosphere.

    `base_y` is retained in the signature for API compatibility but is
    no longer used for the Y anchor (kept to avoid cascading scenario
    changes).
    """
    x = base_x + float(rng.uniform(-BORDER_HALF_WIDTH, BORDER_HALF_WIDTH))
    # Per-kind distance NORTH of the strait centerline (see constants).
    if kind == ThreatType.HGV:
        y = config.STRAIT_CENTER_Y + STRAIT_OFFSET_HGV       # 190 km
    elif kind == ThreatType.BALLISTIC:
        y = config.STRAIT_CENTER_Y + STRAIT_OFFSET_BALLISTIC # 170 km
    elif kind == ThreatType.DRONE:
        y = config.STRAIT_CENTER_Y + STRAIT_OFFSET_DRONE     # 130 km
    else:
        y = config.STRAIT_CENTER_Y + STRAIT_OFFSET_CRUISE    # 145 km (cruise)
    if kind == ThreatType.DRONE:
        z = float(rng.uniform(*DRONE_ALT_RANGE))
    elif kind == ThreatType.CRUISE_SUB:
        z = float(rng.uniform(*CRUISE_ALT_RANGE))
    elif kind == ThreatType.BALLISTIC:
        z = float(rng.uniform(*BALLISTIC_ALT_RANGE))
    elif kind == ThreatType.HGV:
        z = float(rng.uniform(*HGV_ALT_RANGE))
    else:
        z = 0.0
    return (x, y, z)


def _build_cruise_waypoints(
    spawn_xyz, target_xy, rng: np.random.Generator
) -> List[tuple]:
    """Generate 1-2 intermediate waypoints for an S-shaped cruise route.

    Each intermediate point sits along the spawn→target line at a randomly
    chosen progress fraction with a lateral offset of 5-20 km. With two
    waypoints the offsets alternate sign so the path actually weaves.
    """
    sx, sy, sz = spawn_xyz
    tx, ty = target_xy
    # 1 or 2 intermediate waypoints (50/50)
    n = int(rng.integers(1, 3))
    progress = sorted(float(rng.uniform(0.30, 0.70)) for _ in range(n))
    # Random side first, alternating after to weave.
    side = 1.0 if rng.random() < 0.5 else -1.0
    wps: List[tuple] = []
    for i, p in enumerate(progress):
        # base point on the straight line to target
        bx = sx + (tx - sx) * p
        by = sy + (ty - sy) * p
        offset_mag = float(rng.uniform(5_000.0, 20_000.0))
        # Lateral offset direction = perpendicular to the straight line
        # (in XY plane). For a near-southward route this is mostly along X.
        dx = tx - sx
        dy = ty - sy
        norm = float(np.sqrt(dx * dx + dy * dy)) or 1.0
        # Perp(dx,dy) = (-dy, dx)
        px = -dy / norm
        py = dx / norm
        s = side * (1.0 if i % 2 == 0 else -1.0)
        wx = bx + px * offset_mag * s
        wy = by + py * offset_mag * s
        wps.append((wx, wy, sz))
    return wps


class RedAI:
    def __init__(self, waves: List[WaveSpec]):
        self.waves = sorted(waves, key=lambda w: w.time)
        self._next_wave = 0
        self.log: List[str] = []
        # Fresh entropy per RedAI instance — every Reset / restart reshuffles.
        self.rng = np.random.default_rng()

    def step(self, t_now: float, world) -> None:
        """Spawn any waves whose time has come.

        Each WaveSpec.threats is a list of ThreatType (no coords). For
        every threat we sample a fresh (x, y, z) north of the strait,
        pick a weighted-random target site (Milestone G), and for
        cruise_sub additionally generate intermediate waypoints toward
        *that* site (not the base).
        """
        base_x = config.BLUE_BASE_POS[0]
        base_y = config.BLUE_BASE_POS[1]

        while (
            self._next_wave < len(self.waves)
            and self.waves[self._next_wave].time <= t_now
        ):
            w = self.waves[self._next_wave]
            for kind in w.threats:
                spawn = _sample_spawn(kind, self.rng, base_x, base_y)
                target_xy = _pick_target(self.rng)
                if kind == ThreatType.CRUISE_SUB:
                    wps = _build_cruise_waypoints(spawn, target_xy, self.rng)
                    world.spawn_threat(
                        kind, spawn, target_xy, intermediate_waypoints=wps
                    )
                else:
                    world.spawn_threat(kind, spawn, target_xy)
            self.log.append(
                f"[{t_now:6.1f}s] {w.label} launched ({len(w.threats)} threats)"
            )
            self._next_wave += 1

    @property
    def done(self) -> bool:
        return self._next_wave >= len(self.waves)
