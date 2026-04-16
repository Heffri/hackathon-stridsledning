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

from . import config
from .types import ThreatType, WaveSpec


# --- Border-line geometry (relative to BLUE_BASE_POS) ---
BORDER_DY = 60_000.0        # 60 km north of base
BORDER_HALF_WIDTH = 30_000.0  # X spans ±30 km around base axis

# --- Per-kind spawn altitude envelopes (m AGL) ---
DRONE_ALT_RANGE = (200.0, 2_000.0)
CRUISE_ALT_RANGE = (50.0, 500.0)
BALLISTIC_ALT_RANGE = (30_000.0, 40_000.0)


def build_demo_waves() -> List[WaveSpec]:
    """5 escalating waves. Threats are emitted symbolically (kind only); the
    actual spawn coordinates are sampled per-launch inside RedAI.step so the
    border distribution is genuinely random per run.
    """
    waves = [
        WaveSpec(
            time=2.0,
            threats=[ThreatType.DRONE] * 3,
            label="Wave 1: Drones",
        ),
        WaveSpec(
            time=35.0,
            threats=[ThreatType.CRUISE_SUB] * 2,
            label="Wave 2: Cruise",
        ),
        WaveSpec(
            time=75.0,
            threats=[ThreatType.DRONE] * 4 + [ThreatType.CRUISE_SUB],
            label="Wave 3: Mixed",
        ),
        WaveSpec(
            time=120.0,
            threats=[ThreatType.BALLISTIC],
            label="Wave 4: Ballistic",
        ),
        WaveSpec(
            time=150.0,
            threats=(
                [ThreatType.BALLISTIC]
                + [ThreatType.DRONE] * 2
                + [ThreatType.CRUISE_SUB]
            ),
            label="Wave 5: High-low mixed",
        ),
    ]
    return waves


def _sample_spawn(kind: ThreatType, rng: np.random.Generator, base_x: float, base_y: float):
    """Pick (x, y, z) on the north border for one threat.

    All threats share the same Y (border line) and X is sampled across the
    full ±30 km width. Z range is per-kind so drones cluster low, cruise
    hugs the deck, and ballistic re-enters from the upper atmosphere.
    """
    x = base_x + float(rng.uniform(-BORDER_HALF_WIDTH, BORDER_HALF_WIDTH))
    y = base_y + BORDER_DY
    if kind == ThreatType.DRONE:
        z = float(rng.uniform(*DRONE_ALT_RANGE))
    elif kind == ThreatType.CRUISE_SUB:
        z = float(rng.uniform(*CRUISE_ALT_RANGE))
    elif kind == ThreatType.BALLISTIC:
        z = float(rng.uniform(*BALLISTIC_ALT_RANGE))
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

        Each WaveSpec.threats is now a list of ThreatType (no coords). For
        every threat we sample a fresh (x, y, z) on the border line, and for
        cruise_sub we additionally generate intermediate waypoints.
        """
        base_x = config.BLUE_BASE_POS[0]
        base_y = config.BLUE_BASE_POS[1]
        target_xy = (base_x, base_y)

        while (
            self._next_wave < len(self.waves)
            and self.waves[self._next_wave].time <= t_now
        ):
            w = self.waves[self._next_wave]
            for kind in w.threats:
                spawn = _sample_spawn(kind, self.rng, base_x, base_y)
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
