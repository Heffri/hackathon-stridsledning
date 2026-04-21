"""Gymnasium environment — Red-perspective RL wrapper (symmetric to env.py).

Agent controls Red offensive decisions. Per decision tick it picks:
  * a threat kind (hold, drone, cruise_sub, ballistic, hgv), and
  * a target Blue site (index into sites.SOUTH_SITES).

Launcher position is auto-selected per kind: drone / cruise_sub pull
from RedLauncherFleet.next_pos (round-robin across the north islands
and mainland); ballistic / hgv use the strategic far-north strip
sampler from red_ai (_STRATEGIC_Y_BAND, altitude floors). Opponent =
rule-based BlueAI. Cadence matches env.py (DECISION_EVERY = 10).

V1 scope cuts (defer to future worker if training plateaus):
  * No launcher-position choice — agent only picks (kind, site).
  * No maneuver_schedule — HGV uses its default glide-dive, cruise_sub
    uses default S-shape waypoints (from red_ai._build_cruise_waypoints).
  * Omniscient observation — identical dict shape + content as Blue env.
    Both sides see the full world state. Red's perspective is encoded in
    the reward, not in a filtered observation.

Observation / feature widths / normalization scales are imported from
rl.env so both envs share ground truth. The `_encode_obs` method is
adapted from rl.env.MissileInterceptEnv._encode_obs — `self.blue.launchers`
replaces `self.fleet`, otherwise bit-identical.

Action space: MultiDiscrete([5, len(SOUTH_SITES)]).
  * action[0] ∈ [0, 5): 0 = hold, 1..4 = ThreatType.(DRONE, CRUISE_SUB,
    BALLISTIC, HGV). Ordering mirrors THREAT_KIND_ORDER + 1.
  * action[1] ∈ [0, len(SOUTH_SITES)): target site index. Ignored when
    action[0] == 0.

Action mask: marginal component-wise, length sum(nvec) = 5 + n_sites.
Slots [0:5] are the kind mask, [5:5+n_sites] is the site mask (always
all-ones — any site is a valid aim point). Consumed via the `action_masks`
method + ActionMasker wrapper in red_train.py.

Reward sign convention (flipped vs Blue):
  * +2.0 × event.damage per `leak` event (Red hit a Blue site).
  * -spec.usd_cost / 1e6 per `intercept` event (Red threat was killed
    in flight). Additive to the spawn cost subtracted at decision time,
    so a spawned-and-intercepted threat nets roughly -2 × cost/$M —
    spawning threats that get shot down is strongly penalised.
  * -0.2 per `ground_crash` event with a threat id (Red threat crashed
    outside a site — wasted).
  * -spec.usd_cost / 1e6 subtracted once per successful spawn at decision
    time (encourages cost-aware play).
  * Terminal: +100 Red win (any Blue site at HP 0), -100 Blue win
    (Red out of budget AND no live threats), 0 draw / truncation.
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np
import gymnasium as gym
from gymnasium import spaces

from sim import sites as sites_module
from sim.blue_ai import BlueAI
from sim.config import (
    ARENA_X,
    DT,
)
from sim.launcher import RedLauncherFleet
from sim.red_ai import (
    BALLISTIC_ALT_RANGE,
    BALLISTIC_MIN_Z,
    CRUISE_ALT_RANGE,
    DRONE_ALT_RANGE,
    HGV_ALT_RANGE,
    HGV_MIN_Z,
    STRATEGIC_Y_BAND,
)
from sim.types import (
    INTERCEPTOR_SPECS,
    InterceptorType,
    MatchPhase,
    THREAT_SPECS,
    ThreatType,
)
from sim.world import World

from rl.env import (
    BUDGET_SCALE,
    DECISION_EVERY,
    GLOBAL_FEATURES,
    INT_KIND_ORDER,
    INTERCEPTOR_FEATURES,
    LAUNCHER_FEATURES,
    MAX_EPISODE_SIM_TIME,
    MAX_INTERCEPTORS,
    MAX_LAUNCHERS,
    MAX_SITES,
    MAX_THREATS,
    N_INT_KINDS,
    N_PHASES,
    N_SITE_SUBTYPES,
    N_THREAT_KINDS,
    PHASE_ORDER,
    POS_SCALE,
    SITE_FEATURES,
    SITE_SUBTYPE_ORDER,
    THREAT_FEATURES,
    THREAT_KIND_ORDER,
    TIME_SCALE,
    VEL_SCALE,
)


# Red action → ThreatType mapping. Index 0 = hold; 1..4 mirror
# THREAT_KIND_ORDER so the network's kind-slot axis has a stable
# interpretation across both envs.
RED_ACTION_KINDS: List[Optional[ThreatType]] = [
    None,
    ThreatType.DRONE,
    ThreatType.CRUISE_SUB,
    ThreatType.BALLISTIC,
    ThreatType.HGV,
]
N_RED_KINDS = len(RED_ACTION_KINDS)


def _onehot(idx: int, n: int) -> np.ndarray:
    v = np.zeros(n, dtype=np.float32)
    if 0 <= idx < n:
        v[idx] = 1.0
    return v


class RedEnv(gym.Env):
    """Red-perspective Gym env. See module docstring for agent contract."""

    metadata = {"render_modes": []}

    def __init__(
        self,
        seed: Optional[int] = None,
        episode_time_limit: float = MAX_EPISODE_SIM_TIME,
    ):
        super().__init__()
        self._seed = seed
        self._episode_time_limit = episode_time_limit
        # Captured at construction. SOUTH_SITES is a module-level list
        # that is populated once at import of sim.sites, so len(...) is
        # stable across the env's lifetime.
        self._n_sites = max(1, len(sites_module.SOUTH_SITES))
        self._build_spaces()
        self.world: Optional[World] = None
        self.blue: Optional[BlueAI] = None
        self.red_launchers: Optional[RedLauncherFleet] = None
        self.rng: Optional[np.random.Generator] = None
        self._cum_reward: float = 0.0

    def _build_spaces(self):
        mask_len = N_RED_KINDS + self._n_sites
        self.observation_space = spaces.Dict({
            "threats": spaces.Box(-10.0, 10.0, (MAX_THREATS, THREAT_FEATURES), dtype=np.float32),
            "threats_mask": spaces.Box(0, 1, (MAX_THREATS,), dtype=np.int8),
            "launchers": spaces.Box(-10.0, 10.0, (MAX_LAUNCHERS, LAUNCHER_FEATURES), dtype=np.float32),
            "launchers_mask": spaces.Box(0, 1, (MAX_LAUNCHERS,), dtype=np.int8),
            "interceptors": spaces.Box(-10.0, 10.0, (MAX_INTERCEPTORS, INTERCEPTOR_FEATURES), dtype=np.float32),
            "interceptors_mask": spaces.Box(0, 1, (MAX_INTERCEPTORS,), dtype=np.int8),
            "sites": spaces.Box(-10.0, 10.0, (MAX_SITES, SITE_FEATURES), dtype=np.float32),
            "sites_mask": spaces.Box(0, 1, (MAX_SITES,), dtype=np.int8),
            "global": spaces.Box(-10.0, 10.0, (GLOBAL_FEATURES,), dtype=np.float32),
            # Component-wise marginal mask. Slots [0:N_RED_KINDS] gate
            # the kind choice; slots [N_RED_KINDS:N_RED_KINDS+n_sites]
            # gate the site choice. MaskablePPO expects sum(nvec).
            "action_mask": spaces.Box(0, 1, (mask_len,), dtype=np.int8),
        })
        self.action_space = spaces.MultiDiscrete([N_RED_KINDS, self._n_sites])

    # ------------------------------------------------------------------
    def reset(self, seed: Optional[int] = None, options=None):
        super().reset(seed=seed)
        if seed is not None:
            self._seed = seed
        self.rng = np.random.default_rng(seed)
        sites_module.reset_leaks()
        self.world = World()
        # BlueAI owns its own LauncherFleet (constructed from
        # config.BLUE_LAUNCHER_POSITIONS). Mirrors how env.py uses its
        # own fleet — except here the fleet belongs to the opponent.
        self.blue = BlueAI()
        # Red launcher fleet is used only for `positions_for(kind)` /
        # `next_pos(kind)` lookups; no ammo / cooldown bookkeeping.
        self.red_launchers = RedLauncherFleet()
        self.world.transition(MatchPhase.RUNNING)
        self._cum_reward = 0.0
        return self._encode_obs(), {}

    # ------------------------------------------------------------------
    def step(self, action):
        action = np.asarray(action, dtype=np.int64).reshape(-1)
        # Apply Red action first (spawn or hold). Deducts red_budget
        # inside on success; returns the spec cost in $M for the
        # decision-level cost penalty.
        spawned, spec_cost_M = self._apply_action(action)

        event_reward = 0.0
        for _ in range(DECISION_EVERY):
            self.world.events = []
            self.blue.step(self.world.t, self.world)
            # No RedLauncherFleet.tick() — fleet is ammo-less (see
            # launcher.RedLauncher docstring).
            self.world.step(DT)
            event_reward += self._reward_from_events(self.world.events)
            self.world.prune_dead()
            if self._winner() is not None:
                break
            if self.world.t >= self._episode_time_limit:
                break

        # Decision-level cost penalty is applied once per spawn
        # (spec_cost_M = 0.0 on hold). Mirrors Boyu's Blue shaping
        # structure: event-driven dense reward plus a per-decision
        # efficiency term.
        reward = event_reward - spec_cost_M

        terminated = self._winner() is not None
        truncated = (not terminated) and self.world.t >= self._episode_time_limit

        if terminated:
            w = self._winner()
            if w == "red":
                reward += 100.0
            elif w == "blue":
                reward -= 100.0

        self._cum_reward += reward
        info = {
            "winner": self._winner(),
            "sim_t": self.world.t,
            "n_spawns": 1 if spawned else 0,
            "red_budget": self.world.red_budget,
            "blue_budget": self.world.blue_budget,
            "site_hp_total": sum(s.hp for s in sites_module.SOUTH_SITES),
            "cum_reward": self._cum_reward,
        }
        return self._encode_obs(), float(reward), terminated, truncated, info

    # ------------------------------------------------------------------
    def _winner(self) -> Optional[str]:
        # Red wins when any military site's HP is depleted.
        for site in sites_module.SOUTH_SITES:
            if site.hp <= 0:
                return "red"
        # Blue wins when Red is priced out of spawning anything AND
        # there are no live Red threats left on the board. Mirrors the
        # future-ready win path that Scenario.winner gates on (see
        # world.py M-TIER3-RED-BUDGET docstring).
        cheapest = min(spec.usd_cost for spec in THREAT_SPECS.values())
        red_stuck = self.world.red_budget < cheapest
        no_threats = all(not t.state.alive for t in self.world.threats.values())
        if red_stuck and no_threats:
            return "blue"
        return None

    def _alive_threats(self) -> List:
        return [t for t in self.world.threats.values() if t.state.alive][:MAX_THREATS]

    def _alive_interceptors(self) -> List:
        return [
            i for i in self.world.interceptors.values() if i.state.alive
        ][:MAX_INTERCEPTORS]

    # ------------------------------------------------------------------
    def _apply_action(self, action: np.ndarray) -> tuple:
        """Execute the Red decision. Returns (spawned, spec_cost_M).

        * `spawned` is True iff a threat entered the world this call.
        * `spec_cost_M` is the spawn cost in $M (0.0 on hold or failed
          spawn). Caller uses it as the decision-level reward penalty.
        """
        kind_idx = int(action[0])
        site_idx = int(action[1]) if action.shape[0] > 1 else 0
        if kind_idx == 0:
            return False, 0.0
        if kind_idx < 0 or kind_idx >= N_RED_KINDS:
            return False, 0.0
        kind = RED_ACTION_KINDS[kind_idx]
        spec = THREAT_SPECS[kind]
        if self.world.red_budget < spec.usd_cost:
            return False, 0.0

        sites_list = sites_module.SOUTH_SITES
        if not sites_list:
            return False, 0.0
        target_site = sites_list[site_idx % len(sites_list)]
        target_xy = target_site.pos
        target_site_id = target_site.id

        spawn_pos = self._pick_spawn(kind)
        if spawn_pos is None:
            # No launcher of this kind available — agent shouldn't be
            # able to pick it (action mask gates), but defensive.
            return False, 0.0
        try:
            if kind == ThreatType.CRUISE_SUB:
                wps = self._build_cruise_waypoints(spawn_pos, target_xy)
                self.world.spawn_threat(
                    kind, spawn_pos, target_xy,
                    intermediate_waypoints=wps,
                    target_site_id=target_site_id,
                )
            else:
                self.world.spawn_threat(
                    kind, spawn_pos, target_xy,
                    target_site_id=target_site_id,
                )
        except ValueError:
            # W14 spawn-location contract rejected the coord. Treat as
            # a no-op so a mis-configured sampler doesn't crash the
            # episode. Budget is not deducted.
            return False, 0.0

        self.world.red_budget = max(0, self.world.red_budget - spec.usd_cost)
        return True, spec.usd_cost / 1e6

    def _pick_spawn(self, kind: ThreatType) -> Optional[tuple]:
        """Pick (x, y, z) for a Red threat of this kind.

        Drone / cruise use the Red launcher fleet's round-robin position
        picker (matches RedAI's visible-launcher idiom). Ballistic /
        HGV use the strategic far-north strip sampler from red_ai.
        """
        if kind in (ThreatType.DRONE, ThreatType.CRUISE_SUB):
            pos = self.red_launchers.next_pos(kind)
            if pos is None:
                return None
            x, y = pos
            if kind == ThreatType.DRONE:
                z = float(self.rng.uniform(*DRONE_ALT_RANGE))
            else:
                z = float(self.rng.uniform(*CRUISE_ALT_RANGE))
            return (x, y, z)
        if kind == ThreatType.BALLISTIC:
            x = float(self.rng.uniform(0.0, ARENA_X))
            y = float(self.rng.uniform(*STRATEGIC_Y_BAND))
            z = max(BALLISTIC_MIN_Z, float(self.rng.uniform(*BALLISTIC_ALT_RANGE)))
            return (x, y, z)
        if kind == ThreatType.HGV:
            x = float(self.rng.uniform(0.0, ARENA_X))
            y = float(self.rng.uniform(*STRATEGIC_Y_BAND))
            z = max(HGV_MIN_Z, float(self.rng.uniform(*HGV_ALT_RANGE)))
            return (x, y, z)
        return None

    def _build_cruise_waypoints(self, spawn_xyz, target_xy) -> List[tuple]:
        """Port of red_ai._build_cruise_waypoints — uses env-local rng so
        reset(seed=...) is reproducible."""
        sx, sy, sz = spawn_xyz
        tx, ty = target_xy
        n = int(self.rng.integers(1, 3))
        progress = sorted(float(self.rng.uniform(0.30, 0.70)) for _ in range(n))
        side = 1.0 if self.rng.random() < 0.5 else -1.0
        wps: List[tuple] = []
        for i, p in enumerate(progress):
            bx = sx + (tx - sx) * p
            by = sy + (ty - sy) * p
            offset_mag = float(self.rng.uniform(5_000.0, 20_000.0))
            dx = tx - sx
            dy = ty - sy
            norm = float(np.sqrt(dx * dx + dy * dy)) or 1.0
            px = -dy / norm
            py = dx / norm
            s = side * (1.0 if i % 2 == 0 else -1.0)
            wx = bx + px * offset_mag * s
            wy = by + py * offset_mag * s
            wps.append((wx, wy, sz))
        return wps

    # ------------------------------------------------------------------
    def _reward_from_events(self, events: List[dict]) -> float:
        """Per-tick dense shaping. Red's objective is to damage Blue
        sites; events drive the reward signal. Sign-flipped from
        env.py._reward_from_events (Blue's event handler).
        """
        r = 0.0
        for ev in events:
            et = ev.get("type")
            if et == "leak":
                # Red scored on a Blue site. Mirror magnitude of Boyu's
                # Blue penalty (-2.0 * dmg) → Red reward +2.0 * dmg.
                dmg = ev.get("damage", 0)
                r += float(dmg) * 2.0
            elif et == "intercept":
                # Red threat was killed in flight — the threat was
                # already paid for at spawn time; the intercept event
                # adds an additional cost-scaled penalty so the agent
                # learns to avoid spawning into obvious engagement
                # windows.
                tid = ev.get("threat")
                threat = self.world.threats.get(tid) if tid is not None else None
                if threat is not None:
                    try:
                        spec = THREAT_SPECS[ThreatType(threat.state.kind)]
                        r -= spec.usd_cost / 1e6
                    except (KeyError, ValueError):
                        r -= 1.0
                else:
                    r -= 1.0
            elif et == "ground_crash" and ev.get("threat") is not None:
                # Red threat crashed without hitting a site. Small
                # penalty to discourage spawning into dead-end
                # trajectories. Gated on 'threat' key so interceptor
                # ground_crash events (same event type) don't count.
                r -= 0.2
        return r

    # ------------------------------------------------------------------
    def action_masks(self) -> np.ndarray:
        """Public API for sb3_contrib.ActionMasker. Returns the flat
        marginal mask, shape (N_RED_KINDS + n_sites,), dtype int8."""
        return self._build_action_mask()

    def _build_action_mask(self) -> np.ndarray:
        """Component-wise marginal mask for MultiDiscrete([5, n_sites]).

        Layout:
          mask[0:N_RED_KINDS]              = kind mask
          mask[N_RED_KINDS:N_RED_KINDS+n]  = site mask (always all-ones)

        Total length = sum(action_space.nvec) = N_RED_KINDS + n_sites.
        Hold (kind=0) is always legal. Non-hold kinds are legal iff
        Red can afford the spec cost AND a spawn path exists
        (drone/cruise need a launcher for that kind; strategic kinds
        always have the far-north strip).
        """
        n_sites = self._n_sites
        mask = np.zeros(N_RED_KINDS + n_sites, dtype=np.int8)
        mask[0] = 1  # hold
        budget = self.world.red_budget if self.world is not None else 0
        for k_idx in range(1, N_RED_KINDS):
            kind = RED_ACTION_KINDS[k_idx]
            spec = THREAT_SPECS[kind]
            if budget < spec.usd_cost:
                continue
            if kind in (ThreatType.DRONE, ThreatType.CRUISE_SUB):
                if not self.red_launchers.positions_for(kind):
                    continue
            mask[k_idx] = 1
        # Site dim: every site is a valid aim point regardless of kind.
        mask[N_RED_KINDS:N_RED_KINDS + n_sites] = 1
        return mask

    # ------------------------------------------------------------------
    def _encode_obs(self) -> dict:
        """Omniscient Dict observation — same shape + fields as Blue env.

        Adapted from rl.env.MissileInterceptEnv._encode_obs:
        `self.blue.launchers` replaces `self.fleet`; other logic is
        identical. Kept as a method (not imported from env.py) because
        it references `self`-bound fleet / world state and the Blue env
        class hierarchy doesn't support the substitution cleanly.
        """
        threats = self._alive_threats()
        launchers = self.blue.launchers.launchers[:MAX_LAUNCHERS]
        interceptors = self._alive_interceptors()
        sites = sites_module.SOUTH_SITES[:MAX_SITES]
        t_now = self.world.t

        in_flight_by_kind = {k: 0 for k in INT_KIND_ORDER}
        for inter in interceptors:
            try:
                k = InterceptorType(inter.state.kind)
                in_flight_by_kind[k] = in_flight_by_kind.get(k, 0) + 1
            except ValueError:
                pass

        # --- Threats ---
        t_arr = np.zeros((MAX_THREATS, THREAT_FEATURES), dtype=np.float32)
        t_mask = np.zeros(MAX_THREATS, dtype=np.int8)
        for i, th in enumerate(threats):
            p, v = th.state.pos, th.state.vel
            try:
                k_idx = THREAT_KIND_ORDER.index(ThreatType(th.state.kind))
            except ValueError:
                k_idx = 0
            t_arr[i, 0] = float(p[0]) / POS_SCALE
            t_arr[i, 1] = float(p[1]) / POS_SCALE
            t_arr[i, 2] = float(p[2]) / POS_SCALE
            t_arr[i, 3] = float(v[0]) / VEL_SCALE
            t_arr[i, 4] = float(v[1]) / VEL_SCALE
            t_arr[i, 5] = float(v[2]) / VEL_SCALE
            t_arr[i, 6:6 + N_THREAT_KINDS] = _onehot(k_idx, N_THREAT_KINDS)
            hp_max = max(1, th.state.hp_max)
            t_arr[i, 6 + N_THREAT_KINDS] = th.state.hp / hp_max
            t_arr[i, 7 + N_THREAT_KINDS] = (t_now - th.state.spawn_t) / TIME_SCALE
            t_mask[i] = 1

        # --- Launchers (Blue) ---
        l_arr = np.zeros((MAX_LAUNCHERS, LAUNCHER_FEATURES), dtype=np.float32)
        l_mask = np.zeros(MAX_LAUNCHERS, dtype=np.int8)
        for i, lch in enumerate(launchers):
            try:
                k_idx = INT_KIND_ORDER.index(lch.kind)
            except ValueError:
                k_idx = 0
            cd_left = max(0.0, lch.inter_shot_cd - (t_now - lch.last_shot_t))
            reload_left = lch.reload_remaining(t_now)
            mag = max(1, lch.magazine_capacity)
            l_arr[i, 0] = float(lch.pos[0]) / POS_SCALE
            l_arr[i, 1] = float(lch.pos[1]) / POS_SCALE
            l_arr[i, 2:2 + N_INT_KINDS] = _onehot(k_idx, N_INT_KINDS)
            l_arr[i, 2 + N_INT_KINDS] = lch.current_ammo / mag
            l_arr[i, 3 + N_INT_KINDS] = cd_left / 10.0
            l_arr[i, 4 + N_INT_KINDS] = reload_left / 180.0
            l_arr[i, 5 + N_INT_KINDS] = in_flight_by_kind.get(lch.kind, 0) / 10.0
            l_mask[i] = 1

        # --- Interceptors ---
        i_arr = np.zeros((MAX_INTERCEPTORS, INTERCEPTOR_FEATURES), dtype=np.float32)
        i_mask = np.zeros(MAX_INTERCEPTORS, dtype=np.int8)
        threat_id_to_slot = {th.state.id: idx for idx, th in enumerate(threats)}
        for i, inter in enumerate(interceptors):
            p, v = inter.state.pos, inter.state.vel
            try:
                k_idx = INT_KIND_ORDER.index(InterceptorType(inter.state.kind))
            except ValueError:
                k_idx = 0
            fuel_total = max(1e-3, inter.spec.fuel_s)
            fuel_left = max(0.0, inter.spec.fuel_s - (t_now - inter.launched_t))
            t_slot = threat_id_to_slot.get(inter.target_id, -1)
            i_arr[i, 0] = float(p[0]) / POS_SCALE
            i_arr[i, 1] = float(p[1]) / POS_SCALE
            i_arr[i, 2] = float(p[2]) / POS_SCALE
            i_arr[i, 3] = float(v[0]) / VEL_SCALE
            i_arr[i, 4] = float(v[1]) / VEL_SCALE
            i_arr[i, 5] = float(v[2]) / VEL_SCALE
            i_arr[i, 6:6 + N_INT_KINDS] = _onehot(k_idx, N_INT_KINDS)
            i_arr[i, 6 + N_INT_KINDS] = fuel_left / fuel_total
            i_arr[i, 7 + N_INT_KINDS] = (t_slot + 1) / (MAX_THREATS + 1)
            i_mask[i] = 1

        # --- Sites ---
        s_arr = np.zeros((MAX_SITES, SITE_FEATURES), dtype=np.float32)
        s_mask = np.zeros(MAX_SITES, dtype=np.int8)
        for i, site in enumerate(sites):
            try:
                sub_idx = SITE_SUBTYPE_ORDER.index(site.subtype)
            except ValueError:
                sub_idx = 3
            hp_max = max(1, site.hp_max)
            s_arr[i, 0] = float(site.pos[0]) / POS_SCALE
            s_arr[i, 1] = float(site.pos[1]) / POS_SCALE
            s_arr[i, 2:2 + N_SITE_SUBTYPES] = _onehot(sub_idx, N_SITE_SUBTYPES)
            s_arr[i, 2 + N_SITE_SUBTYPES] = site.hp / hp_max
            s_mask[i] = 1

        # --- Global ---
        g_arr = np.zeros(GLOBAL_FEATURES, dtype=np.float32)
        g_arr[0] = t_now / TIME_SCALE
        g_arr[1] = self.world.blue_budget / BUDGET_SCALE
        g_arr[2] = self.world.red_budget / BUDGET_SCALE
        try:
            phase_idx = PHASE_ORDER.index(self.world.phase)
        except ValueError:
            phase_idx = 0
        g_arr[3:3 + N_PHASES] = _onehot(phase_idx, N_PHASES)

        return {
            "threats": t_arr,
            "threats_mask": t_mask,
            "launchers": l_arr,
            "launchers_mask": l_mask,
            "interceptors": i_arr,
            "interceptors_mask": i_mask,
            "sites": s_arr,
            "sites_mask": s_mask,
            "global": g_arr,
            "action_mask": self._build_action_mask(),
        }
