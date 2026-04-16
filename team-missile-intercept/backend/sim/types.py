"""Dataclasses, enums, weapon spec tables.

Kept small for Milestone B: no HP, no fuel timer (interceptors self-destruct
on timeout instead), no magazine.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple

import numpy as np


class Team(str, Enum):
    RED = "red"
    BLUE = "blue"


class ThreatType(str, Enum):
    DRONE = "drone"
    CRUISE_SUB = "cruise_sub"
    BALLISTIC = "ballistic"


class InterceptorType(str, Enum):
    CIWS = "ciws"
    SHORT_SAM = "short_sam"
    MED_SAM = "med_sam"
    LONG_SAM = "long_sam"


@dataclass
class ThreatSpec:
    kind: ThreatType
    cruise_speed: float      # m/s
    cruise_alt: float        # m AGL
    max_g: float             # g's (not applied in demo — straight-line)
    drag_k: float            # simplified drag coefficient (unitless, tuned)
    kill_radius: float       # hit radius used when something hits this
    color: str               # hex, client render hint


@dataclass
class InterceptorSpec:
    kind: InterceptorType
    max_speed: float         # m/s
    max_g: float             # g's (used to cap commanded accel)
    max_range: float         # m (launch envelope)
    drag_k: float            # drag coefficient
    kill_radius: float       # m
    color: str


# --- Threat specs ---
THREAT_SPECS = {
    ThreatType.DRONE: ThreatSpec(
        kind=ThreatType.DRONE,
        cruise_speed=120.0,
        cruise_alt=800.0,
        max_g=2.0,
        drag_k=1.0e-5,
        kill_radius=30.0,
        color="#ff3040",
    ),
    ThreatType.CRUISE_SUB: ThreatSpec(
        kind=ThreatType.CRUISE_SUB,
        cruise_speed=260.0,
        cruise_alt=60.0,
        max_g=2.0,
        drag_k=5.0e-6,
        kill_radius=35.0,
        color="#ff5050",
    ),
    # Terminal-phase ballistic missile (Iskander-class, simplified).
    # cruise_speed here = initial re-entry/terminal speed; cruise_alt is
    # unused (gravity + initial downward velocity drive the trajectory).
    ThreatType.BALLISTIC: ThreatSpec(
        kind=ThreatType.BALLISTIC,
        cruise_speed=1800.0,
        cruise_alt=0.0,
        max_g=3.0,
        drag_k=2.0e-6,
        kill_radius=70.0,
        color="#ff8020",
    ),
}

# --- Interceptor specs ---
INTERCEPTOR_SPECS = {
    InterceptorType.CIWS: InterceptorSpec(
        kind=InterceptorType.CIWS,
        max_speed=1000.0,
        max_g=25.0,
        max_range=4_000.0,
        drag_k=2.0e-5,
        kill_radius=45.0,
        color="#ffd24a",
    ),
    InterceptorType.SHORT_SAM: InterceptorSpec(
        kind=InterceptorType.SHORT_SAM,
        max_speed=680.0,
        max_g=20.0,
        max_range=9_000.0,
        drag_k=1.0e-5,
        kill_radius=60.0,
        color="#ffcc33",
    ),
    InterceptorType.MED_SAM: InterceptorSpec(
        kind=InterceptorType.MED_SAM,
        max_speed=1020.0,
        max_g=40.0,
        max_range=40_000.0,
        drag_k=6.0e-6,
        kill_radius=75.0,
        color="#fff089",
    ),
    # Long-range SAM (Patriot PAC-2 class). Mach 5, 70 km, large blast-frag.
    # Only interceptor cleared to engage ballistic threats.
    InterceptorType.LONG_SAM: InterceptorSpec(
        kind=InterceptorType.LONG_SAM,
        max_speed=1700.0,
        max_g=25.0,
        max_range=70_000.0,
        drag_k=4.0e-6,
        kill_radius=90.0,
        color="#ffec40",
    ),
}


@dataclass
class EntityState:
    """Minimal render/sim state for any projectile."""
    id: int
    team: Team
    kind: str
    pos: np.ndarray           # shape (3,)
    vel: np.ndarray           # shape (3,)
    alive: bool = True
    target_id: Optional[int] = None
    spawn_t: float = 0.0
    color: str = "#ffffff"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "team": self.team.value,
            "kind": self.kind,
            "pos": [float(self.pos[0]), float(self.pos[1]), float(self.pos[2])],
            "vel": [float(self.vel[0]), float(self.vel[1]), float(self.vel[2])],
            "alive": self.alive,
            "target_id": self.target_id,
            "spawn_t": self.spawn_t,
            "color": self.color,
        }


@dataclass
class Explosion:
    pos: np.ndarray
    t: float
    lifetime: float = 1.0

    def to_dict(self) -> dict:
        return {
            "pos": [float(self.pos[0]), float(self.pos[1]), float(self.pos[2])],
            "t": self.t,
            "lifetime": self.lifetime,
        }


@dataclass
class WaveSpec:
    time: float                           # sim seconds when wave launches
    threats: list                          # list[tuple[ThreatType, start_xy]]
    label: str = ""
