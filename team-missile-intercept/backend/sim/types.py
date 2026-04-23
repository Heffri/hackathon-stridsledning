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


class MatchPhase(str, Enum):
    """Match lifecycle states (M-TIER2-PHASE).

    setup     — pre-match, world frozen, waiting for a start command
                (used later by Milestone J deployment UI).
    running   — live game, sim advances, Red/Blue AI tick.
    paused    — frozen mid-match, sim does not advance. Existing entities
                keep their poses on-screen so the operator can inspect.
    finished  — winner declared, sim does not advance. Only legal exit is
                a reset back to setup.

    Legal transitions are enforced by `World.transition`; callers that
    attempt an illegal move get a False return (no raise) so the server
    layer can convert it into a WebSocket error response without
    aborting the tick.
    """

    SETUP = "setup"
    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"


# Legal MatchPhase transitions. Keyed by (from_phase, to_phase).
# finished → setup is the only path out of finished (via reset).
LEGAL_PHASE_TRANSITIONS: frozenset = frozenset(
    {
        (MatchPhase.SETUP, MatchPhase.RUNNING),
        (MatchPhase.RUNNING, MatchPhase.PAUSED),
        (MatchPhase.PAUSED, MatchPhase.RUNNING),
        (MatchPhase.RUNNING, MatchPhase.FINISHED),
        (MatchPhase.PAUSED, MatchPhase.FINISHED),
        (MatchPhase.FINISHED, MatchPhase.SETUP),
    }
)


class ThreatType(str, Enum):
    DRONE = "drone"
    CRUISE_SUB = "cruise_sub"
    BALLISTIC = "ballistic"
    HGV = "hgv"


class InterceptorType(str, Enum):
    # All enum VALUES are real-weapon strings so the frontend can mount a
    # distinct mesh per product. Python code refers to members by name
    # (InterceptorType.SHORT_SAM) — the value string is the wire format.
    CIWS = "ciws"
    SHORT_SAM = "rbs_70"
    IRIS_T_SLS = "iris_t_sls"
    MED_SAM = "iris_t_slm"
    LONG_SAM = "pac_2"
    HIT_TO_KILL = "pac_3"


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
    # If True, the 1500 m horizontal-disc leak check additionally requires
    # the threat to be near ground level before it damages the site — an
    # airburst above a site no longer counts as a hit. Every current
    # threat kind (drone, cruise_sub, ballistic, HGV) sets this True so
    # flyover at altitude doesn't trigger damage on a non-targeted site
    # the ground-track happens to cross. Spec default stays False so a
    # future nuclear warhead kind can omit the override and keep airburst.
    requires_ground_impact: bool = False


