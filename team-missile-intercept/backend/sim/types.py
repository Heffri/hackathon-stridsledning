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
    HGV = "hgv"


class InterceptorType(str, Enum):
    CIWS = "ciws"
    SHORT_SAM = "short_sam"
    MED_SAM = "med_sam"
    LONG_SAM = "long_sam"
    HIT_TO_KILL = "hit_to_kill"


@dataclass
class ThreatSpec:
    kind: ThreatType
    cruise_speed: float      # m/s
    cruise_alt: float        # m AGL
    max_g: float             # g's (not applied in demo — straight-line)
    drag_k: float            # simplified drag coefficient (unitless, tuned)
    kill_radius: float       # hit radius used when something hits this
    color: str               # hex, client render hint
    hp: int = 10             # hull points; 0 = dead
    usd_cost: int = 30_000   # per-unit price, used for cost-exchange logic


@dataclass
class InterceptorSpec:
    kind: InterceptorType
    max_speed: float         # m/s
    max_g: float             # g's (used to cap commanded accel)
    max_range: float         # m (launch envelope)
    drag_k: float            # drag coefficient
    kill_radius: float       # m — bounding radius used by CPA checks
    color: str
    # Damage model (see WEAPON_SPECS.md):
    damage_direct: int = 40       # damage if CPA < radius_direct
    damage_prox: int = 20         # max damage at radius 0, falling quadratically to 0 at radius_prox
    radius_direct: float = 0.5    # direct-hit radius in metres
    radius_prox: float = 8.0      # proximity-fuse radius
    usd_cost: int = 175_000       # cost-exchange reference price


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
        hp=10,
        usd_cost=30_000,
    ),
    ThreatType.CRUISE_SUB: ThreatSpec(
        kind=ThreatType.CRUISE_SUB,
        cruise_speed=260.0,
        cruise_alt=60.0,
        max_g=2.0,
        drag_k=5.0e-6,
        kill_radius=35.0,
        color="#ff5050",
        hp=30,
        usd_cost=1_500_000,
    ),
    # Terminal-phase ballistic missile (Iskander-class, simplified).
    ThreatType.BALLISTIC: ThreatSpec(
        kind=ThreatType.BALLISTIC,
        cruise_speed=1800.0,
        cruise_alt=0.0,
        max_g=3.0,
        drag_k=2.0e-6,
        kill_radius=70.0,
        color="#ff8020",
        hp=80,
        usd_cost=3_000_000,
    ),
    # Hypersonic glide vehicle (Kinzhal/DF-ZF class). Simplified:
    # PN-guided virtual waypoints produce a wide S-curve in the mid-phase,
    # then PN onto the base for the terminal dive.
    # "cruise_alt" is the initial glide altitude.
    ThreatType.HGV: ThreatSpec(
        kind=ThreatType.HGV,
        cruise_speed=1700.0,
        cruise_alt=35_000.0,
        max_g=15.0,
        drag_k=1.5e-6,
        kill_radius=70.0,
        color="#ff4080",
        hp=60,
        usd_cost=10_000_000,
    ),
}

# --- Interceptor specs ---
# kill_radius is the CPA gate used to decide "this tick produced a hit";
# damage is resolved from the CPA distance using (damage_direct, damage_prox,
# radius_direct, radius_prox) per WEAPON_SPECS.md.
INTERCEPTOR_SPECS = {
    # Note on radius_prox vs WEAPON_SPECS.md: real-world warhead fuse radii
    # (5–20 m) are much smaller than typical miss distances from our
    # grid-limited PN implementation (~20–60 m CPA). We scale each
    # radius_prox up so the damage model interacts meaningfully with the
    # guidance error; damage magnitudes are kept at spec, so the visible
    # "needs multiple shots for hardened targets" tension survives.
    # Design: kill_radius is the CPA-gate (roughly sized to typical PN
    # miss distance). radius_prox is the damage-falloff scale — set larger
    # than kill_radius so that even near-edge hits (CPA ≈ kill_radius)
    # still deal a meaningful fraction of damage_prox via the
    # (1 - d/radius_prox)² falloff. Bigger, harder targets need a wider
    # warhead to be reliably lethal; this is where the LONG-SAM/PAC-2's
    # blast-frag pattern advantage shows up.
    InterceptorType.CIWS: InterceptorSpec(
        kind=InterceptorType.CIWS,
        max_speed=1000.0,
        max_g=25.0,
        max_range=4_000.0,
        drag_k=2.0e-5,
        kill_radius=45.0,
        color="#ffd24a",
        damage_direct=15,
        damage_prox=8,
        radius_direct=1.0,
        radius_prox=80.0,
        usd_cost=2_000,
    ),
    InterceptorType.SHORT_SAM: InterceptorSpec(
        kind=InterceptorType.SHORT_SAM,
        max_speed=680.0,
        max_g=20.0,
        max_range=9_000.0,
        drag_k=1.0e-5,
        kill_radius=60.0,
        color="#ffcc33",
        damage_direct=40,
        damage_prox=20,
        radius_direct=1.0,
        radius_prox=120.0,
        usd_cost=175_000,
    ),
    InterceptorType.MED_SAM: InterceptorSpec(
        kind=InterceptorType.MED_SAM,
        max_speed=1020.0,
        max_g=40.0,
        max_range=40_000.0,
        drag_k=6.0e-6,
        kill_radius=75.0,
        color="#fff089",
        damage_direct=50,
        damage_prox=25,
        radius_direct=2.0,
        radius_prox=150.0,
        usd_cost=1_000_000,
    ),
    # Long-range SAM (Patriot PAC-2 class). Mach 5, 70 km, large blast-frag.
    InterceptorType.LONG_SAM: InterceptorSpec(
        kind=InterceptorType.LONG_SAM,
        max_speed=1700.0,
        max_g=25.0,
        max_range=70_000.0,
        drag_k=4.0e-6,
        kill_radius=90.0,
        color="#ffec40",
        damage_direct=80,
        damage_prox=40,
        radius_direct=3.0,
        radius_prox=180.0,
        usd_cost=3_000_000,
    ),
    # Hit-to-kill (PAC-3 MSE). Pure kinetic kill mechanism — 200 dmg on
    # a direct hit, one-shots ballistic / HGV. Our grid-stepped PN only
    # achieves sub-metre CPA rarely, so the direct radius is widened to
    # 25 m (within the fleet average miss). Proximity damage is intention-
    # ally mild (kinetic body, no frag), so a fringe hit (30-60 m miss)
    # still fails — the "sniper" feel survives.
    InterceptorType.HIT_TO_KILL: InterceptorSpec(
        kind=InterceptorType.HIT_TO_KILL,
        max_speed=1700.0,
        max_g=50.0,
        max_range=60_000.0,
        drag_k=4.0e-6,
        kill_radius=60.0,
        color="#ff7a7a",
        damage_direct=200,
        damage_prox=25,
        radius_direct=25.0,
        radius_prox=60.0,
        usd_cost=4_000_000,
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
    hp: int = 0
    hp_max: int = 0

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
            "hp": self.hp,
            "hp_max": self.hp_max,
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
