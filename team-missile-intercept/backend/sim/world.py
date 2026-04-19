"""Simulation world: tick loop, spawning, binary intercept detection.

No HP: closest-approach distance under kill_radius = hit. Both the
interceptor and the target are removed, explosion event emitted.
"""
from typing import Dict, List, Optional

import numpy as np

from . import config, physics, sites
from .entities import Interceptor, Threat
from .types import (
    EntityState,
    Explosion,
    InterceptorType,
    Team,
    ThreatType,
)


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
        self.misses: int = 0  # threats that reached base / ground
        self.leaked: int = 0  # threats that hit the base

        # Milestone I: Blue spends USD per interceptor launch. Budget
        # exhaustion = Red wins. BlueAI._fire deducts spec.usd_cost.
        self.blue_budget: int = config.BLUE_BUDGET_START
        self.blue_budget_max: int = config.BLUE_BUDGET_START

        self.events: List[dict] = []  # transient event log for this tick

    def _new_id(self) -> int:
        eid = self._next_id
        self._next_id += 1
        return eid

    # --- spawning ---
    def spawn_threat(
        self,
        kind: ThreatType,
        start_xy,
        target_xy,
        intermediate_waypoints=None,
    ) -> int:
        eid = self._new_id()
        t = Threat(
            eid,
            kind,
            start_xy,
            target_xy,
            self.t,
            intermediate_waypoints=intermediate_waypoints,
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
    ) -> int:
        eid = self._new_id()
        i = Interceptor(eid, kind, launch_pos, initial_dir, target_id, self.t)
        self.interceptors[eid] = i
        self.events.append(
            {"type": "launch", "id": eid, "kind": kind.value, "target": target_id}
        )
        return eid

    # --- tick ---
    def step(self, dt: float) -> None:
        # Note: events are cleared by Scenario.step at the start of the
        # tick, not here — otherwise launch events appended by blue_ai
        # (via spawn_interceptor) get wiped before they reach the client.

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
            # legible 1-3 shot kills.
            spec = inter.spec
            if d_min < spec.radius_direct:
                damage = spec.damage_direct
                hit_kind = "direct"
            elif d_min < spec.radius_prox:
                fall = 1.0 - (d_min / spec.radius_prox)
                damage = max(1, int(round(spec.damage_prox * fall)))
                hit_kind = "prox"
            else:
                damage = 0
                hit_kind = "miss"

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

        # 5) sweep dead entities (keep for 1 tick so client can render final pose)
        for tid in list(self.threats.keys()):
            if not self.threats[tid].state.alive:
                # keep a tick of zombie for render continuity
                pass
        # We'll prune at next snapshot step below.

        self.t += dt

    def prune_dead(self) -> None:
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
            },
        }
