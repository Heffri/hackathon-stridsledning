"""Simulation world: tick loop, spawning, binary intercept detection.

No HP: closest-approach distance under kill_radius = hit. Both the
interceptor and the target are removed, explosion event emitted.
"""
from typing import Dict, List, Optional

import numpy as np

from . import config, physics, sites, terrain
from .entities import Interceptor, Threat
from .types import (
    LEGAL_PHASE_TRANSITIONS,
    EntityState,
    Explosion,
    InterceptorSpec,
    InterceptorType,
    MatchPhase,
    Team,
    ThreatType,
)


def resolve_detonation(
    spec: InterceptorSpec,
    engagement_mode: str,
    d_min: float,
) -> Optional[str]:
    """Decide whether an interceptor detonates given its closest-approach
    distance `d_min` to the tracked primary target. Returns the event
    `hit_kind` string on detonation, or None on miss.

    Trigger semantics (AOE 2026-04-24):
      * 'prox' — detonate when `d_min < radius_prox`. hit_kind 'direct'
        if inside radius_direct, else 'prox'.
      * 'htk'  — detonate when `d_min < radius_direct`. hit_kind
        'htk_direct'. PAC-3 uses this exclusively.

    Damage is no longer computed here — callers run `resolve_aoe` at the
    detonation coordinate to apply flat `fragment_damage` within
    `fragment_radius` to every alive Red threat.

    Raises ValueError for unknown mode strings (caller bug).
    """
    if engagement_mode == "prox":
        if d_min < spec.radius_direct:
            return "direct"
        if d_min < spec.radius_prox:
            return "prox"
        return None
    if engagement_mode == "htk":
        if d_min < spec.radius_direct:
            return "htk_direct"
        return None
    raise ValueError(f"Unknown engagement_mode: {engagement_mode!r}")


def resolve_aoe(
    world: "World",
    spec: InterceptorSpec,
    detonation_xyz: np.ndarray,
    primary_target_id: Optional[int] = None,
) -> Dict[int, int]:
    """Apply AOE fragment damage at `detonation_xyz`. Returns a dict
    mapping victim threat_id → damage dealt. Does NOT mutate HP or the
    alive flag — caller applies the per-victim HP update + event
    emission so it can dedupe events and book-keep cost-exchange.

    Rules:
      * Only alive Red threats are damage candidates. Blue interceptors,
        Blue sites, and already-dead threats are skipped — no friendly
        fire, no AOE on ground targets.
      * Flat within-radius damage: every threat with `d <= fragment_radius`
        takes exactly `fragment_damage`. No falloff — clean RL gradient.
      * `fragment_radius=0` (PAC-3): only the `primary_target_id`
        threat takes damage, and only if it's still alive. Matches the
        "pure HTK, no splash" design intent. `d <= 0` would otherwise
        match nothing since a threat's centre is never exactly at the
        detonation point given floating-point arithmetic.
    """
    hits: Dict[int, int] = {}
    radius = float(spec.fragment_radius)
    damage = int(spec.fragment_damage)
    if radius <= 0.0:
        # Pure-HTK (PAC-3). Primary target connects; no splash.
        if primary_target_id is None:
            return hits
        primary = world.threats.get(primary_target_id)
        if primary is None or not primary.state.alive:
            return hits
        hits[primary_target_id] = damage
        return hits
    radius_sq = radius * radius
    dx = detonation_xyz[0]
    dy = detonation_xyz[1]
    dz = detonation_xyz[2]
    for tid, threat in world.threats.items():
        if not threat.state.alive:
            continue
        p = threat.state.pos
        ddx = float(p[0]) - dx
        ddy = float(p[1]) - dy
        ddz = float(p[2]) - dz
        if (ddx * ddx + ddy * ddy + ddz * ddz) <= radius_sq:
            hits[tid] = damage
    return hits