@dataclass
class InterceptorSpec:
    kind: InterceptorType
    max_speed: float         # m/s
    max_g: float             # g's (used to cap commanded accel)
    max_range: float         # m (launch envelope)
    drag_k: float            # drag coefficient
    kill_radius: float       # m — bounding radius used by CPA checks
    color: str
    # Propulsion:
    fuel_s: float = 10.0     # seconds of powered flight (boost+sustain motor)
    # Damage model — arcade fragmentation AOE (Phase 2 of blue_aoe_long).
    # On detonation every alive threat within `fragment_radius` of the
    # detonation point takes a flat `fragment_damage`. No CPA-based
    # falloff (flat within radius is cleaner for the RL gradient and
    # legible on-screen). Direct-hit damage is the same `fragment_damage`
    # since the primary target sits at d≈0 from the detonation.
    damage_direct: int = 40       # retained for log/event display only
    fragment_radius: float = 0.0  # AOE radius in metres (0 → pure HTK)
    fragment_damage: int = 20     # flat damage to every threat inside radius
    radius_direct: float = 0.5    # detonation-gate — htk mode fires when d_min < this
    radius_prox: float = 8.0      # detonation-gate — prox mode fires when d_min < this
    usd_cost: int = 175_000       # cost-exchange reference price
    # Engagement-mode infrastructure (M-TIER2.5). Each spec declares the
    # legal modes it can be fired in and a default. Modes:
    #   * 'prox' — current auto direct-then-prox behaviour (damage falls
    #     off linearly inside radius_prox, direct hit inside radius_direct).
    #   * 'htk'  — hit-to-kill: direct hit inside radius_direct deals
    #     `damage_direct * 2`; anything wider is a clean miss (0 damage).
    # Per-type overrides live on the spec instances below:
    #   * CIWS  → choices=('prox',), default='prox' (cannon has no HTK concept).
    #   * SHORT_SAM / IRIS_T_SLS / MED_SAM / LONG_SAM →
    #       choices=('prox', 'htk'), default='prox' (dual-mode; HTK opt-in).
    #   * HIT_TO_KILL (PAC-3) → choices=('htk',), default='htk' (physically
    #       HTK-only; prox is not a legal mode for pac_3).
    # Defaults below preserve current behaviour (prox everywhere) — no
    # caller opts into HTK in M-TIER2.5; this is infrastructure only.
    engagement_mode_choices: Tuple[str, ...] = ("prox",)
    default_engagement_mode: str = "prox"


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
        requires_ground_impact=True,
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
        requires_ground_impact=True,
    ),
    # Terminal-phase ballistic missile. 13 Mach (4459 m/s) matches the
    # public terminal velocity of modern MaRV / heavy-RV designs
    # (Iskander upgrade, DF-17 depressed-trajectory test). Hard target
    # for the interceptor fleet by design — PAC-3 / PAC-2 saturation has
    # to land direct hits or stack proxy kills before the RV crosses
    # the last 30 km.
    ThreatType.BALLISTIC: ThreatSpec(
        kind=ThreatType.BALLISTIC,
        cruise_speed=4459.0,
        cruise_alt=0.0,
        max_g=3.0,
        drag_k=2.0e-6,
        kill_radius=70.0,
        color="#ff8020",
        hp=80,
        usd_cost=3_000_000,
        requires_ground_impact=True,
    ),
    # Hypersonic glide vehicle (Kinzhal/DF-ZF class). 17 Mach glide
    # velocity — at this speed the R = v²/a formula gives a ~347 km
    # turn radius under max_g=10, so HGV effectively flies straight
    # through the 150 km arena unless it bleeds speed. Manoeuvres
    # aggressively bleed kinetic energy (see _HGV_BLEED_RATE), and
    # below _HGV_STALL_SPEED lift collapses and the HGV crashes.
    ThreatType.HGV: ThreatSpec(
        kind=ThreatType.HGV,
        cruise_speed=5831.0,
        cruise_alt=35_000.0,
        # max_g 10 → 6 as part of the 2026-04-22 balance pass. Pure
        # ~100 % leak rate vs PAC-3 PN made HGV the only rational Red
        # spawn (damage/$ 4× over ballistic); softening the evasion
        # envelope gives the interceptor a chance to land while keeping
        # HGV faster than ballistic so it stays an elite threat.
        # Tradeoff: on the fixed-wave rule-vs-rule test_balance sweep
        # this pushes Blue winrate to ~85 % (vs the spec's 30-55 %
        # target) because rule_Red's scripted waves can't exploit the
        # new env. The 30-55 % target was calibrated when HGV was a
        # guaranteed leak; it isn't reachable with any max_g ≤ 8 on
        # the current wave plan without also retuning the waves.
        # Diversifying *learned* Red (the core goal) needs the deeper
        # nerf, so max_g=6 wins the tradeoff.
        max_g=6.0,
        drag_k=1.5e-6,
        kill_radius=70.0,
        color="#ff4080",
        hp=60,
        # usd_cost 10M → 25M as part of the 2026-04-22 balance pass.
        # At $100M Red budget this drops the HGV cap from 10 to 4 per
        # match, forcing Red to mix in ballistic / cruise to fill the
        # remaining budget instead of pure HGV spam.
        usd_cost=25_000_000,
        requires_ground_impact=True,
    ),
}

