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
    SITE_LEAK_DAMAGE,
)
from sim.launcher import LauncherFleet
from sim.red_ai import RedAI, build_demo_waves, build_training_waves
from sim.types import (
    INTERCEPTOR_SPECS,
    InterceptorType,
    MatchPhase,
    THREAT_SPECS,
    ThreatType,
)
from sim.world import World


# --- Fixed shape caps (pad + mask for variable entity counts) ---
# AOE 2026-04-24: bumped caps for ScriptedRedAI saturation + Slot C/D
# pools (C has 23 launchers, D has 19). Previous caps (30/15/40)
# clipped ~47 % of scripted-Red ticks on threats alone — Blue policy
# was blind to half the swarm by construction. Priority truncation
# below keeps the most urgent threats visible when we still exceed cap.
MAX_THREATS = 96
MAX_LAUNCHERS = 24
MAX_INTERCEPTORS = 128
MAX_SITES = 10

# Agent decides every N sim ticks. 10 ticks = 0.5s sim per decision.
DECISION_EVERY = 10

# 2026-04-22 audit: split RL horizon from live-server safety cap.
#   * `config.MAX_SIM_TIME = 3600s` remains the server/live safety net.
#   * `RL_MAX_EPISODE_SIM_TIME` is the default RL training / eval
#     horizon — long enough to cover observed match lengths under the
#     HGV3800 balance (~935s), short enough to keep rollout/eval
#     latency practical. Callers can override per-env via
#     `episode_time_limit=...`.
RL_MAX_EPISODE_SIM_TIME = 3000.0
MAX_EPISODE_SIM_TIME = RL_MAX_EPISODE_SIM_TIME  # back-compat alias

