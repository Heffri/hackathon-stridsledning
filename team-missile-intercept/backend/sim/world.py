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


def resolve_aoe(
    spec: InterceptorSpec,
    detonation_xyz: np.ndarray,
    threats: Dict[int, "Threat"],
) -> Dict[int, int]:
    """Flat-within-radius AOE damage. Returns `{threat_id: damage}` for
    every alive threat whose 3D distance to `detonation_xyz` is
    `<= spec.fragment_radius`. Direct-hit on the primary target reads
    out of the same map — at d≈0 (detonation centred on the target)
    the threat is inside any non-negative radius.

    PAC-3 edge case: `spec.fragment_radius == 0` means only threats at
    exactly d=0 qualify. The `<=` (not `<`) gate preserves one-shot
    behaviour when the detonation is placed at the primary target's
    position (see the caller in `World.step`).

    Design: flat within radius (not a falloff) keeps the RL gradient
    clean — every cluster of drones inside a warhead burst either all
    live or all die, no partial-damage grey zone that confuses the
    policy's credit assignment.
    """
    out: Dict[int, int] = {}
    r = float(spec.fragment_radius)
    dmg = int(spec.fragment_damage)
    if dmg <= 0:
        return out
    dx = detonation_xyz
    for tid, threat in threats.items():
        if not threat.state.alive:
            continue
        p = threat.state.pos
        # 3D distance — AOE is volumetric (airburst above a ground
        # target still catches the target).
        d = ((p[0] - dx[0]) ** 2 + (p[1] - dx[1]) ** 2 + (p[2] - dx[2]) ** 2) ** 0.5
        if d <= r:
            out[tid] = dmg
    return out


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
        )
        self.interceptors[eid] = i
        self.events.append(
            {"type": "launch", "id": eid, "kind": kind.value, "target": target_id}
        )
        return eid

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

        # 2) advance interceptors (need target state — use pre-step target).
        # Arcade AOE reacquire-on-death (blue_aoe_long Phase 2): if the
        # interceptor's current target died, look for the nearest alive
        # threat still inside the launcher's max_range and swap to it.
        # Bug 4 (blue_aoe_mixed): terminal-phase gate — if CPA on the
        # dying target is < 2 s out, a fresh retarget will almost always
        # fail (turn-radius limits). Better to coast on the dying target
        # and timeout quietly than to flail toward a distant live target.
        # Non-terminal death (CPA > 2 s or already-pruned target with no
        # velocity info) falls through to the normal retarget path.
        for inter in list(self.interceptors.values()):
            prev_pos = inter.state.pos.copy()
            prev_vel = inter.state.vel.copy()
            target = self.threats.get(inter.target_id)
            if target is None or not target.state.alive:
                retarget = True
                if target is not None and not target.state.alive:
                    # Target is present but just-died this tick — we still
                    # have its prev_pos / prev_vel to estimate CPA time.
                    # If CPA is < 2 s out, skip the retarget (terminal phase).
                    try:
                        cpa_t = physics.time_to_cpa(
                            inter.state.pos,
                            inter.state.vel,
                            target._prev_pos,
                            target._prev_vel,
                        )
                    except Exception:
                        cpa_t = float("inf")
                    if 0.0 <= cpa_t < 2.0:
                        retarget = False
                if retarget:
                    new_target = self.nearest_alive_threat(
                        inter.state.pos,
                        max_range_m=inter.spec.max_range,
                        launcher_pos=inter._launcher_pos,
                    )
                    if new_target is not None:
                        inter.target_id = new_target.state.id
                        # Bug 8 mirror (2026-04-24): also update
                        # EntityState.target_id so snapshot / HUD / RL obs
                        # consumers see the new target. Interceptor.target_id
                        # (slot) drives PN; EntityState.target_id is what
                        # LearnedBlueAI's orphan cleanup + client renderer
                        # read. Belt-and-braces even after the orphan cleanup
                        # was removed — future telemetry / status-panel
                        # consumers rely on this sync.
                        inter.state.target_id = new_target.state.id
                        target = new_target
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

        # 3) collision + arcade AOE resolution.
        # CPA gate (d_min < kill_radius) fires detonation as before. On
        # detonation the interceptor is consumed and `resolve_aoe` applies
        # `spec.fragment_damage` to every alive threat within 3D
        # `spec.fragment_radius` of the detonation — including the primary
        # target at d≈0. PAC-3 with fragment_radius=0 keeps pure-HTK
        # behaviour thanks to the `<=` gate in resolve_aoe.
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
            kr = max(inter.spec.kill_radius, target.spec.kill_radius)
            if d_min > kr:
                continue

            # Detonation fires at the target's position so PAC-3 (r=0)
            # still gets d=0 on the primary. Secondary threats take
            # fragment_damage if their 3D distance to target is <= radius.
            detonation_pos = target.state.pos.copy()
            hit_pos = (inter.state.pos + target.state.pos) * 0.5
            aoe_dmg = resolve_aoe(inter.spec, detonation_pos, self.threats)

            primary_id = target.state.id
            primary_dmg = aoe_dmg.get(primary_id, 0)
            inter.state.alive = False   # interceptor consumed regardless
            self.explosions.append(Explosion(pos=hit_pos, t=self.t))

            # Apply primary damage first so its event fires with the
            # usual "intercept"/"damage" labelling.
            target.state.hp = max(0, target.state.hp - primary_dmg)
            primary_killed = target.state.hp <= 0
            if primary_killed:
                target.state.alive = False
                self.intercepts += 1
                self.events.append(
                    {
                        "type": "intercept",
                        "interceptor": inter.state.id,
                        "threat": primary_id,
                        "pos": [float(hit_pos[0]), float(hit_pos[1]), float(hit_pos[2])],
                        "miss_distance": d_min,
                        "damage": primary_dmg,
                        "hit_kind": "aoe_primary",
                    }
                )
            else:
                self.events.append(
                    {
                        "type": "damage",
                        "interceptor": inter.state.id,
                        "threat": primary_id,
                        "pos": [float(hit_pos[0]), float(hit_pos[1]), float(hit_pos[2])],
                        "miss_distance": d_min,
                        "damage": primary_dmg,
                        "hit_kind": "aoe_primary",
                        "hp_remaining": target.state.hp,
                    }
                )

            # Secondary AOE — bonus damage to every other alive threat in
            # radius. No friendly fire (interceptors and sites are not in
            # `self.threats`), so the loop below is threat-only by design.
            for tid, dmg in aoe_dmg.items():
                if tid == primary_id:
                    continue
                other = self.threats.get(tid)
                if other is None or not other.state.alive:
                    continue
                other.state.hp = max(0, other.state.hp - dmg)
                if other.state.hp <= 0:
                    other.state.alive = False
                    self.intercepts += 1
                    self.events.append(
                        {
                            "type": "intercept",
                            "interceptor": inter.state.id,
                            "threat": tid,
                            "pos": [float(other.state.pos[0]),
                                    float(other.state.pos[1]),
                                    float(other.state.pos[2])],
                            "miss_distance": float(
                                ((other.state.pos[0] - detonation_pos[0]) ** 2
                                 + (other.state.pos[1] - detonation_pos[1]) ** 2
                                 + (other.state.pos[2] - detonation_pos[2]) ** 2) ** 0.5
                            ),
                            "damage": dmg,
                            "hit_kind": "aoe_secondary",
                        }
                    )
                else:
                    self.events.append(
                        {
                            "type": "damage",
                            "interceptor": inter.state.id,
                            "threat": tid,
                            "pos": [float(other.state.pos[0]),
                                    float(other.state.pos[1]),
                                    float(other.state.pos[2])],
                            "miss_distance": float(
                                ((other.state.pos[0] - detonation_pos[0]) ** 2
                                 + (other.state.pos[1] - detonation_pos[1]) ** 2
                                 + (other.state.pos[2] - detonation_pos[2]) ** 2) ** 0.5
                            ),
                            "damage": dmg,
                            "hit_kind": "aoe_secondary",
                            "hp_remaining": other.state.hp,
                        }
                    )

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

    def nearest_alive_threat(
        self,
        pos: np.ndarray,
        max_range_m: float,
        launcher_pos: np.ndarray,
    ) -> Optional[Threat]:
        """Find the closest alive threat to `pos` whose 2D ground distance
        from `launcher_pos` is within `max_range_m`. Used by the arcade
        AOE reacquire-on-death hook in World.step. Returns None when no
        alive threat satisfies the launcher-range gate.

        Gate semantics mirror `blue_ai._try_fire` so that a retargeted
        interceptor doesn't pick a target the original launcher couldn't
        have fired at — a real launcher can't magically extend its range
        just because a missile is already airborne.
        """
        lx = float(launcher_pos[0])
        ly = float(launcher_pos[1])
        gate_sq = float(max_range_m) * float(max_range_m)
        ix = float(pos[0])
        iy = float(pos[1])
        iz = float(pos[2]) if len(pos) > 2 else 0.0
        best: Optional[Threat] = None
        best_d_sq = float("inf")
        for threat in self.threats.values():
            if not threat.state.alive:
                continue
            tx = float(threat.state.pos[0])
            ty = float(threat.state.pos[1])
            # Launcher-to-candidate gate (2D ground distance)
            dx_l = tx - lx
            dy_l = ty - ly
            if dx_l * dx_l + dy_l * dy_l > gate_sq:
                continue
            # Pick nearest to the interceptor (3D)
            dx_i = tx - ix
            dy_i = ty - iy
            dz_i = float(threat.state.pos[2]) - iz
            d_sq = dx_i * dx_i + dy_i * dy_i + dz_i * dz_i
            if d_sq < best_d_sq:
                best_d_sq = d_sq
                best = threat
        return best

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
