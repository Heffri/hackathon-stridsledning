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
# Fallback fires when the preferred primary weapons are all busy or out
# of range. Operator principle: "cost-exchange is the FIRST consideration
# but not the only one — if a threat is at the door and only an
# expensive weapon is available, fire the expensive weapon." Fallback is
# how the AI honours that principle without abandoning cost discipline:
# primary is tried first every tick, fallback only kicks in when primary
# returns nothing. For DRONE specifically, wave 5's three simultaneous
# drones used to saturate the 2× RBS 70 launchers and then get ignored
# by the idle IRIS-T SLS — now SLS / SLM step in as fallback.
FALLBACK_RULES: Dict[ThreatType, List[InterceptorType]] = {
    # DRONE fallback is intentionally just SLS. MED-SAM at $1 M firing
    # on a $30 K drone is 33× exchange — that's the kind of rigidity the
    # operator explicitly didn't want ("cost matters but don't paralyse
    # yourself"). SLS at 16× is also bad but the point-defense override
    # (CIWS bypasses saturation) + the LAST_RESORT_T_IMPACT_S tier cover
    # the genuinely urgent cases.
    ThreatType.DRONE: [
        InterceptorType.IRIS_T_SLS,
    ],
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
    """Seconds until threat reaches `base`, assuming constant closing
    velocity. +inf if not closing. Still anchored to the base as an
    approximate "defended point" — with 7 Saab sites spread across the
    south there's no single defended point, but the base sits roughly
    central so urgency estimates via it are close enough for
    wait-vs-escalate decisions."""
    to_base = base - threat_pos
    dist = float(np.linalg.norm(to_base))
    if dist < 1.0:
        return 0.0
    closing = float(np.dot(threat_vel, to_base / dist))
    if closing <= 1.0:
        return float("inf")
    return dist / closing


def _time_to_enter_range(
    threat_pos: np.ndarray,
    threat_vel: np.ndarray,
    launcher_pos: np.ndarray,
    max_range: float,
) -> float:
    """Seconds until the threat crosses inside `max_range × LAUNCH_RANGE_MARGIN`
    of `launcher_pos`. 0 if already inside, +inf if it never will (not
    closing)."""
    gate = max_range * config.LAUNCH_RANGE_MARGIN
    to_lch = launcher_pos - threat_pos
    dist = float(np.linalg.norm(to_lch))
    if dist <= gate:
        return 0.0
    closing = float(np.dot(threat_vel, to_lch / max(dist, 1e-6)))
    if closing <= 1.0:
        return float("inf")
    return (dist - gate) / closing


def _launcher_ready_time(
    launchers: LauncherFleet, kind: InterceptorType, t_now: float
) -> float:
    """Min seconds until any launcher of this kind can fire. 0 if one is
    ready now, +inf if none exist. Position-agnostic: this is the
    "will any launcher of this kind be ready within X seconds" upper
    bound. Per-launcher ready time is computed inline in
    _primary_available_in_time since it also needs the launcher's
    position for the matching t_enter."""
    best = float("inf")
    for lch in launchers.launchers:
        if lch.kind != kind:
            continue
        if lch.can_fire(t_now):
            return 0.0
        rt = lch.reload_remaining(t_now) if lch.reloading else 0.0
        cd = max(0.0, lch.inter_shot_cd - (t_now - lch.last_shot_t))
        wait = max(rt, cd)
        if wait < best:
            best = wait
    return best


def _launcher_ready_wait(lch: Launcher, t_now: float) -> float:
    """Per-launcher ready wait: 0 if it can fire now, else max(reload
    remaining, inter-shot CD remaining). Used by
    _primary_available_in_time which needs the wait per individual
    launcher instance (paired with that launcher's position)."""
    if lch.can_fire(t_now):
        return 0.0
    rt = lch.reload_remaining(t_now) if lch.reloading else 0.0
    cd = max(0.0, lch.inter_shot_cd - (t_now - lch.last_shot_t))
    return max(rt, cd)


def _primary_available_in_time(
    kinds: List[InterceptorType],
    launchers: LauncherFleet,
    threat_pos: np.ndarray,
    threat_vel: np.ndarray,
    t_impact: float,
    t_now: float,
    margin: float = 3.0,
) -> bool:
    """True iff at least one `(kind, launcher)` pair of the primary
    `kinds` will be both in range and have that specific launcher ready
    at some point before impact minus `margin`. Milestone H: per-
    launcher range math replaces the Milestone F base-centred gate so
    forward-deployed SLS / SLM aren't wrongly reported as "will reach
    the threat" when their individual positions can't."""
    if t_impact == float("inf"):
        return True  # not closing, no pressure — keep waiting for primary
    deadline = t_impact - margin
    for kind in kinds:
        spec = INTERCEPTOR_SPECS[kind]
        for lch in launchers.launchers:
            if lch.kind != kind:
                continue
            lch_pos_3d = np.array(
                [lch.pos[0], lch.pos[1], 0.0], dtype=np.float64
            )
            t_enter = _time_to_enter_range(
                threat_pos, threat_vel, lch_pos_3d, spec.max_range
            )
            t_ready = _launcher_ready_wait(lch, t_now)
            t_need = max(t_enter, t_ready)
            if t_need < deadline:
                return True
    return False


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
    threat_pos: np.ndarray,
    kinds: List[InterceptorType],
    launchers: LauncherFleet,
    t_now: float,
) -> Tuple[Optional[InterceptorType], Optional[Launcher]]:
    """Iterate `kinds` in preference order. For each kind, iterate every
    launcher of that kind and return the first `(kind, launcher)` pair
    whose individual position puts `threat_pos` inside
    `max_range × LAUNCH_RANGE_MARGIN` AND whose state is ready to fire.
    None if nothing qualifies.

    Milestone H: replaces the Milestone F base-distance gate. Forward-
    deployed SLS / SLM no longer get cleared to fire on threats that
    their actual position can't reach, and they now DO get cleared to
    fire on flank threats that the base-distance check would have
    rejected.
    """
    for kind in kinds:
        spec = INTERCEPTOR_SPECS[kind]
        gate_sq = (spec.max_range * config.LAUNCH_RANGE_MARGIN) ** 2
        for lch in launchers.launchers:
            if lch.kind != kind:
                continue
            if not lch.can_fire(t_now):
                continue
            dx = float(threat_pos[0] - lch.pos[0])
            dy = float(threat_pos[1] - lch.pos[1])
            if dx * dx + dy * dy <= gate_sq:
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
            # `dist_to_base` is kept only for the HUD log line — engagement
            # decisions use per-launcher distances now (Milestone H).
            dist_to_base = float(np.linalg.norm(threat_pos - base))

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
            # 4 km envelope. Real Lvkv 90 doctrine is "anything that
            # reaches the inner ring gets sprayed" — cheap rounds,
            # cheap kill attempt even on hypersonic RVs that probably
            # outrun it. Milestone H: each CIWS launcher checks its
            # own envelope independently.
            #
            # Issue #20 (M-TIER2.8, 2026-04-20): CIWS is still exempt
            # from `MAX_SIMULTANEOUS_PER_THREAT` (rapid-fire is the
            # point — it's a cannon, not a SAM) but DOES respect the
            # expected-damage saturation gate now. Stops firing once
            # enough in-flight damage is inbound to kill the threat,
            # counting every assigned interceptor (CIWS + non-CIWS).
            # Before the fix, CIWS would dump ~20-30 rounds at a 10-HP
            # drone — $40-$60k of ammunition on a $30k target. With
            # the gate, ~2-4 rounds land the kill (drone hp 10 /
            # ciws damage_prox 8 = 2 rounds ceiling), extras stop at
            # the gate.
            ciws_spec = INTERCEPTOR_SPECS[InterceptorType.CIWS]
            ciws_gate_sq = (
                ciws_spec.max_range * config.LAUNCH_RANGE_MARGIN
            ) ** 2
            ciws_expected_dmg = _expected_damage(assigned_iids, world)
            if ciws_expected_dmg < threat.state.hp:
                for lch in self.launchers.launchers:
                    if lch.kind != InterceptorType.CIWS:
                        continue
                    if not lch.can_fire(t_now):
                        continue
                    dx = float(threat_pos[0] - lch.pos[0])
                    dy = float(threat_pos[1] - lch.pos[1])
                    if dx * dx + dy * dy <= ciws_gate_sq:
                        self._fire(
                            world, t_now, tid, threat, InterceptorType.CIWS,
                            lch, base, dist_to_base, tag=" [CIWS]",
                        )
                        break  # one CIWS launcher per tick per threat

            # --- Main saturation gate (excludes CIWS rounds) ---
            if len(non_ciws) >= MAX_SIMULTANEOUS_PER_THREAT:
                continue
            expected_dmg = _expected_damage(non_ciws, world)
            if expected_dmg >= threat.state.hp:
                continue

            # Primary pass: first in-range + ready (kind, launcher) pair
            # in preference order — now computed per-launcher.
            primary_kinds = PRIMARY_RULES.get(threat_kind, [])
            kind, lch = _try_fire(
                threat_pos, primary_kinds, self.launchers, t_now
            )
            tag = ""

            if kind is None:
                # Primary returned nothing this tick. Before escalating
                # to fallback (expensive), check whether a primary option
                # will become available in time. If yes, hold fire and
                # wait — this is the "cost-exchange first" principle.
                # Only escalate when primary genuinely can't engage.
                t_impact = _time_to_impact(threat_pos, threat_vel, base)
                if _primary_available_in_time(
                    primary_kinds, self.launchers,
                    threat_pos, threat_vel, t_impact, t_now,
                ):
                    continue  # wait for primary
                fb_kinds = FALLBACK_RULES.get(threat_kind, [])
                kind, lch = _try_fire(
                    threat_pos, fb_kinds, self.launchers, t_now
                )
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
                    kind, lch = _try_fire(
                        threat_pos, desperation, self.launchers, t_now
                    )
                    if kind is not None:
                        tag = " [LAST RESORT]"

            if kind is None:
                continue  # nothing to do this tick

            self._fire(
                world, t_now, tid, threat, kind, lch, base, dist_to_base,
                tag=tag,
            )

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
        # Milestone F: interceptors launch from the firing launcher's own
        # position, not the base. `base` / `dist` stay in the signature
        # because the HUD log line still reports threat-to-base range
        # (approximate "distance from the thing we're defending"; the
        # operator reads this as the urgency indicator). Milestone H:
        # engagement-decision math now works per-launcher, so the
        # decision to fire actually matches each launcher's physical
        # reach — see `_try_fire` / `_primary_available_in_time`.
        launch_pos = (lch.pos[0], lch.pos[1], 0.0)
        launch_np = np.array(launch_pos, dtype=np.float64)
        initial_dir = threat.state.pos - launch_np
        initial_dir[2] = max(initial_dir[2], 1000.0)
        # M-TIER2.5: caller does not override engagement_mode — spec
        # default applies (prox for every interceptor except pac_3,
        # which is htk by construction). Launcher.fire returns the
        # resolved mode so the Interceptor carries a matching field.
        mode = lch.fire(t_now)
        iid = world.spawn_interceptor(
            kind, launch_pos, tuple(initial_dir), tid, engagement_mode=mode,
        )
        # Milestone I: Blue pays spec.usd_cost per launch. Budget floor
        # at 0. Issue #21 (M-TIER2.8, 2026-04-20): budget depletion is
        # no longer an instant Red win — Scenario.winner only ends the
        # match on military-site HP=0 / all-waves-done-no-threats /
        # max_sim_time, so running out of money just means "no more
        # shots this match"; in-flight interceptors and magazine
        # reserve can still resolve the fight. We deduct regardless of
        # whether the launch was rational (the engagement-decision
        # layer already gates via PRIMARY / FALLBACK / LAST_RESORT;
        # this just wires the cost).
        world.blue_budget = max(
            0, world.blue_budget - INTERCEPTOR_SPECS[kind].usd_cost
        )
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
