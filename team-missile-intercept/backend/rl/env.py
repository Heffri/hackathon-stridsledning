"""Gymnasium environment — Blue-side RL wrapper.

Agent controls Blue firing decisions at every decision tick:
for each ready Blue launcher, pick a visible Red threat to fire at
(or hold). Engagement mode = spec default. Guidance = existing PN.
Opponent = rule-based RedAI.

Decision cadence: every DECISION_EVERY sim ticks (DT=0.05s → 0.5s per
decision). Episode truncates at MAX_EPISODE_SIM_TIME to keep rollouts
bounded (default matches run 1700-1900s sim).

Observation (dict): padded tensors + boolean masks for variable-count
entity sets. Action: MultiDiscrete([MAX_THREATS+1] * MAX_LAUNCHERS)
where index MAX_THREATS means "hold fire". Invalid actions masked via
`action_mask` in obs — use MaskablePPO to respect it.
"""
from __future__ import annotations

import random
from typing import List, Optional

import numpy as np
import gymnasium as gym
from gymnasium import spaces

from sim import sites as sites_module
from sim.config import (
    BLUE_BUDGET_START,
    DT,
    LAUNCH_RANGE_MARGIN,
    RED_BUDGET_START,
)
from sim.launcher import LauncherFleet
from sim.red_ai import RedAI, build_demo_waves
from sim.types import (
    INTERCEPTOR_SPECS,
    InterceptorType,
    MatchPhase,
    ThreatType,
)
from sim.world import World


# --- Fixed shape caps (pad + mask for variable entity counts) ---
MAX_THREATS = 30
MAX_LAUNCHERS = 15
MAX_INTERCEPTORS = 40
MAX_SITES = 10

# Agent decides every N sim ticks. 10 ticks = 0.5s sim per decision.
DECISION_EVERY = 10

# Hard cap on episode sim time (seconds). Default matches run 1700-1900s;
# training uses shorter episodes for sample efficiency.
MAX_EPISODE_SIM_TIME = 600.0

# --- Normalization scales (keep obs tensor O(1)) ---
POS_SCALE = 1e5        # 100 km reference
VEL_SCALE = 2000.0     # Mach-ish
HP_SCALE = 100.0
BUDGET_SCALE = 1.2e8   # $120M
TIME_SCALE = MAX_EPISODE_SIM_TIME

# --- Kind encodings (fixed index ordering) ---
THREAT_KIND_ORDER: List[ThreatType] = [
    ThreatType.DRONE,
    ThreatType.CRUISE_SUB,
    ThreatType.BALLISTIC,
    ThreatType.HGV,
]
INT_KIND_ORDER: List[InterceptorType] = [
    InterceptorType.CIWS,
    InterceptorType.SHORT_SAM,
    InterceptorType.IRIS_T_SLS,
    InterceptorType.MED_SAM,
    InterceptorType.LONG_SAM,
    InterceptorType.HIT_TO_KILL,
]
SITE_SUBTYPE_ORDER = ["air_base", "capital", "major_city", "base"]
PHASE_ORDER = [MatchPhase.SETUP, MatchPhase.RUNNING, MatchPhase.PAUSED, MatchPhase.FINISHED]

N_THREAT_KINDS = len(THREAT_KIND_ORDER)
N_INT_KINDS = len(INT_KIND_ORDER)
N_SITE_SUBTYPES = len(SITE_SUBTYPE_ORDER)
N_PHASES = len(PHASE_ORDER)

# Per-entity feature widths
# threats: [x, y, z, vx, vy, vz, kind_onehot(4), hp/max, time_since_spawn] = 12
THREAT_FEATURES = 6 + N_THREAT_KINDS + 2
# launchers: [x, y, kind_onehot(6), ammo/mag, cooldown_norm, reloading, in_flight_norm] = 12
LAUNCHER_FEATURES = 2 + N_INT_KINDS + 4
# interceptors: [x, y, z, vx, vy, vz, kind_onehot(6), fuel_remaining_norm, target_idx_norm] = 14
INTERCEPTOR_FEATURES = 6 + N_INT_KINDS + 2
# sites: [x, y, subtype_onehot(4), hp/max] = 7
SITE_FEATURES = 2 + N_SITE_SUBTYPES + 1
# global: [sim_t, blue_budget, red_budget, phase_onehot(4)] = 7
GLOBAL_FEATURES = 3 + N_PHASES


