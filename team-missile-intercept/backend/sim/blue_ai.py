"""Blue AI — layered, saturation-style interceptor fire.

Per-threat engagement model:
  * Primary rules list weapons in preference order (cheapest/most
    appropriate first). We fire the first in-range + ready option.
  * Saturation: as the threat closes, cheaper shorter-range weapons come
    into range. We keep firing layered shots while the threat's expected
    in-flight damage is below its remaining HP — so an HGV gets PAC-3,
    then PAC-2 on the way in, then MED-SAM fallback, then IRIS-T SLS as
    it reaches terminal range, and so on. This is the "throw whatever's
    left at it" behaviour the operator asked for.
  * Fallback rules kick in only when no primary option is in-range +
    ready; last-resort shots at HGV / ballistic when PAC-3 / PAC-2 are
    empty or reloading.

The single-assignment lock from the previous revision is gone — a threat
can now have multiple interceptors in flight simultaneously, capped at
MAX_SIMULTANEOUS_PER_THREAT to keep ammo use bounded.
"""
import math
from typing import Dict, List, Optional, Tuple

import numpy as np

from . import config
from .launcher import Launcher, LauncherFleet
from .types import (
    INTERCEPTOR_SPECS,
    InterceptorType,
    THREAT_SPECS,
    ThreatType,
)


# Primary engagement rules, in preference order (first entry tried first).
# DRONE primary stops at SHORT_SAM — MED_SAM is fallback so short-range
# kit actually fires when drones come inside 10 km rather than being
# overkilled by a 40 km SAM while the short-range launcher sits idle.
PRIMARY_RULES: Dict[ThreatType, List[InterceptorType]] = {
    ThreatType.DRONE: [
        InterceptorType.CIWS,
        InterceptorType.SHORT_SAM,
    ],
    ThreatType.CRUISE_SUB: [
        InterceptorType.SHORT_SAM,
        InterceptorType.IRIS_T_SLS,
        InterceptorType.MED_SAM,
    ],
    ThreatType.BALLISTIC: [
        InterceptorType.HIT_TO_KILL,
        InterceptorType.LONG_SAM,
    ],
    ThreatType.HGV: [
        InterceptorType.HIT_TO_KILL,
        InterceptorType.LONG_SAM,
    ],
}

# Fallback rules — tried only when no primary option can engage right now.
# Same list-order semantics; no cost ranking.
# Drones deliberately have NO fallback: spawn at 30 km means they're
# inside MED-SAM envelope immediately, and listing MED-SAM as fallback
# made the AI 25-dmg-overkill a 10-HP drone from 30 km while SHORT_SAM
# and CIWS idled. With no fallback, the AI patiently waits until the
# drone crosses the 10 km SHORT_SAM gate (drone flight takes ~250 s, so
# we have plenty of time to hold fire).
FALLBACK_RULES: Dict[ThreatType, List[InterceptorType]] = {
    ThreatType.HGV: [
        InterceptorType.MED_SAM,
        InterceptorType.IRIS_T_SLS,
        InterceptorType.SHORT_SAM,
        InterceptorType.CIWS,
    ],
    ThreatType.BALLISTIC: [
        InterceptorType.MED_SAM,
        InterceptorType.IRIS_T_SLS,
    ],
}

# Maximum simultaneous interceptors in flight per threat, EXCLUDING
# CIWS. CIWS rounds are counted separately (they're cheap and layered
# point-defense). 3 is enough for the worst case (HGV = PAC-3 + PAC-2 +
# MED_SAM layered).
MAX_SIMULTANEOUS_PER_THREAT = 3

# Seconds-to-impact under which "last-resort" fire kicks in — if primary
# and fallback have nothing in range, try anything available. Stops the
# AI being rigidly cost-rational while a drone is 3 seconds from the
# base with only PAC-2 ammo remaining.
LAST_RESORT_T_IMPACT_S = 15.0

# Complete interceptor roster used by the last-resort tier. Ordered
# cheap → expensive so desperation still favours CIWS / SHORT_SAM when
# they're available.
_ALL_INTERCEPTORS: List[InterceptorType] = [
    InterceptorType.CIWS,
    InterceptorType.SHORT_SAM,
    InterceptorType.IRIS_T_SLS,
    InterceptorType.MED_SAM,
    InterceptorType.LONG_SAM,
    InterceptorType.HIT_TO_KILL,
]


def _time_to_impact(threat_pos: np.ndarray, threat_vel: np.ndarray, base: np.ndarray) -> float:
    """Seconds until threat reaches base, assuming constant closing
    velocity. +inf if not closing."""
    to_base = base - threat_pos
    dist = float(np.linalg.norm(to_base))
    if dist < 1.0:
        return 0.0
    closing = float(np.dot(threat_vel, to_base / dist))
    if closing <= 1.0:
        return float("inf")
    return dist / closing


def _expected_damage(
    assigned_iids: List[int], world
) -> int:
    """Sum of damage_prox over living assigned interceptors. Used as a
    shots-in-flight gate so we stop firing once enough damage is inbound
    to kill the threat."""
    total = 0
    for iid in assigned_iids:
        inter = world.interceptors.get(iid)
        if inter is None or not inter.state.alive:
            continue
        spec = INTERCEPTOR_SPECS.get(InterceptorType(inter.state.kind))
        if spec is None:
            continue
        total += spec.damage_prox
    return total