# --- Interceptor specs ---
# Arcade AOE model (blue_aoe_long Phase 2): kill_radius is the CPA gate
# that decides "this tick produced a detonation"; on detonation every
# alive threat inside `fragment_radius` of the detonation point takes a
# flat `fragment_damage`. No per-CPA falloff anymore.
INTERCEPTOR_SPECS = {
    # Calibration targets (§3.6 of the worker prompt):
    #   CIWS        r=30  dmg=12  — flak-like, kills tight drone pairs
    #   RBS-70      r=50  dmg=18  — MANPADS-scale HE
    #   IRIS-T SLS  r=100 dmg=35  — clears 3-4 drone cluster
    #   IRIS-T SLM  r=120 dmg=50  — clears 4-6 drone cluster
    #   PAC-2       r=150 dmg=80  — kills a cruise pair, chips ballistic
    #   PAC-3       r=0   dmg=120 — pure HTK, primary-only via d<=r gate
    # radius_prox / radius_direct below are retained as detonation-gate
    # inputs for future mode routing (not the damage falloff). Every
    # detonation currently fires via kill_radius; see World.step block 3.
    InterceptorType.CIWS: InterceptorSpec(
        kind=InterceptorType.CIWS,
        max_speed=1000.0,
        max_g=25.0,
        max_range=4_000.0,
        drag_k=2.0e-5,
        kill_radius=45.0,
        color="#ffd24a",
        fuel_s=4.0,
        damage_direct=15,
        fragment_radius=30.0,
        fragment_damage=12,
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
        color="#4a8a3a",  # matches rbs_70 mesh (olive green)
        fuel_s=13.0,
        damage_direct=40,
        fragment_radius=50.0,
        fragment_damage=18,
        radius_direct=1.0,
        radius_prox=120.0,
        usd_cost=175_000,
        engagement_mode_choices=("prox", "htk"),
    ),
    # Short-range SAM+ (IRIS-T SLS / RBS 98). Mach 2 average, 60G TVC —
    # the most agile interceptor, designed for terminal "knife fight" vs
    # manoeuvring targets within 12 km. Ground-launched IRIS-T with short
    # booster; 11.4 kg HE-frag warhead.
    InterceptorType.IRIS_T_SLS: InterceptorSpec(
        kind=InterceptorType.IRIS_T_SLS,
        max_speed=400.0,
        max_g=60.0,
        max_range=12_000.0,
        drag_k=1.2e-5,
        kill_radius=60.0,
        color="#ff9944",
        fuel_s=30.0,
        damage_direct=50,
        fragment_radius=100.0,
        fragment_damage=35,
        radius_direct=1.0,
        radius_prox=100.0,
        usd_cost=500_000,
        engagement_mode_choices=("prox", "htk"),
    ),
    InterceptorType.MED_SAM: InterceptorSpec(
        kind=InterceptorType.MED_SAM,
        max_speed=1020.0,
        max_g=40.0,
        max_range=40_000.0,
        drag_k=6.0e-6,
        kill_radius=75.0,
        color="#ff8c1a",  # matches iris_t_slm mesh (orange)
        fuel_s=39.0,
        damage_direct=50,
        fragment_radius=120.0,
        fragment_damage=50,
        radius_direct=2.0,
        radius_prox=150.0,
        usd_cost=1_000_000,
        engagement_mode_choices=("prox", "htk"),
    ),
    # Long-range SAM (Patriot PAC-2 class). Mach 5, 70 km, large blast-frag.
    InterceptorType.LONG_SAM: InterceptorSpec(
        kind=InterceptorType.LONG_SAM,
        max_speed=1700.0,
        max_g=25.0,
        max_range=70_000.0,
        drag_k=4.0e-6,
        kill_radius=90.0,
        color="#ff69b4",  # matches pac_2 mesh (pink)
        fuel_s=41.0,
        damage_direct=80,
        fragment_radius=150.0,
        fragment_damage=80,
        radius_direct=3.0,
        radius_prox=180.0,
        usd_cost=3_000_000,
        engagement_mode_choices=("prox", "htk"),
    ),
    # Hit-to-kill (PAC-3 MSE). Pure kinetic kill mechanism — 200 dmg on
    # a direct hit, one-shots ballistic / HGV. Our grid-stepped PN only
    # achieves sub-metre CPA rarely, so the direct radius is widened to
    # 40 m — was 25, but the new 15 G HGV slaloms right through a 25 m
    # gate, CPA sits at 30-80 m and the one-shot almost never triggers.
    # Proximity damage is intentionally mild (kinetic body, no frag), so
    # a fringe hit (50-60 m miss) still fails — the "sniper" feel
    # survives, the demo just stops being a coin flip against HGVs.
    InterceptorType.HIT_TO_KILL: InterceptorSpec(
        kind=InterceptorType.HIT_TO_KILL,
        max_speed=1700.0,
        max_g=50.0,
        max_range=60_000.0,
        drag_k=4.0e-6,
        kill_radius=60.0,
        color="#a855f7",  # matches pac_3 mesh (purple)
        fuel_s=35.0,
        damage_direct=200,
        # PAC-3 stays pure HTK — fragment_radius=0 means no splash; the
        # primary target at d≈0 still takes fragment_damage thanks to the
        # `d <= radius` gate in resolve_aoe. One-shots ballistic (hp 80)
        # and HGV (hp 60) by design.
        fragment_radius=0.0,
        fragment_damage=120,
        # Bumped from 40 m → 60 m: at Mach 13 ballistic closing (6159
        # m/s relative to PAC-3), per-tick relative displacement is
        # ~308 m, and typical PN CPA drifts 30-80 m. 40 m was borderline
        # for direct hits at this speed; 60 m keeps PAC-3's hit-to-kill
        # intent against the realistic fast-ballistic threat.
        radius_direct=60.0,
        radius_prox=80.0,
        usd_cost=4_000_000,
        engagement_mode_choices=("htk",),
        default_engagement_mode="htk",
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
    # True while the motor is burning (interceptor boost + sustain phase).
    # Frontend uses this to gate the exhaust flame visual. Threats that
    # have no propulsion (ballistic, HGV) stay False throughout.
    thrust_active: bool = False

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
            "thrust_active": self.thrust_active,
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