class World:
    def __init__(self):
        self.t: float = 0.0
        self.threats: Dict[int, Threat] = {}
        self.interceptors: Dict[int, Interceptor] = {}
        self.explosions: List[Explosion] = []
        self._next_id: int = 1

        # Counters for HUD
        self.threats_spawned: int = 0
        self.intercepts: int = 0
        self.leaked: int = 0  # threats that hit the base

        # Milestone I: Blue spends USD per interceptor launch.
        # BlueAI._fire deducts spec.usd_cost. Issue #21 (M-TIER2.8)
        # removed budget-as-loss — budget is an economic HUD indicator.
        self.blue_budget: int = config.BLUE_BUDGET_START
        self.blue_budget_max: int = config.BLUE_BUDGET_START

        # M-TIER3-RED-BUDGET (Issue #8, 2026-04-20): Red side
        # symmetric pool. Deducted per-threat at spawn time in
        # `red_ai.step` (THREAT_SPECS[kind].usd_cost). Spawn is gated —
        # if world.red_budget < cost of the next threat, that threat
        # is skipped and logged. Scenario.winner adds a future-ready
        # Blue-win path on budget exhaustion + no-threats-alive; a
        # no-op under the current wave spawner because red.done fires
        # first, but live once Boyu's Red AI spawns on a budget
        # decision rather than a wave schedule.
        self.red_budget: int = config.RED_BUDGET_START
        self.red_budget_max: int = config.RED_BUDGET_START

        # M-TIER2-PHASE: Match lifecycle phase. A freshly constructed
        # World sits in SETUP until someone (server `start` command, a
        # test calling `transition(RUNNING)`, or `build_default_scenario(
        # auto_start=True)`) advances it. The sim loop in
        # `Scenario.step` treats any non-RUNNING phase as frozen.
        self.phase: MatchPhase = MatchPhase.SETUP

        self.events: List[dict] = []  # transient event log for this tick

    def _new_id(self) -> int:
        eid = self._next_id
        self._next_id += 1
        return eid

    # --- match phase FSM (M-TIER2-PHASE) ---
    def transition(self, to: "MatchPhase") -> bool:
        """Attempt a Match Phase transition. Returns True on success,
        False on illegal move (state unchanged). The legal table lives
        in `types.LEGAL_PHASE_TRANSITIONS`. No-op (same phase → same
        phase) is treated as illegal so the server layer can surface
        accidental double-clicks as an error rather than silently
        swallowing them.
        """
        if (self.phase, to) not in LEGAL_PHASE_TRANSITIONS:
            return False
        self.phase = to
        return True

    # --- spawning ---
    def spawn_threat(
        self,
        kind: ThreatType,
        start_xy,
        target_xy,
        intermediate_waypoints=None,
        target_site_id=None,
        maneuver_schedule=None,
        validate_location: bool = True,
    ) -> int:
        """Construct a Threat and register it with the world.

        Primary call sites: `red_ai.RedAI.step` during wave spawn,
        plus `test_balance_baseline` / `test_ballistic_cep` /
        `test_hgv_impact` for headless trials.

        Args:
          kind: `ThreatType` enum member.
          start_xy: 2- or 3-tuple in world metres. If length-2, z
            defaults to `spec.cruise_alt` (set inside the Threat
            constructor). Length-3 wins over the spec default.
          target_xy: 2-tuple (site position in metres). z=0 is added
            inside the constructor — every threat aims at ground.
          intermediate_waypoints: optional list of (x, y[, z])
            tuples. Cruise / drone kinds walk this list to the
            final target; ballistic ignores it (solver path only
            uses spawn + target).
          target_site_id: M-TIER3-THREAT-CONTRACT (Issue #10).
            Optional stable integer id of the `Site` this threat is
            aimed at. Used by the flyover-fallback in `Threat.step`
            to detect "I've passed my target" and for external
            traceability (e.g. Red AI log / debugging). None is
            legal — threat just flies to `target_xy` without site
            binding.
          maneuver_schedule: M-TIER3-THREAT-CONTRACT (Issues
            #11 / #12). Optional list of
            `(t_offset_s, turn_dir_3vec, g_load, duration_s)` tuples.
            While an entry is active (spawn-relative time in
            `[t_offset, t_offset + duration)`), the threat's default
            waypoint steering is REPLACED by a lateral acceleration
            of `g_load × GRAVITY` in `turn_dir`. Applies to drone /
            cruise / ballistic only — HGV uses `override_maneuver`
            instead. None / empty list means no scheduled jinks.
          validate_location: W14 (Issue #30) opt-out. When True
            (default), `start_xy` is checked against the per-kind
            Red spawn contract (see "Raises"). Pass False only from
            tests that pre-position a threat at a non-contract
            location to unit-test other behaviour (flyover
            fallback, CIWS saturation, maneuver schedule, winner
            conditions). Production AI callers (RedAI.step today,
            Boyu's Red AI tomorrow) MUST leave this True so bad
            coord choices surface loudly via ValueError rather
            than silently admitting an illegal spawn.

        Returns:
          Entity id (positive int) for lookup in `self.threats`.

        Side effects:
          Appends to `self.threats`, bumps `self.threats_spawned`,
          and emits a `threat_spawn` event with `{id, kind}`.

        Caller rules:
          Do not mutate the returned Threat's internal fields
          directly (`waypoint`, `_wp_queue`, pos, vel). Use
          `Threat.override_maneuver(dir, g)` for per-tick HGV
          lateral control (ignored on drone / cruise / ballistic
          kinds — those use `maneuver_schedule` instead). Spawn
          position and target cannot be changed after construction —
          spawn a new Threat.

        Raises:
          ValueError: W14 (Issue #30) spatial spawn contract — the
            caller's (x, y) violates the per-kind rule. Drone / cruise
            must be on north-side land; ballistic / HGV must be
            y >= config.STRATEGIC_Y_FLOOR. The current wave spawner
            (`red_ai._spawn_point` + `_sample_spawn`) always produces
            valid coords; this raise surfaces bugs in future Red AI
            callers loudly rather than silently dropping the spawn.
            Altitude is not validated — see CONTRACT_SEAMS.md §9.
        """
        # W14 (Issue #30): enforce the Red spawn contract. Boyu's
        # future Red AI calls spawn_threat with arbitrary (x, y) — the
        # runtime validates the location per kind so a misbehaving AI
        # can't cheat by spawning an HGV directly over a Blue site.
        # Tests that pre-position a threat for unit-testing other
        # behaviour (flyover, CIWS, maneuver) can opt out with
        # validate_location=False.
        if validate_location:
            x_spawn = float(start_xy[0])
            y_spawn = float(start_xy[1])
            if kind in (ThreatType.DRONE, ThreatType.CRUISE_SUB):
                if not terrain.point_on_north_land(x_spawn, y_spawn):
                    raise ValueError(
                        f"{kind.value} spawn at ({x_spawn:.0f}, "
                        f"{y_spawn:.0f}) is not on north-side land. "
                        f"Drone / cruise must launch from Red mainland "
                        f"or islands (see terrain.point_on_north_land)."
                    )
            elif kind in (ThreatType.BALLISTIC, ThreatType.HGV):
                if y_spawn < config.STRATEGIC_Y_FLOOR:
                    raise ValueError(
                        f"{kind.value} spawn y={y_spawn:.0f} is too "
                        f"close to the front line. Strategic-range "
                        f"assets must spawn with y >= "
                        f"{config.STRATEGIC_Y_FLOOR:.0f} (gives Blue "
                        f"~20+ s of engagement window; see "
                        f"config.STRATEGIC_Y_FLOOR)."
                    )

        eid = self._new_id()
        t = Threat(
            eid,
            kind,
            start_xy,
            target_xy,
            self.t,
            intermediate_waypoints=intermediate_waypoints,
            target_site_id=target_site_id,
            maneuver_schedule=maneuver_schedule,
        )
        self.threats[eid] = t
        self.threats_spawned += 1
        self.events.append({"type": "threat_spawn", "id": eid, "kind": kind.value})
        return eid

    def spawn_interceptor(
        self,
        kind: InterceptorType,
        launch_pos,
        initial_dir,
        target_id: int,
        engagement_mode: Optional[str] = None,
        launcher_pos=None,
        launcher_max_range_m: Optional[float] = None,
    ) -> int:
        """Construct an Interceptor and register it with the world.

        Primary call sites: `blue_ai.BlueAI._fire` during engagement,
        plus `test_engagement_mode` for unit tests. A future learned
        Blue AI (Oskar) is the main planned additional caller.

        Args:
          kind: `InterceptorType` enum member.
          launch_pos: 3-tuple / np.ndarray launch position in world
            metres (the Interceptor constructor forces a np.array
            copy of shape 3).
          initial_dir: 3-vector pointing at the target at launch.
            Only the horizontal component is used for the VLS boost
            lean — the z component is ignored for SAMs. CIWS (only
            non-VLS kind) uses the full 3-vector for its ballistic
            lofted burst.
          target_id: id of the live Threat this interceptor will
            track via PN guidance.
          engagement_mode: optional `'prox' | 'htk'` override.
            `None` → the interceptor uses its spec's
            `default_engagement_mode` (prox for every SAM, htk for
            pac_3). Explicit strings must appear in
            `spec.engagement_mode_choices` or the Interceptor
            constructor raises `ValueError`.

        Returns:
          Entity id (positive int) for lookup in `self.interceptors`.

        Side effects:
          Appends to `self.interceptors` and emits a `launch` event
          with `{id, kind, target}`.

        Caller rules:
          Pair with `Launcher.fire(t_now, engagement_mode=X)` which
          returns the resolved mode string — pass that through so
          ammo / CD bookkeeping and the Interceptor's mode field
          agree. Contract in `ENGAGEMENT_MODE_DESIGN.md`.
        """
        eid = self._new_id()
        # `engagement_mode=None` → Interceptor uses the spec default.
        # Legal callers (BlueAI._fire) pass the value resolved by
        # Launcher.fire so both ends agree; the Interceptor constructor
        # validates defensively.
        i = Interceptor(
            eid, kind, launch_pos, initial_dir, target_id, self.t,
            engagement_mode=engagement_mode,
            launcher_pos=launcher_pos,
            launcher_max_range_m=launcher_max_range_m,
        )
        self.interceptors[eid] = i
        self.events.append(
            {"type": "launch", "id": eid, "kind": kind.value, "target": target_id}
        )
        return eid

    # --- retarget helpers (AOE 2026-04-24) ---
    def nearest_alive_threat(self, inter) -> "Optional[Threat]":
        """Pick the nearest alive Red threat inside the interceptor's
        LAUNCHER range envelope. Range gate uses 2D ground distance from
        the threat to `inter.launcher_pos` against `inter.launcher_max_range_m`
        × `config.LAUNCH_RANGE_MARGIN`. Ranking is done by 3D distance
        from the threat to the interceptor's current position — once the
        gate is passed, grab the physically-closest threat for the
        shortest retarget leg.

        Returns None if no alive threat falls inside the launcher's
        envelope.
        """
        if not self.threats:
            return None
        gate_sq = (inter.launcher_max_range_m * config.LAUNCH_RANGE_MARGIN) ** 2
        lx = float(inter.launcher_pos[0])
        ly = float(inter.launcher_pos[1])
        ipos = inter.state.pos
        ix = float(ipos[0])
        iy = float(ipos[1])
        iz = float(ipos[2])
        best_t = None
        best_d3_sq = None
        for threat in self.threats.values():
            if not threat.state.alive:
                continue
            if threat.state.team != Team.RED:
                continue
            tp = threat.state.pos
            tx = float(tp[0])
            ty = float(tp[1])
            # 2D ground-distance gate from threat to launcher.
            dx_g = tx - lx
            dy_g = ty - ly
            if (dx_g * dx_g + dy_g * dy_g) > gate_sq:
                continue
            # 3D ranking distance from threat to interceptor.
            dx_r = tx - ix
            dy_r = ty - iy
            dz_r = float(tp[2]) - iz
            d3_sq = dx_r * dx_r + dy_r * dy_r + dz_r * dz_r
            if best_d3_sq is None or d3_sq < best_d3_sq:
                best_d3_sq = d3_sq
                best_t = threat
        return best_t

    def _in_terminal_lock(self, inter, dt: float) -> bool:
        """Return True if the interceptor is within 2 s of predicted CPA
        against its *previous* target — regardless of whether that
        target is still alive. Locked interceptors skip retarget so
        terminal geometry plays out and AOE can still catch the old
        target area. Old target fully pruned → no terminal lock,
        retarget allowed.
        """
        old_tid = inter.target_id
        if old_tid is None:
            return False
        old_t = self.threats.get(old_tid)
        if old_t is None:
            return False
        # Signed closing time: dot((p_t - p_i), (v_t - v_i)) / |v_rel|^2
        # Positive when the two bodies are still approaching; 0..2 s
        # window = terminal lock.
        rel_p = old_t.state.pos - inter.state.pos
        rel_v = old_t.state.vel - inter.state.vel
        rel_v_sq = float(np.dot(rel_v, rel_v))
        if rel_v_sq < 1e-6:
            return False
        t_cpa = -float(np.dot(rel_p, rel_v)) / rel_v_sq
        return 0.0 <= t_cpa < 2.0

    # --- tick ---
    def step(self, dt: float) -> None:
        """Advance the world by `dt` seconds. Five phases in order:

          1. Threat step (physics integration per kind).
          2. Interceptor step (PN guidance + CPA update) + timeout
             check against `config.INTERCEPT_TIMEOUT`.
          3. CPA-based interceptor-vs-threat damage resolution.
             Interceptor is consumed regardless of damage dealt;
             threat only dies when hp drops to 0.
          4. Site-disc leak detection (horizontal radius
             `BASE_HIT_RADIUS`, gated by `requires_ground_impact`).
             A threat inside any site's disc + near ground leaks
             to that site and subtracts `SITE_LEAK_DAMAGE[kind]`
             from its hp.
          4b. Unified ground-impact collision for any remaining
             live threat / interceptor that touches the ground.
             Threats landing inside a site disc leak; outside, a
             `ground_crash` event fires.
          5. `self.t += dt` — advance sim time.

        Not phase-gated: the phase gate lives at `Scenario.step`
        only. Callers that construct a raw `World()` and drive
        `world.step(dt)` directly (several tests do this) bypass
        the FSM and always advance. If a future change moves phase
        gating down here, update those tests.

        Events are cleared by `Scenario.step` at the start of its
        tick, not here — otherwise launch events appended by
        `blue_ai.step` before `world.step` would get wiped.
        """

        # 1) advance threats. HGV needs world access to scan for nearby
        # interceptors (Level-5 evasion); other threats ignore the arg.
        for threat in list(self.threats.values()):
            prev_pos = threat.state.pos.copy()
            prev_vel = threat.state.vel.copy()
            threat.step(dt, self)
            threat._prev_pos = prev_pos  # stored on-the-fly for CPA calc
            threat._prev_vel = prev_vel

        # 2) advance interceptors. Lost-target retarget runs FIRST
        # (AOE 2026-04-24): if the tracked target is missing or dead and
        # we're not in terminal-lock (< 2 s to CPA on the old target
        # state), pick the nearest alive Red threat inside the original
        # launcher's range envelope. No target found → target_id=None,
        # interceptor coasts to stall naturally.
        for inter in list(self.interceptors.values()):
            if not inter.state.alive:
                continue
            target = self.threats.get(inter.target_id) if inter.target_id is not None else None
            target_dead_or_missing = target is None or not target.state.alive
            if target_dead_or_missing and not self._in_terminal_lock(inter, dt):
                new_target = self.nearest_alive_threat(inter)
                if new_target is not None:
                    inter.target_id = new_target.state.id
                    inter.state.target_id = new_target.state.id
                else:
                    inter.target_id = None
                    inter.state.target_id = None

            prev_pos = inter.state.pos.copy()
            prev_vel = inter.state.vel.copy()
            target = self.threats.get(inter.target_id) if inter.target_id is not None else None
            target_state = target.state if target is not None else None
            inter.step(dt, target_state, self.t)
            inter._prev_pos = prev_pos
            inter._prev_vel = prev_vel

            # Timeout / out-of-arena
            age = self.t - inter.launched_t
            if age > config.INTERCEPT_TIMEOUT and inter.state.alive:
                inter.state.alive = False
                self.events.append(
                    {"type": "timeout", "id": inter.state.id}
                )

        # 3) AOE collision resolution (2026-04-24). For each live
        # interceptor: test CPA vs primary target, trigger detonation
        # via `resolve_detonation` (prox/htk mode), then apply
        # `resolve_aoe` at the detonation coordinate — every alive Red
        # threat inside `fragment_radius` takes flat `fragment_damage`.
        # Interceptor is consumed on detonation only (miss keeps it
        # flying, next tick tries again).
        for inter in list(self.interceptors.values()):
            if not inter.state.alive:
                continue
            target = self.threats.get(inter.target_id)
            if target is None or not target.state.alive:
                continue

            d_min = physics.closest_approach(
                inter._prev_pos, inter._prev_vel,
                target._prev_pos, target._prev_vel,
                dt,
            )
            hit_kind = resolve_detonation(
                inter.spec, inter.engagement_mode, d_min
            )
            if hit_kind is None:
                continue  # no detonation, interceptor keeps flying

            det_pos = (inter.state.pos + target.state.pos) * 0.5
            primary_id = target.state.id
            # AOE: flat fragment_damage to every alive threat inside
            # fragment_radius. PAC-3 (radius=0) hits primary only.
            aoe_hits = resolve_aoe(
                self, inter.spec, det_pos, primary_target_id=primary_id
            )
            inter.state.alive = False  # consumed on detonation
            self.explosions.append(Explosion(pos=det_pos, t=self.t))

            # Apply HP + emit per-victim events so Blue RL reward can
            # dedupe by interceptor id. `is_primary` marks the tracked
            # target for cost-exchange bookkeeping.
            for vid, dmg in aoe_hits.items():
                victim = self.threats.get(vid)
                if victim is None:
                    continue
                victim.state.hp = max(0, victim.state.hp - dmg)
                is_primary = (vid == primary_id)
                pos_list = [
                    float(det_pos[0]), float(det_pos[1]), float(det_pos[2])
                ]
                if victim.state.hp <= 0:
                    victim.state.alive = False
                    self.intercepts += 1
                    self.events.append({
                        "type": "intercept",
                        "interceptor": inter.state.id,
                        "threat": victim.state.id,
                        "kind": victim.state.kind,
                        "interceptor_kind": inter.state.kind,
                        "pos": pos_list,
                        "miss_distance": d_min if is_primary else 0.0,
                        "damage": dmg,
                        "hit_kind": hit_kind if is_primary else "aoe",
                        "is_primary": is_primary,
                        "primary_threat": primary_id,
                    })
                else:
                    self.events.append({
                        "type": "damage",
                        "interceptor": inter.state.id,
                        "threat": victim.state.id,
                        "kind": victim.state.kind,
                        "interceptor_kind": inter.state.kind,
                        "pos": pos_list,
                        "miss_distance": d_min if is_primary else 0.0,
                        "damage": dmg,
                        "hit_kind": hit_kind if is_primary else "aoe",
                        "hp_remaining": victim.state.hp,
                        "is_primary": is_primary,
                        "primary_threat": primary_id,
                    })

        # 4) threats that crossed any site footprint (horizontal distance
        #    within config.BASE_HIT_RADIUS, any altitude). Milestone G:
        #    the single-base block is gone — every Saab-named south-side
        #    location plus the legacy base is a targetable site. The hit
        #    radius stays 1500 m (matches visual marker + pre-G geometry).
        #    Uses horizontal 2D distance so an HGV terminal-diving over
        #    a site doesn't skim the 3D sphere.
        hit_r_sq = config.BASE_HIT_RADIUS * config.BASE_HIT_RADIUS
        # Ground-impact epsilon above site altitude (sites sit at GROUND_Z).
        # A 50 m window catches the terminal dive frame without letting a
        # high-altitude airburst count as a hit.
        ground_eps = config.GROUND_Z + 50.0
        for tid, threat in list(self.threats.items()):
            if not threat.state.alive:
                continue
            for site in sites.SOUTH_SITES:
                dx = threat.state.pos[0] - site.pos[0]
                dy = threat.state.pos[1] - site.pos[1]
                if (dx * dx + dy * dy) < hit_r_sq:
                    # HGV (and any future kind flagged requires_ground_impact)
                    # must also be near ground; otherwise it flies through
                    # and the damage is instead resolved by the ground-
                    # impact leak path at section 4b when/if it crashes.
                    if threat.spec.requires_ground_impact and threat.state.pos[2] > ground_eps:
                        continue
                    threat.state.alive = False
                    site.leaks += 1
                    self.leaked += 1
                    # Milestone I: per-kind HP damage on every leak.
                    dmg = config.SITE_LEAK_DAMAGE.get(threat.state.kind, 10)
                    site.hp = max(0, site.hp - dmg)
                    self.explosions.append(Explosion(pos=threat.state.pos.copy(), t=self.t))
                    self.events.append(
                        {
                            "type": "leak",
                            "threat": tid,
                            "kind": threat.state.kind,
                            "site": site.name,
                            "damage": dmg,
                            "site_hp": site.hp,
                        }
                    )
                    break

        # 4b) Unified ground collision — any live entity (threat or
        # interceptor) that touches the ground explodes. Ground impact
        # inside any site footprint counts as a leak for that site;
        # outside all sites, it's a ground_crash.
        for tid, threat in list(self.threats.items()):
            if not threat.state.alive:
                continue
            if threat.state.pos[2] <= config.GROUND_Z:
                threat.state.alive = False
                hit_pos = threat.state.pos.copy()
                hit_pos[2] = config.GROUND_Z
                self.explosions.append(Explosion(pos=hit_pos, t=self.t))
                hit_site = None
                for site in sites.SOUTH_SITES:
                    dx = hit_pos[0] - site.pos[0]
                    dy = hit_pos[1] - site.pos[1]
                    if (dx * dx + dy * dy) <= hit_r_sq:
                        hit_site = site
                        break
                if hit_site is not None:
                    hit_site.leaks += 1
                    self.leaked += 1
                    dmg = config.SITE_LEAK_DAMAGE.get(threat.state.kind, 10)
                    hit_site.hp = max(0, hit_site.hp - dmg)
                    self.events.append(
                        {
                            "type": "leak",
                            "threat": tid,
                            "kind": threat.state.kind,
                            "site": hit_site.name,
                            "damage": dmg,
                            "site_hp": hit_site.hp,
                        }
                    )
                else:
                    self.events.append(
                        {"type": "ground_crash", "threat": tid, "kind": threat.state.kind}
                    )
        for iid, inter in list(self.interceptors.items()):
            if not inter.state.alive:
                continue
            if inter.state.pos[2] <= config.GROUND_Z:
                inter.state.alive = False
                hit_pos = inter.state.pos.copy()
                hit_pos[2] = config.GROUND_Z
                self.explosions.append(Explosion(pos=hit_pos, t=self.t))
                self.events.append(
                    {"type": "ground_crash", "interceptor": iid, "kind": inter.state.kind}
                )

        # 5) dead-entity pruning happens at the end of the RUNNING tick
        # in Scenario.step via world.prune_dead(). Keeping dead entities
        # on the dict for exactly one tick lets the snapshot publish their
        # final pose + kind so the client can render the terminal
        # explosion frame.

        self.t += dt

    def prune_dead(self) -> None:
        """Drop entities marked `state.alive = False` and expired
        explosions. Called at the end of every RUNNING tick in
        `Scenario.step`. Entities that die during `world.step` stay
        in the dict for one extra tick so the next snapshot publishes
        their final pose + kind (client renders the terminal
        explosion frame) before they vanish.
        """
        for tid in [k for k, v in self.threats.items() if not v.state.alive]:
            del self.threats[tid]
        for iid in [k for k, v in self.interceptors.items() if not v.state.alive]:
            del self.interceptors[iid]
        # Drop old explosions
        self.explosions = [
            e for e in self.explosions if (self.t - e.t) < e.lifetime
        ]

    # --- snapshot for streaming ---
    def snapshot(self) -> dict:
        """World-level snapshot: live entities, active explosions,
        this-tick events, and numeric stats. `Scenario.snapshot`
        wraps this with AI logs, launcher state, site HP, winner,
        and phase. Consumed by the frontend via `server.py` once
        per `config.STREAM_HZ` tick.
        """
        ents: List[dict] = []
        for t in self.threats.values():
            ents.append(t.state.to_dict())
        for i in self.interceptors.values():
            ents.append(i.state.to_dict())
        return {
            "t": self.t,
            "entities": ents,
            "explosions": [e.to_dict() for e in self.explosions],
            "events": self.events,
            "stats": {
                "spawned": self.threats_spawned,
                "intercepts": self.intercepts,
                "leaked": self.leaked,
                "active_threats": sum(1 for t in self.threats.values() if t.state.alive),
                "active_interceptors": sum(
                    1 for i in self.interceptors.values() if i.state.alive
                ),
                "blue_budget": self.blue_budget,
                "blue_budget_max": self.blue_budget_max,
                "red_budget": self.red_budget,
                "red_budget_max": self.red_budget_max,
            },
        }