def _try_fire(
    dist: float,
    kinds: List[InterceptorType],
    launchers: LauncherFleet,
    t_now: float,
) -> Tuple[Optional[InterceptorType], Optional[Launcher]]:
    """Iterate kinds in list order; return (kind, launcher) for the first
    in-range weapon whose launcher is ready. None if nothing fires."""
    for kind in kinds:
        spec = INTERCEPTOR_SPECS[kind]
        if dist > spec.max_range * config.LAUNCH_RANGE_MARGIN:
            continue
        lch = launchers.find_ready(kind, t_now)
        if lch is None:
            continue
        return (kind, lch)
    return (None, None)


class BlueAI:
    def __init__(self):
        # threat_id -> list of interceptor_ids currently in flight at it
        self.assignments: Dict[int, List[int]] = {}
        self.log: List[str] = []
        self.launchers = LauncherFleet()

    def step(self, t_now: float, world) -> None:
        self.launchers.tick(t_now)

        # Purge dead interceptor ids from assignments so saturation
        # accounting stays accurate.
        for tid in list(self.assignments.keys()):
            live = [
                iid
                for iid in self.assignments[tid]
                if iid in world.interceptors
                and world.interceptors[iid].state.alive
            ]
            if live:
                self.assignments[tid] = live
            else:
                self.assignments.pop(tid, None)

        base = np.array(config.BLUE_BASE_POS, dtype=np.float64)

        for tid, threat in world.threats.items():
            if not threat.state.alive:
                continue

            threat_pos = threat.state.pos
            threat_vel = threat.state.vel
            threat_kind = ThreatType(threat.state.kind)
            dist = float(np.linalg.norm(threat_pos - base))

            # CIWS is counted separately from the main saturation cap —
            # it's the cheap point-defense layer that fires whenever
            # anything is inside its envelope, even if other
            # interceptors are already inbound.
            assigned_iids = self.assignments.get(tid, [])
            non_ciws = [
                iid for iid in assigned_iids
                if iid in world.interceptors
                and world.interceptors[iid].state.kind != InterceptorType.CIWS.value
            ]

            # --- Point-defense: CIWS fires on ANY threat inside its
            # 4 km envelope, regardless of saturation gate or threat
            # kind. Real Lvkv 90 doctrine is "anything that reaches the
            # inner ring gets sprayed" — cheap rounds, cheap kill
            # attempt even on hypersonic RVs that probably outrun it.
            # Provides visible defensive fire for the demo.
            ciws_spec = INTERCEPTOR_SPECS[InterceptorType.CIWS]
            if dist < ciws_spec.max_range * config.LAUNCH_RANGE_MARGIN:
                lch = self.launchers.find_ready(InterceptorType.CIWS, t_now)
                if lch is not None:
                    self._fire(
                        world, t_now, tid, threat, InterceptorType.CIWS,
                        lch, base, dist, tag=" [CIWS]",
                    )
                    # Continue to the main saturation pass below — SAMs
                    # still layer on top if gates allow.

            # --- Main saturation gate (excludes CIWS rounds) ---
            if len(non_ciws) >= MAX_SIMULTANEOUS_PER_THREAT:
                continue
            expected_dmg = _expected_damage(non_ciws, world)
            if expected_dmg >= threat.state.hp:
                continue

            # Primary pass: first in-range + ready weapon in preference
            # order.
            kind, lch = _try_fire(
                dist, PRIMARY_RULES.get(threat_kind, []), self.launchers, t_now
            )
            tag = ""

            if kind is None:
                # No primary option; try fallback.
                fb_kinds = FALLBACK_RULES.get(threat_kind, [])
                kind, lch = _try_fire(dist, fb_kinds, self.launchers, t_now)
                if kind is not None:
                    tag = " [FALLBACK]"

            if kind is None:
                # Primary + fallback both dry. If impact is imminent,
                # throw anything in range — operator brief: "if a drone
                # is about to hit and only PAC-2 is left, use the PAC-2".
                t_impact = _time_to_impact(threat_pos, threat_vel, base)
                if t_impact < LAST_RESORT_T_IMPACT_S:
                    tried = set(PRIMARY_RULES.get(threat_kind, [])) | set(
                        FALLBACK_RULES.get(threat_kind, [])
                    )
                    desperation = [k for k in _ALL_INTERCEPTORS if k not in tried]
                    kind, lch = _try_fire(dist, desperation, self.launchers, t_now)
                    if kind is not None:
                        tag = " [LAST RESORT]"

            if kind is None:
                continue  # nothing to do this tick

            self._fire(world, t_now, tid, threat, kind, lch, base, dist, tag=tag)

    def _fire(
        self,
        world,
        t_now: float,
        tid: int,
        threat,
        kind: InterceptorType,
        lch: Launcher,
        base: np.ndarray,
        dist: float,
        tag: str,
    ) -> None:
        initial_dir = threat.state.pos - base
        initial_dir[2] = max(initial_dir[2], 1000.0)
        iid = world.spawn_interceptor(
            kind, tuple(base), tuple(initial_dir), tid
        )
        lch.fire(t_now)
        self.assignments.setdefault(tid, []).append(iid)
        threat_spec = THREAT_SPECS[ThreatType(threat.state.kind)]
        dmg = INTERCEPTOR_SPECS[kind].damage_prox
        n_flight = len(self.assignments[tid])
        self.log.append(
            f"[{t_now:6.1f}s] {kind.value}{tag} → {threat.state.kind} "
            f"(hp {threat.state.hp}/{threat_spec.hp}, "
            f"{n_flight} in flight, inbound +{dmg} dmg, "
            f"rng {dist/1000:.1f} km)"
        )
