"""Simulation world: tick loop, spawning, binary intercept detection.

No HP: closest-approach distance under kill_radius = hit. Both the
interceptor and the target are removed, explosion event emitted.
"""
from typing import Dict, List, Optional

import numpy as np

from . import config, physics, sites
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


def resolve_damage(
    spec: InterceptorSpec,
    engagement_mode: str,
    d_min: float,
) -> tuple:
    """Compute (damage, hit_kind) for an interceptor→threat encounter
    at closest-approach distance `d_min`. Extracted from the World.step
    damage branch so `test_engagement_mode` can unit-test the model
    without running the full integrator.

    Mode semantics (M-TIER2.5):
      * 'prox' — current auto direct+prox behaviour. Bit-for-bit
        identical to pre-M-TIER2.5: direct hit inside `radius_direct`
        deals `damage_direct`; inside `radius_prox` deals a linearly-
        falling off fraction of `damage_prox` (at least 1); wider is
        a clean miss (0 damage). Event strings preserved as
        'direct' / 'prox' / 'miss'.
      * 'htk'  — hit-to-kill. Direct hit inside `radius_direct` deals
        `damage_direct * 2`; anything wider is a clean miss. Event
        strings 'htk_direct' / 'htk_miss'. HTK is opt-in (M-TIER2.5
        infrastructure only — no caller defaults to HTK except pac_3,
        which is physically HTK-only).

    Raises ValueError for unknown mode strings (caller bug).
    """
    if engagement_mode == "prox":
        if d_min < spec.radius_direct:
            return (spec.damage_direct, "direct")
        if d_min < spec.radius_prox:
            fall = 1.0 - (d_min / spec.radius_prox)
            return (max(1, int(round(spec.damage_prox * fall))), "prox")
        return (0, "miss")
    if engagement_mode == "htk":
        if d_min < spec.radius_direct:
            return (spec.damage_direct * 2, "htk_direct")
        return (0, "htk_miss")
    raise ValueError(f"Unknown engagement_mode: {engagement_mode!r}")


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
        """
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

        # 2) advance interceptors (need target state — use pre-step target)
        for inter in list(self.interceptors.values()):
            prev_pos = inter.state.pos.copy()
            prev_vel = inter.state.vel.copy()
            target = self.threats.get(inter.target_id)
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

        # 3) collision: for each live interceptor, test CPA vs its target
        # and resolve damage via the (direct, prox) model from
        # WEAPON_SPECS.md. The interceptor is consumed regardless of whether
        # the shot killed the target — that is the tension driving the
        # "need another shot" scenarios. The target only dies when HP ≤ 0.
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
            # CPA gate uses kill_radius (≈ typical PN miss distance). Keep
            # it tighter than radius_prox so the damage event fires at the
            # actual pass — otherwise the damage triggers on the incoming
            # leg at still-large separation and the interceptor is consumed
            # before the closest approach is reached.
            kr = max(inter.spec.kill_radius, target.spec.kill_radius)
            if d_min > kr:
                continue

            # Resolve damage from CPA distance. The spec's "(1 - d/r)²"
            # quadratic falloff combined with real-warhead-scale fuse radii
            # (5-20 m) leaves almost every hit with 1-2 damage given our
            # PN's typical 20-80 m CPA. We instead use a linear falloff with
            # radius_prox scaled up — keeps the "direct vs prox" design
            # intent and spec damage values intact while giving the demo
            # legible 1-3 shot kills. M-TIER2.5 factored this out into
            # `resolve_damage` so the mode split (prox vs htk) is unit-
            # testable without the full step loop.
            damage, hit_kind = resolve_damage(
                inter.spec, inter.engagement_mode, d_min
            )

            hit_pos = (inter.state.pos + target.state.pos) * 0.5
            target.state.hp = max(0, target.state.hp - damage)
            inter.state.alive = False  # interceptor consumed either way
            # Always show a small flash at the CPA point so near-misses
            # still read on screen.
            self.explosions.append(Explosion(pos=hit_pos, t=self.t))

            if target.state.hp <= 0:
                target.state.alive = False
                self.intercepts += 1
                self.events.append(
                    {
                        "type": "intercept",
                        "interceptor": inter.state.id,
                        "threat": target.state.id,
                        "pos": [float(hit_pos[0]), float(hit_pos[1]), float(hit_pos[2])],
                        "miss_distance": d_min,
                        "damage": damage,
                        "hit_kind": hit_kind,
                    }
                )
            else:
                self.events.append(
                    {
                        "type": "damage",
                        "interceptor": inter.state.id,
                        "threat": target.state.id,
                        "pos": [float(hit_pos[0]), float(hit_pos[1]), float(hit_pos[2])],
                        "miss_distance": d_min,
                        "damage": damage,
                        "hit_kind": hit_kind,
                        "hp_remaining": target.state.hp,
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