# --- Normalization scales (keep obs tensor O(1)) ---
POS_SCALE = 1e5        # 100 km reference
VEL_SCALE = 2000.0     # Mach-ish
HP_SCALE = 100.0
BUDGET_SCALE = 2.0e8   # $200M — AOE-era Blue budget cap
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

    # Cost-efficiency shaping. Per-intercept penalty applied in
    # `_reward_from_events` equals max(0, (interceptor_cost - threat_cost)
    # in $M) * COST_DIFF_WEIGHT. See comment block in the intercept branch
    # for calibration notes against the SITE_LEAK_DAMAGE*2 credit.
    # Tuned down from 2.0 (v5) to 1.0 (v6): v5 at 2.0 tied with random
    # baseline on hard scenarios — penalty was biting exploration too hard
    # when no cheap launcher was in range, so the agent learned to skip
    # shots rather than overpay. 1.0 still beats "prefer cheap" but lets
    # an overpriced kill remain net-positive enough to fire when it's the
    # only legal option.
    COST_DIFF_WEIGHT = 1.0

    VALID_RED_MODES = ("training_random", "demo_fixed", "trained", "pool", "scripted")

    def __init__(
        self,
        seed: Optional[int] = None,
        episode_time_limit: float = MAX_EPISODE_SIM_TIME,
        red_mode: str = "training_random",
        difficulty: str = "mixed",
        red_model_path: Optional[str] = None,
        red_deterministic: bool = False,
        red_pool_config: Optional[dict] = None,
        reward_shaping: Optional[dict] = None,
        blue_positions: Optional[dict] = None,
        blue_positions_pool: Optional[list] = None,
        scripted_config: Optional[dict] = None,
    ):
        super().__init__()
        if red_mode not in self.VALID_RED_MODES:
            raise ValueError(
                f"red_mode must be one of {self.VALID_RED_MODES}, got {red_mode!r}"
            )
        if red_mode == "trained" and not red_model_path:
            raise ValueError("red_mode='trained' requires red_model_path")
        if red_mode == "pool" and not red_pool_config:
            raise ValueError("red_mode='pool' requires red_pool_config")
        self._seed = seed
        self._episode_time_limit = episode_time_limit
        self._red_mode = red_mode
        self._difficulty = difficulty
        self._red_model_path = red_model_path
        self._red_deterministic = red_deterministic
        self._reward_shaping = reward_shaping or {}
        self._blue_positions = blue_positions
        # Layout pool: list of (positions_dict, weight, slot_label).
        # When set, reset() samples a roster per episode and overrides
        # any static `blue_positions`. None → use `blue_positions` or
        # config default, as before.
        self._blue_positions_pool = blue_positions_pool
        if blue_positions_pool:
            # Pre-compute sampling weights.
            self._pool_weights = np.array(
                [w for (_, w, _) in blue_positions_pool], dtype=np.float64
            )
            total = float(self._pool_weights.sum())
            if total <= 0.0:
                raise ValueError("blue_positions_pool weights sum to <= 0")
            self._pool_weights = self._pool_weights / total
        else:
            self._pool_weights = None
        self._last_layout_slot: Optional[str] = None
        # Scripted curriculum config: forwarded to ScriptedRedAI when
        # red_mode="scripted". None → use ScriptedRedAI defaults (full
        # 3×3×hgv behaviour).
        self._scripted_config = scripted_config or {}
        self._episode_count = 0
        self._last_red_name: Optional[str] = None
        self._red_pool = None
        if red_mode == "pool":
            from rl.red_pool import RedPool
            self._red_pool = RedPool(red_pool_config)
        self._build_spaces()
        self.world: Optional[World] = None
        self.fleet: Optional[LauncherFleet] = None
        self.red: Optional[RedAI] = None

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
        sites_module.reset_leaks()
        self.world = World()
        # 2026-04-22 audit: apply blue-roster base-cost deduction so
        # world.blue_budget reflects interceptor-only budget. Default
        # positions come from config if caller didn't override.
        from sim import config as sim_config
        from sim.blue_layout import apply_blue_layout_budget, validate_blue_layout
        # Per-episode RNG. Seed = base_seed XOR episode_count so successive
        # episodes in the same worker see different scenarios while staying
        # reproducible across runs. With seed=None we fall back to fresh
        # entropy (manual debugging).
        if self._seed is not None:
            red_seed = int(self._seed) ^ (self._episode_count * 0x9E3779B1)
            red_rng = np.random.default_rng(red_seed & 0xFFFFFFFF)
        else:
            red_rng = np.random.default_rng()
        # Layout selection: pool (per-episode sample) > static override >
        # config default. Pool RNG forks from the red_rng stream so both
        # are reproducible under the same env seed.
        if self._blue_positions_pool is not None:
            pool_rng = np.random.default_rng(red_rng.integers(0, 2**32))
            idx = int(pool_rng.choice(len(self._blue_positions_pool), p=self._pool_weights))
            positions, _w, slot_label = self._blue_positions_pool[idx]
            self._last_layout_slot = slot_label
        elif self._blue_positions is not None:
            positions = self._blue_positions
            self._last_layout_slot = None
        else:
            positions = sim_config.BLUE_LAUNCHER_POSITIONS
            self._last_layout_slot = None
        # Hard-fail on illegal / over-budget layouts. Mirror Scenario.
        validate_blue_layout(positions)
        apply_blue_layout_budget(self.world, positions)
        self.fleet = LauncherFleet(positions=positions)
        if self._red_mode == "pool":
            self.red, self._last_red_name = self._red_pool.sample(
                red_rng, self.fleet, episode_count=self._episode_count
            )
        elif self._red_mode == "trained":
            from rl.trained_red import TrainedRedAI
            self.red = TrainedRedAI(
                model_path=self._red_model_path,
                blue_fleet=self.fleet,
                rng=red_rng,
                deterministic=self._red_deterministic,
            )
            self._last_red_name = "trained"
        elif self._red_mode == "scripted":
            # ScriptedRedAI only reads `scenario.world` path-less; stores
            # the reference at construction but `.step(t, world)` takes
            # the world as an arg. A minimal shim with `.world` is enough.
            from sim.red_ai import ScriptedRedAI

            class _ScenarioShell:
                def __init__(self, world):
                    self.world = world

            self.red = ScriptedRedAI(
                _ScenarioShell(self.world), **self._scripted_config
            )
            self._last_red_name = "scripted"
        else:
            if self._red_mode == "demo_fixed":
                waves = build_demo_waves()
            else:
                waves = build_training_waves(red_rng, difficulty=self._difficulty)
            self.red = RedAI(waves, rng=red_rng)
            self._last_red_name = self._red_mode
        self.world.transition(MatchPhase.RUNNING)
        self._cum_reward = 0.0
        self._episode_count += 1
        alive_threats_total = sum(1 for t in self.world.threats.values() if t.state.alive)
        alive_launchers_total = len(self.fleet.launchers) if self.fleet is not None else 0
        info = {
            "red_name": self._last_red_name,
            "layout_slot": self._last_layout_slot,
            "alive_threats_total": alive_threats_total,
            "visible_threats": min(alive_threats_total, MAX_THREATS),
            "threats_truncated": max(0, alive_threats_total - MAX_THREATS),
            "alive_launchers_total": alive_launchers_total,
            "visible_launchers": min(alive_launchers_total, MAX_LAUNCHERS),
            "launchers_truncated": max(0, alive_launchers_total - MAX_LAUNCHERS),
        }
        return self._encode_obs(), info

    # ------------------------------------------------------------------
    def step(self, action):
        action = np.asarray(action, dtype=np.int64).reshape(-1)
        # Snapshot before-state for reward diffing
        prev_blue_budget = self.world.blue_budget
        prev_site_hp = sum(s.hp for s in sites_module.SOUTH_SITES)
        prev_threats_intercepted = self.world.intercepts

        # Apply agent action (fire commands). _apply_action emits "launch"
        # events into self.world.events — capture them BEFORE the inner
        # loop clears the list, otherwise Blue's own fires are invisible
        # to downstream diagnostics.
        self.world.events = []
        n_fires = self._apply_action(action)
        step_events: list = []
        for ev in self.world.events:
            ev_copy = dict(ev)
            ev_copy["_t"] = float(self.world.t)
            step_events.append(ev_copy)

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
            for ev in self.world.events:
                # Timestamp each event with current sim_t so downstream
                # diagnostics can reconstruct match timelines. World.step
                # already advanced t — sample after step, before prune.
                ev_copy = dict(ev)
                ev_copy["_t"] = float(self.world.t)
                step_events.append(ev_copy)
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

        # --- Optional reward shaping (config-gated, default off) ---
        # `reward_shaping` dict keys (all default 0.0):
        #   survival_per_decision   : +bonus per decision each site is alive
        #                             (stops "get-it-over-with" collapse at
        #                             short-episode losing runs — gives the
        #                             policy a gradient toward "delay the
        #                             breach even if you can't prevent it").
        #   early_intercept_bonus   : +multiplier on intercept events that
        #                             fire in first `early_intercept_window` s
        #                             (default window 60 s). Encourages
        #                             reacting early instead of waiting.
        #   hgv_intercept_bonus     : extra +reward per HGV / ballistic kill
        #                             on top of SITE_LEAK_DAMAGE credit.
        shaping = self._reward_shaping
        if shaping:
            if shaping.get("survival_per_decision", 0.0):
                alive_sites = sum(1 for s in sites_module.SOUTH_SITES if s.hp > 0)
                reward += float(shaping["survival_per_decision"]) * alive_sites
            early_bonus = float(shaping.get("early_intercept_bonus", 0.0))
            early_win = float(shaping.get("early_intercept_window", 60.0))
            hgv_bonus = float(shaping.get("hgv_intercept_bonus", 0.0))
            if early_bonus or hgv_bonus:
                for ev in step_events:
                    if ev.get("type") != "intercept":
                        continue
                    if early_bonus and ev.get("_t", 999) <= early_win:
                        reward += early_bonus
                    if hgv_bonus:
                        kind = None
                        # interceptor event has interceptor+threat id; look
                        # up threat kind via the alive-threats cache is slow
                        # here — instead read kind from the event's own
                        # payload if present (sim.world does not embed it).
                        # Fall back to alive-threats scan.
                        tid = ev.get("threat")
                        t = self.world.threats.get(tid) if tid is not None else None
                        if t is not None:
                            kind = t.state.kind
                        if kind in ("hgv", "ballistic"):
                            reward += hgv_bonus

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
        winner_str = self._winner()
        # `_winner` sets `_last_terminal_reason` as a side effect so the
        # info payload stays consistent with the Gym termination flag.
        # Override: truncation case is `winner=None` + reason="timeout".
        terminal_reason = getattr(self, "_last_terminal_reason", None)
        # Diagnostic counters: total alive entities, visible (post-cap)
        # count, and truncation count. `threats_truncated` > 0 means the
        # priority-sort keeps only MAX_THREATS of N alive threats for
        # the policy — pipeline health check for scripted-Red saturation.
        alive_threats_total = sum(
            1 for t in self.world.threats.values() if t.state.alive
        )
        alive_launchers_total = len(self.fleet.launchers) if self.fleet is not None else 0
        visible_threats = min(alive_threats_total, MAX_THREATS)
        visible_launchers = min(alive_launchers_total, MAX_LAUNCHERS)
        info = {
            "winner": winner_str,
            "terminal_reason": terminal_reason if (terminated or truncated) else None,
            "sim_t": self.world.t,
            "n_fires": n_fires,
            "blue_budget": self.world.blue_budget,
            "red_budget": self.world.red_budget,
            "site_hp_total": sum(s.hp for s in sites_module.SOUTH_SITES),
            "surviving_sites": sum(
                1 for s in sites_module.SOUTH_SITES
                if s.subtype in ("air_base", "base") and s.hp > 0
            ),
            "destroyed_sites": sum(
                1 for s in sites_module.SOUTH_SITES
                if s.subtype in ("air_base", "base") and s.hp <= 0
            ),
            "cum_reward": self._cum_reward,
            "red_name": self._last_red_name,
            "layout_slot": self._last_layout_slot,
            "events": step_events,
            # AOE 2026-04-24 diagnostic counters.
            "alive_threats_total": alive_threats_total,
            "visible_threats": visible_threats,
            "threats_truncated": max(0, alive_threats_total - MAX_THREATS),
            "alive_launchers_total": alive_launchers_total,
            "visible_launchers": visible_launchers,
            "launchers_truncated": max(0, alive_launchers_total - MAX_LAUNCHERS),
        }
        return self._encode_obs(), float(reward), terminated, truncated, info

    # ------------------------------------------------------------------
    def _winner(self) -> Optional[str]:
        # 2026-04-22 audit: delegate to shared win_conditions module
        # so env and Scenario can't drift apart. "draw" (timeout) is
        # translated to None on the Gym side so terminated=False and
        # truncated=True downstream. Actual terminal_reason is
        # exposed via info["terminal_reason"].
        from sim.win_conditions import compute_winner
        w, r = compute_winner(self.world, self.red, self._episode_time_limit)
        self._last_terminal_reason = r
        if w == "draw":
            return None
        return w

    # Danger weighting for threat-priority truncation (lower = higher
    # priority, so it sorts first). HGV gets 0 (most urgent), drone gets 3.
    _THREAT_DANGER_ORDER = {
        "hgv": 0,
        "ballistic": 1,
        "cruise_sub": 2,
        "drone": 3,
    }

    def _threat_priority_key(self, threat) -> tuple:
        """Sort key for threat priority truncation. Lower key = more
        urgent (= keep when slot-count exceeds MAX_THREATS).

        Primary: estimated time-to-site (ground-distance to target /
        cruise speed). Shorter ETA = more urgent.
        Secondary: danger rank (hgv > ballistic > cruise_sub > drone).
        Tertiary: 2D distance to target (closer = more urgent).
        """
        st = threat.state
        kind_str = st.kind if isinstance(st.kind, str) else getattr(st.kind, "value", str(st.kind))
        # Resolve target xy: prefer target_site lookup, fall back to
        # threat.target_xy if present.
        tx = ty = 0.0
        site = None
        if st.target_id is not None:
            for s in sites_module.SOUTH_SITES:
                if s.id == st.target_id:
                    site = s
                    break
        if site is not None:
            tx, ty = float(site.pos[0]), float(site.pos[1])
        else:
            wp = getattr(threat, "target_xy", None)
            if wp is not None:
                tx, ty = float(wp[0]), float(wp[1])
        px, py = float(st.pos[0]), float(st.pos[1])
        dx_g = px - tx
        dy_g = py - ty
        dist_to_target = (dx_g * dx_g + dy_g * dy_g) ** 0.5
        try:
            spec = THREAT_SPECS[ThreatType(kind_str)]
            speed = max(1.0, float(spec.cruise_speed))
        except (KeyError, ValueError):
            speed = 150.0
        eta = dist_to_target / speed
        danger = self._THREAT_DANGER_ORDER.get(kind_str, 9)
        return (eta, danger, dist_to_target)

    def _alive_threats(self) -> List:
        """All alive Red threats sorted by urgency, truncated to
        MAX_THREATS. When total alive > cap, the policy sees the most
        urgent slice instead of dict-insertion order."""
        alive = [t for t in self.world.threats.values() if t.state.alive]
        if len(alive) > MAX_THREATS:
            alive.sort(key=self._threat_priority_key)
            alive = alive[:MAX_THREATS]
        return alive

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
            # 2026-04-22 audit: affordability gate. Mask should have
            # filtered this out, but defensive re-check so the budget
            # stays a real constraint.
            if self.world.blue_budget < spec.usd_cost:
                continue
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
                launcher_pos=(lch.pos[0], lch.pos[1], 0.0),
                launcher_max_range_m=spec.max_range,
            )
            # 2026-04-22 audit: single strict deduct. Gate above
            # guarantees budget >= cost. The old clamp-to-zero deduct
            # below this line was merged with the gate in the audit —
            # keeping both would double-charge every fire.
            self.world.blue_budget -= spec.usd_cost
            n_fires += 1
        return n_fires

    # ------------------------------------------------------------------
    def _reward_from_events(self, events: List[dict]) -> float:
        """Per-tick dense shaping based on world events list.

        Caller must invoke this BEFORE `world.prune_dead` so intercept
        events can still look up the dead threat's kind in
        `world.threats` for value-scaled credit.

        AOE 2026-04-24: cost-diff penalty applies ONCE per
        interceptor/detonation, not once per secondary AOE kill, so a
        single SLM wiping a 4-drone cluster doesn't 4x-debit the
        interceptor cost. Kill credit (leak-damage * 2) still fires per
        victim — that's the reward for the multi-kill.
        """
        r = 0.0
        # Track interceptor ids we've already charged the overspend
        # penalty to this tick — prevents duplicate charges on AOE
        # multi-kills where the same interceptor id appears in several
        # 'intercept' events.
        cost_penalty_charged: set = set()
        for ev in events:
            et = ev.get("type")
            if et == "intercept":
                # Killing a threat is the symmetric inverse of letting it
                # leak: both branches use `SITE_LEAK_DAMAGE[kind] * 2` so
                # the policy sees +X for stopping a threat that would have
                # cost -X at the site. usd_cost-scaled rewards were ~333×
                # weaker than leak penalties for drones, producing a
                # defensive-only signal.
                tid = ev.get("threat")
                iid = ev.get("interceptor")
                threat = self.world.threats.get(tid) if tid is not None else None
                inter = self.world.interceptors.get(iid) if iid is not None else None
                if threat is not None:
                    dmg = SITE_LEAK_DAMAGE.get(threat.state.kind, 10)
                    r += float(dmg) * 2.0
                else:
                    r += 10.0
                # Over-spend penalty. Using a pricey interceptor on a
                # cheap threat (e.g. $4M PAC-3 on a $30K drone) is
                # obviously a bad trade even if it kills the target.
                # Scale linearly with the *positive* cost differential
                # in $M; zero when interceptor_cost <= threat_cost so
                # good trades aren't punished.
                # AOE dedup: only charge once per interceptor — secondary
                # AOE victims are bonus kills, not bonus cost.
                if (
                    inter is not None
                    and threat is not None
                    and iid not in cost_penalty_charged
                ):
                    try:
                        i_spec = INTERCEPTOR_SPECS[InterceptorType(inter.state.kind)]
                        t_spec = THREAT_SPECS[ThreatType(threat.state.kind)]
                        diff_m = max(0.0, (i_spec.usd_cost - t_spec.usd_cost) / 1e6)
                        r -= diff_m * self.COST_DIFF_WEIGHT
                        cost_penalty_charged.add(iid)
                    except (KeyError, ValueError):
                        pass
            elif et == "leak":
                # Site leak. Heavily weighted by leak damage.
                dmg = ev.get("damage", 0)
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
            # 2026-04-22 audit: budget gate. Shots the agent cannot
            # afford should never reach the policy — hold is the only
            # legal option when the budget is short.
            if self.world.blue_budget < spec.usd_cost:
                continue
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