def _onehot(idx: int, n: int) -> np.ndarray:
    v = np.zeros(n, dtype=np.float32)
    if 0 <= idx < n:
        v[idx] = 1.0
    return v


class MissileInterceptEnv(gym.Env):
    """Blue-side Gym env. See module docstring for agent contract."""

    metadata = {"render_modes": []}

    def __init__(
        self,
        seed: Optional[int] = None,
        episode_time_limit: float = MAX_EPISODE_SIM_TIME,
        layouts_pool: Optional[List[dict]] = None,
        red_mode: str = "default",
        red_mode_pool: Optional[List[str]] = None,
        blue_budget_start: Optional[int] = None,
        red_budget_start: Optional[int] = None,
    ):
        super().__init__()
        self._seed = seed
        self._episode_time_limit = episode_time_limit
        self._build_spaces()
        self.world: Optional[World] = None
        self.fleet: Optional[LauncherFleet] = None
        self.red = None
        # Domain-randomization pool of Blue launcher layouts. Each entry
        # is a dict with at least `roster` (kind->list[[x,y],...]) and
        # optionally `slot` (short id for logging). None disables pool
        # sampling — fleet is built from config.BLUE_LAUNCHER_POSITIONS.
        self._layouts_pool = layouts_pool
        self._red_mode = red_mode
        # Optional per-episode Red-mode sampling pool. When set, each
        # reset() picks one entry uniformly and instantiates Red from
        # it — letting training mix ScriptedRedAI and rule RedAI in the
        # same run so the policy sees both distributions. None disables
        # the pool and `red_mode` (single value) is used.
        # Accepted values: "scripted" (→ ScriptedRedAI),
        # "rule" / "default" (→ RedAI(build_demo_waves())).
        self._red_mode_pool = list(red_mode_pool) if red_mode_pool else None
        self._blue_budget_start = blue_budget_start
        self._red_budget_start = red_budget_start
        self._rng_layout_pool = np.random.default_rng(seed)
        self._last_sampled_slot: Optional[str] = None
        self._last_sampled_red_mode: Optional[str] = None
        self._episode_count: int = 0
        self._red_rng = random.Random(seed)

    def _build_spaces(self):
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
            "action_mask": spaces.Box(0, 1, (MAX_LAUNCHERS, MAX_THREATS + 1), dtype=np.int8),
        })
        self.action_space = spaces.MultiDiscrete([MAX_THREATS + 1] * MAX_LAUNCHERS)

    # ------------------------------------------------------------------
    def reset(self, seed: Optional[int] = None, options=None):
        super().reset(seed=seed)
        if seed is not None:
            self._seed = seed
            self._red_rng = random.Random(seed)
        sites_module.reset_leaks()
        self.world = World()
        if self._blue_budget_start is not None:
            self.world.blue_budget = int(self._blue_budget_start)
            self.world.blue_budget_max = int(self._blue_budget_start)
        if self._red_budget_start is not None:
            self.world.red_budget = int(self._red_budget_start)
            self.world.red_budget_max = int(self._red_budget_start)
        override = self._sample_layout_override()
        self.fleet = (
            LauncherFleet(positions=override) if override is not None
            else LauncherFleet()
        )
        # Pick Red mode — pool wins if set, else fall back to single flag.
        if self._red_mode_pool:
            red_mode = self._red_rng.choice(self._red_mode_pool)
        else:
            red_mode = self._red_mode
        self._last_sampled_red_mode = red_mode
        if red_mode == "scripted":
            from sim.red_ai import ScriptedRedAI
            self.red = ScriptedRedAI(None)
        else:
            # "rule" / "default" / anything else → rule-based RedAI.
            self.red = RedAI(build_demo_waves())
        self.world.transition(MatchPhase.RUNNING)
        self._cum_reward = 0.0
        # Per-kind fire counter, reset each episode. Consumed by
        # per_layout_eval.py via the `info` dict so the 6-cell grid can
        # report CIWS / RBS-70 participation (a key demo requirement).
        self._per_kind_fires: dict = {k.value: 0 for k in INT_KIND_ORDER}
        self._episode_count += 1
        # Bug 3 diag — confirm on-episode-1 that budget overrides actually
        # took effect. Cheap one-shot per-env-process print; the prompt's
        # complaint was that last night's worker silently used config
        # defaults instead of the spec's 200M / 150M.
        if self._episode_count == 1:
            print(
                f"[env] budgets: blue={self.world.blue_budget_max:,} "
                f"red={self.world.red_budget_max:,} red_mode={red_mode}",
                flush=True,
            )
        if self._layouts_pool and self._episode_count % 50 == 1:
            print(
                f"[env] episode {self._episode_count} starting with "
                f"layout slot={self._last_sampled_slot} red_mode={red_mode}",
                flush=True,
            )
        return self._encode_obs(), {}

    # ------------------------------------------------------------------
    def _sample_layout_override(self):
        """Sample one layout from `self._layouts_pool` and return its
        roster as a dict-of-tuples ready for LauncherFleet(positions=...).
        Returns None if pool is unset. Updates `self._last_sampled_slot`.
        """
        if not self._layouts_pool:
            self._last_sampled_slot = None
            return None
        idx = int(self._rng_layout_pool.integers(0, len(self._layouts_pool)))
        chosen = self._layouts_pool[idx]
        roster = chosen.get("roster", {})
        override = {
            kind: [tuple(pos) for pos in positions]
            for kind, positions in roster.items()
        }
        self._last_sampled_slot = chosen.get("slot", "?")
        return override

    # ------------------------------------------------------------------
    def step(self, action):
        action = np.asarray(action, dtype=np.int64).reshape(-1)
        # Snapshot before-state for reward diffing
        prev_blue_budget = self.world.blue_budget
        prev_site_hp = sum(s.hp for s in sites_module.SOUTH_SITES)
        prev_threats_intercepted = self.world.intercepts

        # Apply agent action (fire commands)
        n_fires = self._apply_action(action)

        # Advance sim for DECISION_EVERY ticks; rule Red AI + physics run normally.
        # Reward is computed from events BEFORE prune_dead so intercept events
        # can still look up the threat's kind for value-scaled credit.
        event_reward = 0.0
        for _ in range(DECISION_EVERY):
            self.world.events = []
            self.red.step(self.world.t, self.world)
            self.fleet.tick(self.world.t)  # reload timers
            self.world.step(DT)
            event_reward += self._reward_from_events(self.world.events)
            self.world.prune_dead()
            if self._winner() is not None:
                break
            if self.world.t >= self._episode_time_limit:
                break

        # Additive per-decision penalties. No survival bonus — it creates
        # a stall incentive (agent learns to drag match out past truncation
        # instead of winning). Terminal +100 win bonus is the horizon-
        # shaping signal.
        spent = max(0, prev_blue_budget - self.world.blue_budget)
        reward = event_reward - spent / 1e6 * 0.05  # weak efficiency penalty per $M spent

        terminated = self._winner() is not None
        truncated = (not terminated) and self.world.t >= self._episode_time_limit

        if terminated:
            w = self._winner()
            if w == "blue":
                reward += 100.0
            elif w == "red":
                reward -= 100.0
            # draw: 0

        self._cum_reward += reward
        info = {
            "winner": self._winner(),
            "sim_t": self.world.t,
            "n_fires": n_fires,
            "blue_budget": self.world.blue_budget,
            "site_hp_total": sum(s.hp for s in sites_module.SOUTH_SITES),
            "cum_reward": self._cum_reward,
            "per_kind_fires": dict(self._per_kind_fires),
            "red_mode": self._last_sampled_red_mode,
        }
        return self._encode_obs(), float(reward), terminated, truncated, info

    # ------------------------------------------------------------------
    def _winner(self) -> Optional[str]:
        # Mirrors Scenario.winner's military-only rule (Issue #9). Red wins
        # only when every military site (subtype in {'base','air_base'}) is
        # at HP 0; city / capital HP doesn't count. Pre-fix this function
        # iterated every site and returned "red" on the first HP<=0, which
        # (a) would fire on cities the winner spec explicitly excludes and
        # (b) ended ScriptedRed episodes after ONE base died, blocking the
        # "Blue holds 2/3 sites" outcomes from ever scoring as Blue wins.
        military = [
            s for s in sites_module.SOUTH_SITES
            if s.subtype in ("base", "air_base")
        ]
        if military and all(s.hp <= 0 for s in military):
            return "red"
        red_done = self.red.done or self.world.red_budget <= 0
        no_threats = all(not t.state.alive for t in self.world.threats.values())
        if red_done and no_threats:
            return "blue"
        if self.world.t >= self._episode_time_limit:
            return None  # truncation, not terminal win
        return None

    def _alive_threats(self) -> List:
        return [t for t in self.world.threats.values() if t.state.alive][:MAX_THREATS]

    def _alive_interceptors(self) -> List:
        return [i for i in self.world.interceptors.values() if i.state.alive][:MAX_INTERCEPTORS]

    # ------------------------------------------------------------------
    def _apply_action(self, action: np.ndarray) -> int:
        """Execute fire commands for each launcher.

        action[i] in [0, MAX_THREATS]: MAX_THREATS = hold. Else fire launcher i at
        threat-slot action[i]. Silently skips invalid fires (out of range,
        empty launcher, dead threat, pad slot); the action mask should
        have prevented these but we defensively re-check.
        """
        launchers = self.fleet.launchers
        threats = self._alive_threats()
        n_fires = 0
        for l_idx, a in enumerate(action):
            if l_idx >= len(launchers):
                break
            if a >= MAX_THREATS:
                continue  # hold
            if a >= len(threats):
                continue  # targeted pad slot
            lch = launchers[l_idx]
            if lch.reloading or not lch.can_fire(self.world.t):
                continue
            threat = threats[a]
            if not threat.state.alive:
                continue
            spec = INTERCEPTOR_SPECS[lch.kind]
            t_pos = threat.state.pos
            dx = float(t_pos[0] - lch.pos[0])
            dy = float(t_pos[1] - lch.pos[1])
            dz = float(t_pos[2])
            dist = (dx * dx + dy * dy + dz * dz) ** 0.5
            if dist > spec.max_range * LAUNCH_RANGE_MARGIN:
                continue
            mode = lch.fire(self.world.t)
            self.world.spawn_interceptor(
                lch.kind,
                (lch.pos[0], lch.pos[1], 0.0),
                (dx, dy, dz),
                threat.state.id,
                mode,
            )
            self.world.blue_budget = max(0, self.world.blue_budget - spec.usd_cost)
            n_fires += 1
            # Per-kind fire counter (for per_layout_eval).
            kind_key = lch.kind.value if hasattr(lch.kind, "value") else str(lch.kind)
            self._per_kind_fires[kind_key] = self._per_kind_fires.get(kind_key, 0) + 1
        return n_fires

    # ------------------------------------------------------------------
    def _reward_from_events(self, events: List[dict]) -> float:
        """Per-tick dense shaping based on world events list.

        Caller must invoke this BEFORE `world.prune_dead` so intercept
        events can still look up the dead threat's kind in
        `world.threats` for value-scaled credit.
        """
        r = 0.0
        for ev in events:
            et = ev.get("type")
            if et == "intercept":
                # Threat killed. Scale by the threat's usd_cost so the
                # agent prefers killing expensive / dangerous threats.
                tid = ev.get("threat")
                threat = self.world.threats.get(tid) if tid is not None else None
                if threat is not None:
                    try:
                        spec = self._threat_spec_by_str(threat.state.kind)
                        r += spec.usd_cost / 1e6
                    except KeyError:
                        r += 1.0
                else:
                    r += 1.0
            elif et == "leak":
                # Site leak. Heavily weighted by leak damage.
                # Aggressive-retrain B path (2026-04-25): tiered penalty
                # by threat kind so ballistic/HGV leaks dominate the
                # gradient — forces policy to try PAC-3 even at the cost
                # of wasted shots, vs. the prior flat ×2 that let the
                # policy "accept" ballistic/HGV leaks as cheaper than
                # PAC-3 launch cost.
                dmg = ev.get("damage", 0)
                kind = ev.get("kind", "")
                if kind == "hgv":
                    r -= float(dmg) * 8.0
                elif kind == "ballistic":
                    r -= float(dmg) * 6.0
                elif kind == "cruise_sub":
                    r -= float(dmg) * 3.0
                else:  # drone or unknown
                    r -= float(dmg) * 2.0
            elif et == "ground_crash" and ev.get("threat") is not None:
                # Red threat crashed w/o hitting a site — small credit.
                # Gate on 'threat' key so interceptor ground crashes
                # (which share the 'ground_crash' event type) don't count.
                r += 0.2
        return r

    @staticmethod
    def _threat_spec_by_str(kind_str: str):
        from sim.types import THREAT_SPECS
        return THREAT_SPECS[ThreatType(kind_str)]

    # ------------------------------------------------------------------
    def _encode_obs(self) -> dict:
        threats = self._alive_threats()
        launchers = self.fleet.launchers[:MAX_LAUNCHERS]
        interceptors = self._alive_interceptors()
        sites = sites_module.SOUTH_SITES[:MAX_SITES]
        t_now = self.world.t

        # In-flight count per launcher kind
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

        # --- Launchers ---
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
            l_arr[i, 3 + N_INT_KINDS] = cd_left / 10.0  # ~10s reference
            l_arr[i, 4 + N_INT_KINDS] = reload_left / 180.0  # ~3min reference
            l_arr[i, 5 + N_INT_KINDS] = in_flight_by_kind.get(lch.kind, 0) / 10.0
            l_mask[i] = 1

        # --- Interceptors ---
        i_arr = np.zeros((MAX_INTERCEPTORS, INTERCEPTOR_FEATURES), dtype=np.float32)
        i_mask = np.zeros(MAX_INTERCEPTORS, dtype=np.int8)
        # Map target_id to its padded slot in threats array for the
        # interceptor's target_idx feature.
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
            i_arr[i, 7 + N_INT_KINDS] = (t_slot + 1) / (MAX_THREATS + 1)  # -1 → 0
            i_mask[i] = 1

        # --- Sites ---
        s_arr = np.zeros((MAX_SITES, SITE_FEATURES), dtype=np.float32)
        s_mask = np.zeros(MAX_SITES, dtype=np.int8)
        for i, site in enumerate(sites):
            try:
                sub_idx = SITE_SUBTYPE_ORDER.index(site.subtype)
            except ValueError:
                sub_idx = 3  # 'base' fallback
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

        # --- Action mask ---
        act_mask = self._build_action_mask(threats, launchers)

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
            "action_mask": act_mask,
        }

    # ------------------------------------------------------------------
    def _build_action_mask(self, threats, launchers) -> np.ndarray:
        """Return bool mask [MAX_LAUNCHERS, MAX_THREATS+1].

        Row l col c = True iff launcher l firing at threat slot c is legal.
        Col MAX_THREATS = hold fire, always True for live launchers (even
        when reloading — hold is a no-op).
        """
        mask = np.zeros((MAX_LAUNCHERS, MAX_THREATS + 1), dtype=np.int8)
        t_now = self.world.t
        for l_idx in range(MAX_LAUNCHERS):
            if l_idx >= len(launchers):
                # Pad launcher row: only hold is legal (prevents invalid
                # sample from MultiDiscrete). Using 1 for hold keeps the
                # categorical at least 1 valid option per row.
                mask[l_idx, MAX_THREATS] = 1
                continue
            lch = launchers[l_idx]
            mask[l_idx, MAX_THREATS] = 1  # hold always valid
            if lch.reloading or not lch.can_fire(t_now):
                continue  # only hold
            spec = INTERCEPTOR_SPECS[lch.kind]
            max_range = spec.max_range * LAUNCH_RANGE_MARGIN
            for t_idx, th in enumerate(threats):
                if t_idx >= MAX_THREATS:
                    break
                if not th.state.alive:
                    continue
                dx = float(th.state.pos[0] - lch.pos[0])
                dy = float(th.state.pos[1] - lch.pos[1])
                dz = float(th.state.pos[2])
                dist = (dx * dx + dy * dy + dz * dz) ** 0.5
                if dist <= max_range:
                    mask[l_idx, t_idx] = 1
        return mask
