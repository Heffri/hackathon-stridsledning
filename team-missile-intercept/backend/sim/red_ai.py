"""Red AI — scripted wave spawner (Level 1 only for Milestone B).

Launches threats at preset times from preset positions. No mid-flight
decision making.
"""
from typing import List

import numpy as np

from . import config
from .types import ThreatType, WaveSpec


def build_demo_waves() -> List[WaveSpec]:
    """3 waves, escalating. Each threat spawns at a distance sized to its
    cruise speed so the engagement fits in a ~3-minute demo. Drones are
    slow (45 m/s) so they spawn closer; cruise missiles spawn farther
    but still within MED_SAM max range * margin.
    """
    base_x = config.BLUE_BASE_POS[0]
    base_y = config.BLUE_BASE_POS[1]

    # Spawn Y for each threat type, chosen so both types arrive at base in
    # similar timescales (~1-2 min from spawn) and stay in launch envelope.
    DRONE_SPAWN_Y = base_y + 15_000.0     # 15 km — in SHORT_SAM range
    CRUISE_SPAWN_Y = base_y + 40_000.0    # 40 km — in MED_SAM range

    def xs(n: int, width: float = 8_000.0):
        if n == 1:
            return [base_x]
        step = width / (n - 1)
        return [base_x - width / 2 + i * step for i in range(n)]

    waves = [
        WaveSpec(
            time=2.0,
            threats=[
                (ThreatType.DRONE, (x, DRONE_SPAWN_Y))
                for x in xs(3, width=6_000.0)
            ],
            label="Wave 1: Drones",
        ),
        WaveSpec(
            time=35.0,
            threats=[
                (ThreatType.CRUISE_SUB, (x, CRUISE_SPAWN_Y))
                for x in xs(2, width=15_000.0)
            ],
            label="Wave 2: Cruise",
        ),
        WaveSpec(
            time=75.0,
            threats=(
                [(ThreatType.DRONE, (x, DRONE_SPAWN_Y)) for x in xs(4, width=12_000.0)]
                + [(ThreatType.CRUISE_SUB, (base_x, CRUISE_SPAWN_Y))]
            ),
            label="Wave 3: Mixed",
        ),
    ]
    return waves


class RedAI:
    def __init__(self, waves: List[WaveSpec]):
        self.waves = sorted(waves, key=lambda w: w.time)
        self._next_wave = 0
        self.log: List[str] = []

    def step(self, t_now: float, world) -> None:
        """Spawn any waves whose time has come."""
        while (
            self._next_wave < len(self.waves)
            and self.waves[self._next_wave].time <= t_now
        ):
            w = self.waves[self._next_wave]
            for (kind, start_xy) in w.threats:
                world.spawn_threat(kind, start_xy, config.BLUE_BASE_POS[:2])
            self.log.append(f"[{t_now:6.1f}s] {w.label} launched ({len(w.threats)} threats)")
            self._next_wave += 1

    @property
    def done(self) -> bool:
        return self._next_wave >= len(self.waves)
