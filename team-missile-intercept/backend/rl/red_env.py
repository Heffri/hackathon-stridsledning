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

Reward sign convention (flipped vs Blue). All dense terms are
normalized against the game's starting budgets / total site HP so
magnitudes are comparable across reward components:

  * +10.0 × (site_damage / TOTAL_SITE_HP) per `leak` event. Wiping
    out the full defended side over an episode is worth ~+10 total;
    a single drone leak against a 100-HP site is ~+0.17, an HGV leak
    is ~+1.33.
  * -1.0 × (spawn_cost / RED_BUDGET_START) per successful spawn.
    Burning the full Red budget on spawns sums to ~-1.0. Single spawn
    is paid ONCE per threat lifecycle here — intercept events do NOT
    add a second deduction (the world's red_budget ledger also only
    charges at spawn time, so the reward matches reality).
  * +0.1 × (blue_spend_this_step / BLUE_BUDGET_START) — weak
    cost-exchange bonus when Blue burns interceptor budget reacting
    to Red's threats.
  * -0.2 per `ground_crash` event with a threat id — small penalty
    for wasted trajectories.
  * Terminal: +20 Red win (any Blue site HP = 0), -20 Blue win
    (Red priced out AND no live threats). -5 on draw / truncation —
    without this, "hold forever" is a local optimum (pays nothing
    and collects no terminal penalty).
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import gymnasium as gym
from gymnasium import spaces

from sim import sites as sites_module
from sim.blue_ai import BlueAI
from sim.config import (
    ARENA_X,
    BLUE_BUDGET_START,
    DT,
    LAUNCH_RANGE_MARGIN,
    RED_BUDGET_START,
    SITE_HP_START,
)
from sim.launcher import LauncherFleet, RedLauncherFleet
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

def _patch_numpy_core_for_legacy_pickle() -> None:
    """Alias numpy._core.* → numpy.core.* for cross-version model loads.

    Boyu's Blue model was saved under numpy>=2.0 where numpy's internal
    C-extension modules moved from `numpy.core.*` to `numpy._core.*`.
    Our current env has numpy 1.26. It DOES ship a `numpy._core`
    forwarding stub (imported transitively by torch / sb3 before this
    patch runs) but the stub doesn't expose submodules like
    `numpy._core.numeric`, so the pickled Blue model fails to unpickle.
    We bind each missing submodule into sys.modules as an alias of the
    legacy `numpy.core.*` path. Idempotent: each key is only installed
    if absent.
    """
    import sys
    import types
    import numpy
    sys.modules.setdefault("numpy._core", types.ModuleType("numpy._core"))
    for submod in ("numeric", "multiarray", "_methods", "umath"):
        key = f"numpy._core.{submod}"
        if key in sys.modules:
            continue
        try:
            legacy = getattr(numpy.core, submod)
        except AttributeError:
            continue
        alias = types.ModuleType(key)
        for name in dir(legacy):
            setattr(alias, name, getattr(legacy, name))
        sys.modules[key] = alias


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
        blue_policy_path: Optional[str] = None,
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
        self.blue_fleet: Optional[LauncherFleet] = None
        self.red_launchers: Optional[RedLauncherFleet] = None
        self.rng: Optional[np.random.Generator] = None
        self._cum_reward: float = 0.0
        # Learned-Blue opponent. When None, rule-based BlueAI is used.
        # When a path is given, the policy is loaded ONCE here (per
        # process — under SubprocVecEnv each worker loads its own copy).
        # Device forced to CPU so subprocess inference doesn't share the
        # training process's GPU context.
        self._blue_policy_path = blue_policy_path
        if blue_policy_path is not None:
            _patch_numpy_core_for_legacy_pickle()
            from sb3_contrib import MaskablePPO
            self.blue_policy = MaskablePPO.load(blue_policy_path, device="cpu")
            # Cap-bridging adapter (Red v2, 2026-04-26). Env now runs at
            # 72/32/128 but B_shaped is at 30/15/40, V4 at 30/15/40, Boyu
            # V2a at 96/24/128. Capture model-expected dims so the obs
            # encoder can slice down and the action applier can pad up
            # (mirrors the live_ai LearnedBlueAI adapter).
            obs_space = self.blue_policy.observation_space
            self._blue_model_max_threats = int(obs_space["threats"].shape[0])
            self._blue_model_max_launchers = int(obs_space["launchers"].shape[0])
            self._blue_model_max_interceptors = int(
                obs_space["interceptors"].shape[0]
            )
            self._blue_needs_adapter = (
                self._blue_model_max_threats != MAX_THREATS
                or self._blue_model_max_launchers != MAX_LAUNCHERS
                or self._blue_model_max_interceptors != MAX_INTERCEPTORS
            )
            if self._blue_needs_adapter:
                print(
                    f"[RedEnv] Blue adapter: model expects "
                    f"T={self._blue_model_max_threats}/"
                    f"L={self._blue_model_max_launchers}/"
                    f"I={self._blue_model_max_interceptors} "
                    f"(env at {MAX_THREATS}/{MAX_LAUNCHERS}/{MAX_INTERCEPTORS})",
                    flush=True,
                )
        else:
            self.blue_policy = None
            self._blue_model_max_threats = MAX_THREATS
            self._blue_model_max_launchers = MAX_LAUNCHERS
            self._blue_model_max_interceptors = MAX_INTERCEPTORS
            self._blue_needs_adapter = False

    def _build_spaces(self):
        # +2 for the evasion-bit slots (always-legal pair) — see
        # `_build_action_mask`.
        mask_len = N_RED_KINDS + self._n_sites + 2
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
        # Third dim is the HGV-evasion bit (0 = no maneuver this decision,
        # 1 = trigger override_maneuver perpendicular to the nearest PAC LOS
        # for every alive HGV under PAC threat). See `_apply_hgv_evasion`.
        self.action_space = spaces.MultiDiscrete([N_RED_KINDS, self._n_sites, 2])

    # ------------------------------------------------------------------
    def reset(self, seed: Optional[int] = None, options=None):
        super().reset(seed=seed)
        if seed is not None:
            self._seed = seed
        self.rng = np.random.default_rng(seed)
        sites_module.reset_leaks()
        self.world = World()
        # Rule Blue: BlueAI owns its own LauncherFleet (constructed from
        # config.BLUE_LAUNCHER_POSITIONS). Learned Blue: we own the
        # LauncherFleet directly and drive it from policy.predict
        # (mirroring env.py's MissileInterceptEnv ownership). In both
        # cases `self.blue_fleet` points at the active fleet so the obs
        # encoder has one uniform lookup.
        if self.blue_policy is None:
            self.blue = BlueAI()
            self.blue_fleet = self.blue.launchers
        else:
            self.blue = None
            self.blue_fleet = LauncherFleet()
        # Red launcher fleet is used only for `positions_for(kind)` /
        # `next_pos(kind)` lookups; no ammo / cooldown bookkeeping.
        self.red_launchers = RedLauncherFleet()
        self.world.transition(MatchPhase.RUNNING)
        self._cum_reward = 0.0
        # Total starting site HP drives the normalization denominator
        # for leak rewards. Captured post-reset_leaks so reading from
        # `hp_max` is safe.
        self._total_site_hp = max(
            1, sum(s.hp_max for s in sites_module.SOUTH_SITES)
        )
        # HGV-evasion bookkeeping (v2):
        # `_hgv_recently_maneuvered` maps hgv_id → decision-step at which
        # `override_maneuver` was last commanded. The reward function
        # treats a PAC ground_crash whose target is an HGV maneuvered
        # within the last 10 decision steps as a real dodge.
        # `_hgv_dodge_count` is reported in info each step so training
        # logs can confirm the bonus is firing.
        self._hgv_recently_maneuvered: Dict[int, int] = {}
        self._tick_counter: int = 0
        self._hgv_dodge_count: int = 0
        return self._encode_obs(), {}

    # ------------------------------------------------------------------
    def step(self, action):
        action = np.asarray(action, dtype=np.int64).reshape(-1)
        # Decision-step counter (v2). Incremented before _apply_action
        # so any maneuver recorded by `_apply_hgv_evasion` is timestamped
        # with the current step's index.
        self._tick_counter += 1
        # Snapshot Blue's budget pre-decision so we can reward Red for
        # making Blue burn interceptor money. Red's own budget is
        # snapshotted inside _apply_action via the returned cost.
        prev_blue_budget = self.world.blue_budget

        # Learned Blue acts FIRST, using pre-Red-action world state.
        # Matches Boyu's training distribution: during Blue training,
        # Blue's obs reflected state before the current-window Red AI
        # step ran inside the inner loop — Red's new spawn this window
        # only became visible next decision. Applying Blue before Red
        # here keeps that input distribution consistent.
        if self.blue_policy is not None:
            blue_obs_full = self._encode_obs_blue()
            blue_obs = self._adapt_obs_for_blue_model(blue_obs_full)
            blue_mask_flat = blue_obs["action_mask"].reshape(-1).astype(np.int8)
            blue_action, _ = self.blue_policy.predict(
                blue_obs, deterministic=False, action_masks=blue_mask_flat
            )
            env_blue_action = self._adapt_blue_action_for_env(
                np.asarray(blue_action).reshape(-1)
            )
            self._apply_blue_action(env_blue_action)

        # Apply Red action (spawn or hold). Deducts red_budget
        # inside on success; returns the raw USD spawn cost.
        spawned, spawn_cost_usd = self._apply_action(action)

        event_reward = 0.0
        for _ in range(DECISION_EVERY):
            self.world.events = []
            if self.blue_policy is None:
                # Rule Blue: runs its own decision logic every tick and
                # ticks its internal fleet inside step().
                self.blue.step(self.world.t, self.world)
            else:
                # Learned Blue: fleet tick advances reload / CD timers.
                # Firing decisions already made ONCE at the top of this
                # step() call; no per-tick policy calls.
                self.blue_fleet.tick(self.world.t)
            # No RedLauncherFleet.tick() — fleet is ammo-less (see
            # launcher.RedLauncher docstring).
            self.world.step(DT)
            event_reward += self._reward_from_events(self.world.events)
            self.world.prune_dead()
            if self._winner() is not None:
                break
            if self.world.t >= self._episode_time_limit:
                break

        # --- Normalized per-decision shaping ---
        # Spawn penalty: fraction of Red's starting budget burned on
        # this decision. Single-charge — intercept events are NOT a
        # second penalty (see _reward_from_events docstring).
        spawn_penalty = -1.0 * (spawn_cost_usd / RED_BUDGET_START)
        # Weak cost-exchange bonus: when Blue launches interceptors,
        # Red benefits proportionally to the fraction of Blue's budget
        # spent this decision window. Scaled small (0.1x vs leak 10x)
        # so it doesn't dominate the leak signal.
        blue_spent = max(0, prev_blue_budget - self.world.blue_budget)
        blue_spend_bonus = 0.1 * (blue_spent / BLUE_BUDGET_START)

        reward = event_reward + spawn_penalty + blue_spend_bonus

        terminated = self._winner() is not None
        truncated = (not terminated) and self.world.t >= self._episode_time_limit

        if terminated:
            w = self._winner()
            if w == "red":
                reward += 20.0
            elif w == "blue":
                reward -= 20.0
        elif truncated:
            # Draw / timeout penalty. Stops the agent settling on
            # "hold forever = 0 reward" as a local optimum — that
            # policy now collects -5 instead of 0.
            reward -= 5.0

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
        # M-TIER3-RED-WINNER (2026-04-26): Red wins ONLY when ALL military
        # bases are dead. Old code returned "red" on any single base at
        # hp=0, so the trained Red learned "kill one base then stop" and
        # never learned full-takedown strategy. Mirrors Blue env's win
        # condition (env.py:_winner).
        military_bases = [
            s for s in sites_module.SOUTH_SITES
            if s.subtype in ('base', 'air_base')
        ]
        if military_bases and all(s.hp <= 0 for s in military_bases):
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
        """Execute the Red decision. Returns (spawned, spawn_cost_usd).

        * `spawned` is True iff a threat entered the world this call.
        * `spawn_cost_usd` is the spec's `usd_cost` (0 on hold or failed
          spawn). Caller normalizes by RED_BUDGET_START to produce the
          decision-level spawn penalty.

        Action shape (v2): (3,) — [kind_idx, site_idx, evasion_bit].
        Evasion bit (third dim):
          0 = no maneuver this decision
          1 = trigger HGV evasion: for every alive HGV with a Blue PAC
              interceptor in flight targeting it, compute perpendicular
              evasion direction (perpendicular to LOS to nearest such
              interceptor) and call override_maneuver(direction,
              0.7 * max_g). Records the tick in `_hgv_recently_maneuvered`
              so the reward function can detect actual dodge events.
        """
        kind_idx = int(action[0])
        site_idx = int(action[1]) if action.shape[0] > 1 else 0
        evasion = bool(int(action[2])) if action.shape[0] > 2 else False
        spawned = False
        cost_usd = 0.0
        if kind_idx == 0:
            pass
        elif kind_idx < 0 or kind_idx >= N_RED_KINDS:
            pass
        else:
            kind = RED_ACTION_KINDS[kind_idx]
            spec = THREAT_SPECS[kind]
            if self.world.red_budget >= spec.usd_cost:
                sites_list = sites_module.SOUTH_SITES
                if sites_list:
                    target_site = sites_list[site_idx % len(sites_list)]
                    target_xy = target_site.pos
                    target_site_id = target_site.id
                    spawn_pos = self._pick_spawn(kind)
                    if spawn_pos is not None:
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
                            self.world.red_budget = max(
                                0, self.world.red_budget - spec.usd_cost,
                            )
                            spawned = True
                            cost_usd = float(spec.usd_cost)
                        except ValueError:
                            # W14 spawn-location contract rejected the
                            # coord. No-op; budget not deducted.
                            pass

        if evasion:
            self._apply_hgv_evasion()

        return spawned, cost_usd

    def _apply_hgv_evasion(self) -> None:
        """For each alive HGV, find the nearest in-flight Blue PAC-2/PAC-3
        interceptor targeting it. If one exists, apply override_maneuver
        perpendicular to LOS at 0.7 * max_g and record the tick.

        HGVs without a PAC threatening them get NO maneuver — this
        prevents the policy from using evasion=1 to spin HGVs in safe
        airspace (the speed-bleed mechanic in entities._HGV_BLEED_RATE
        would be free money since no one's chasing).

        The reward function pairs this with the ground_crash detector:
        a PAC dies targeting a maneuvered HGV → +1.0 dodge bonus. Just
        triggering this method without an active PAC threat → no reward.
        """
        PAC_KINDS = (InterceptorType.LONG_SAM, InterceptorType.HIT_TO_KILL)

        for hgv_id, threat in list(self.world.threats.items()):
            if not threat.state.alive:
                continue
            try:
                if ThreatType(threat.state.kind) != ThreatType.HGV:
                    continue
            except ValueError:
                continue

            nearest_inter = None
            nearest_dist_sq = float("inf")
            for iid, inter in self.world.interceptors.items():
                if not inter.state.alive:
                    continue
                if inter.target_id != hgv_id:
                    continue
                try:
                    inter_kind = InterceptorType(inter.state.kind)
                except ValueError:
                    continue
                if inter_kind not in PAC_KINDS:
                    continue
                dx = float(inter.state.pos[0] - threat.state.pos[0])
                dy = float(inter.state.pos[1] - threat.state.pos[1])
                dz = float(inter.state.pos[2] - threat.state.pos[2])
                d_sq = dx * dx + dy * dy + dz * dz
                if d_sq < nearest_dist_sq:
                    nearest_dist_sq = d_sq
                    nearest_inter = inter

            if nearest_inter is None:
                continue  # No PAC threat — skip (no spinning bonus).

            # Perpendicular direction in horizontal plane:
            # perp = LOS x z_up gives a horizontal vector orthogonal to LOS.
            los = np.array([
                float(nearest_inter.state.pos[0] - threat.state.pos[0]),
                float(nearest_inter.state.pos[1] - threat.state.pos[1]),
                float(nearest_inter.state.pos[2] - threat.state.pos[2]),
            ])
            z_up = np.array([0.0, 0.0, 1.0])
            perp = np.cross(los, z_up)
            perp_norm = float(np.linalg.norm(perp))
            if perp_norm < 1e-6:
                continue
            direction = perp / perp_norm

            # 0.7 * max_g — keeps the speed bleed manageable
            # (full max_g would stall HGV in ~30 sustained seconds).
            threat.override_maneuver(direction, threat.spec.max_g * 0.7)

            # Record for dodge detection in the reward function.
            self._hgv_recently_maneuvered[threat.state.id] = self._tick_counter

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
        """Per-tick dense shaping (Red trainee v2, 2026-04-26).

        Single-charge cost model preserved: spawn cost is still applied
        at action time in step() via `spawn_penalty`. The intercept
        branches below are ADDITIONAL signals on top, not replacements.

        Layered signal:
          1. Leak event:
             - Military base/air_base: 10 * (dmg / total_hp) * base_weight
               where base_weight = n_initial / n_alive (3 alive: 1.0,
               1 alive: 3.0). Killing the LAST base gives 3x the reward
               of killing the first. V4 mirror.
             - Civilian / unknown site: 2 * (dmg / total_hp), no scaling.

          2. Intercept event (Red threat killed by Blue interceptor):
             - inter_cost > 5x threat_cost: drain bonus
               (Blue paid > 5x to kill Red's cheap threat).
             - threat_cost >= $1M AND inter_cost < 0.1x threat_cost:
               penalty -1.5 (Red wasted high-value kit on cheap counter).
             - else: 0 (single-charge cost model already taxed Red at
               spawn).

          3. Ground crash of a Blue PAC-2/PAC-3 interceptor whose target
             was an alive HGV that was maneuvered within the last
             10 ticks: +1.0 (real PAC dodge, not just spinning in air).

          4. Ground crash of a Red threat: -0.2 (wasted spawn).

        Caller invokes BEFORE world.prune_dead so events resolve to
        live interceptor / threat objects.
        """
        r = 0.0

        # Base-weight scaling (V4 mirror).
        military_subtypes = ('base', 'air_base')
        n_alive = max(1, sum(
            1 for s in sites_module.SOUTH_SITES
            if s.subtype in military_subtypes and s.hp > 0
        ))
        n_initial = max(1, sum(
            1 for s in sites_module.SOUTH_SITES
            if s.subtype in military_subtypes
        ))
        base_weight = n_initial / n_alive  # 3 alive: 1.0, 2: 1.5, 1: 3.0

        for ev in events:
            et = ev.get("type")

            if et == "leak":
                dmg = ev.get("damage", 0)
                site_name = ev.get("site", "")
                site = next(
                    (s for s in sites_module.SOUTH_SITES if s.name == site_name),
                    None,
                )
                if site is not None and site.subtype in military_subtypes:
                    r += 10.0 * (float(dmg) / self._total_site_hp) * base_weight
                else:
                    r += 2.0 * (float(dmg) / self._total_site_hp)

            elif et == "intercept":
                iid = ev.get("interceptor")
                tid = ev.get("threat")
                inter = self.world.interceptors.get(iid) if iid is not None else None
                threat = self.world.threats.get(tid) if tid is not None else None
                if inter is not None and threat is not None:
                    try:
                        inter_kind = InterceptorType(inter.state.kind)
                        threat_kind = ThreatType(threat.state.kind)
                        inter_cost = INTERCEPTOR_SPECS[inter_kind].usd_cost
                        threat_cost = THREAT_SPECS[threat_kind].usd_cost
                        if inter_cost > threat_cost * 5.0:
                            # Drain: Blue paid > 5x for Red's cheap threat.
                            r += min(inter_cost / threat_cost / 20.0, 1.0)
                        elif threat_cost >= 1_000_000 and inter_cost < threat_cost * 0.1:
                            # Red invested >$1M, killed by <10% the cost.
                            r -= 1.5
                    except (KeyError, ValueError):
                        pass

            elif et == "ground_crash" and ev.get("interceptor") is not None:
                # HGV evasion bonus — only when target was an alive
                # maneuvered HGV and the dead interceptor is PAC-2/PAC-3.
                iid = ev["interceptor"]
                inter = self.world.interceptors.get(iid)
                if inter is None:
                    continue
                target = self.world.threats.get(inter.target_id)
                if target is None or not target.state.alive:
                    continue  # target already dead — not a dodge
                try:
                    if ThreatType(target.state.kind) != ThreatType.HGV:
                        continue
                    inter_kind = InterceptorType(inter.state.kind)
                    if inter_kind not in (
                        InterceptorType.LONG_SAM, InterceptorType.HIT_TO_KILL,
                    ):
                        continue
                    last_maneuver = self._hgv_recently_maneuvered.get(
                        target.state.id, -999_999,
                    )
                    if self._tick_counter - last_maneuver < 10:
                        r += 1.0  # Real PAC dodge by maneuvered HGV.
                        self._hgv_dodge_count += 1
                except (KeyError, ValueError):
                    pass

            elif et == "ground_crash" and ev.get("threat") is not None:
                r -= 0.2

        return r

    # ------------------------------------------------------------------
    def action_masks(self) -> np.ndarray:
        """Public API for sb3_contrib.ActionMasker. Returns the flat
        marginal mask, shape (N_RED_KINDS + n_sites,), dtype int8."""
        return self._build_action_mask()

    def _build_action_mask(self) -> np.ndarray:
        """Component-wise marginal mask for
        MultiDiscrete([N_RED_KINDS, n_sites, 2]).

        Layout:
          mask[0:N_RED_KINDS]                          = kind mask
          mask[N_RED_KINDS:N_RED_KINDS+n_sites]        = site mask (all 1)
          mask[N_RED_KINDS+n_sites:
               N_RED_KINDS+n_sites+2]                  = evasion mask (all 1)

        Total length = sum(action_space.nvec) = N_RED_KINDS + n_sites + 2.
        Hold (kind=0) is always legal. Non-hold kinds are legal iff Red
        can afford the spec cost AND a spawn path exists (drone/cruise
        need a launcher for that kind; strategic kinds always have the
        far-north strip). Evasion bit is always legal: 0 = no maneuver,
        1 = trigger HGV evasion (which is a no-op when no HGV is under
        active PAC threat, see `_apply_hgv_evasion`).
        """
        n_sites = self._n_sites
        mask = np.zeros(N_RED_KINDS + n_sites + 2, dtype=np.int8)
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
        # Evasion dim: both 0 and 1 always legal.
        mask[N_RED_KINDS + n_sites] = 1      # evasion = 0
        mask[N_RED_KINDS + n_sites + 1] = 1  # evasion = 1
        return mask

    # ------------------------------------------------------------------
    # Learned-Blue opponent helpers. Only used when blue_policy is set.
    # All three are ports of the matching methods in
    # rl.env.MissileInterceptEnv — we mirror rather than import so the
    # fleet/threat lookups bind to RedEnv's state.
    def _build_blue_action_mask_2d(self) -> np.ndarray:
        """2D Blue action mask of shape (MAX_LAUNCHERS, MAX_THREATS+1),
        int8. Row l col c = 1 iff launcher l firing at threat-slot c is
        legal this tick. Col MAX_THREATS = hold, always 1 for live or
        pad launcher rows so MaskablePPO can always pick at least one
        legal sub-action per dim.
        """
        threats = self._alive_threats()
        launchers = self.blue_fleet.launchers[:MAX_LAUNCHERS]
        mask = np.zeros((MAX_LAUNCHERS, MAX_THREATS + 1), dtype=np.int8)
        t_now = self.world.t
        for l_idx in range(MAX_LAUNCHERS):
            if l_idx >= len(launchers):
                mask[l_idx, MAX_THREATS] = 1
                continue
            lch = launchers[l_idx]
            mask[l_idx, MAX_THREATS] = 1  # hold always valid
            if lch.reloading or not lch.can_fire(t_now):
                continue
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

    def _encode_obs_blue(self) -> dict:
        """Observation for learned Blue policy inference.

        Identical to `_encode_obs` except `action_mask` is the 2D Blue
        shape (MAX_LAUNCHERS, MAX_THREATS+1) instead of Red's flat
        marginal. Blue's CombinedExtractor was trained on the 2D shape;
        feeding the Red-shaped mask would error on a per-key reshape.
        """
        obs = self._encode_obs()
        obs["action_mask"] = self._build_blue_action_mask_2d()
        return obs

    def _adapt_obs_for_blue_model(self, env_obs: dict) -> dict:
        """Slice env_obs to Blue model's native cap. Mirrors
        live_ai.LearnedBlueAI._adapt_obs_for_model.

        Required because Red v2 runs at MAX_THREATS=72 / MAX_LAUNCHERS=32 /
        MAX_INTERCEPTORS=128 but loaded Blue policies are at smaller caps
        (B_shaped/V4: 30/15/40; Boyu V2a: 96/24/128 — Boyu's threats=96
        is bigger, but launchers=24 and interceptors=128 are smaller and
        equal respectively). For the bigger-than-env case (Boyu's
        threats), the env tensor is naturally smaller; we pad by sticking
        with the original env_obs tensor sliced to model's expected size
        — which means filling the first 72 slots with real data and
        leaving the remaining 24 unused. We do this by allocating a
        zero array of the model size and copying min(env, model) entries.
        """
        if not self._blue_needs_adapter:
            return env_obs
        n_t = self._blue_model_max_threats
        n_l = self._blue_model_max_launchers
        n_i = self._blue_model_max_interceptors

        def _resize(arr: np.ndarray, target: int) -> np.ndarray:
            if arr.shape[0] == target:
                return arr
            if arr.shape[0] > target:
                return arr[:target]
            # Model expects more rows than env produces (e.g. Boyu's 96
            # threats vs env's 72). Pad with zeros and matching mask=0.
            shape = (target,) + arr.shape[1:]
            out = np.zeros(shape, dtype=arr.dtype)
            out[: arr.shape[0]] = arr
            return out

        out_threats = _resize(env_obs["threats"], n_t)
        out_threats_mask = _resize(env_obs["threats_mask"], n_t)
        out_launchers = _resize(env_obs["launchers"], n_l)
        out_launchers_mask = _resize(env_obs["launchers_mask"], n_l)
        out_inter = _resize(env_obs["interceptors"], n_i)
        out_inter_mask = _resize(env_obs["interceptors_mask"], n_i)

        # 2D action_mask resize: (MAX_LAUNCHERS, MAX_THREATS+1) →
        # (n_l, n_t+1). Both dims need handling.
        env_mask = env_obs["action_mask"]
        out_mask = np.zeros((n_l, n_t + 1), dtype=env_mask.dtype)
        copy_l = min(env_mask.shape[0], n_l)
        copy_t = min(env_mask.shape[1] - 1, n_t)
        out_mask[:copy_l, :copy_t] = env_mask[:copy_l, :copy_t]
        # Hold column for model = column index n_t. Each launcher row's
        # hold is always legal — copy or set explicitly.
        out_mask[:, n_t] = 1
        return {
            "threats":           out_threats,
            "threats_mask":      out_threats_mask,
            "launchers":         out_launchers,
            "launchers_mask":    out_launchers_mask,
            "interceptors":      out_inter,
            "interceptors_mask": out_inter_mask,
            "sites":             env_obs["sites"],
            "sites_mask":        env_obs["sites_mask"],
            "global":            env_obs["global"],
            "action_mask":       out_mask,
        }

    def _adapt_blue_action_for_env(self, model_action: np.ndarray) -> np.ndarray:
        """Pad / hold-remap model's action vector to env shape. Mirrors
        live_ai.LearnedBlueAI._adapt_action_for_env.

        Model action shape: (n_l,), values in [0, n_t]. Value n_t = hold.
        Env action shape: (MAX_LAUNCHERS,), values in [0, MAX_THREATS].
        Value MAX_THREATS = hold.

        Slots beyond model's launcher count are filled with env's hold
        sentinel so `_apply_blue_action` skips them.
        """
        if not self._blue_needs_adapter:
            return model_action
        env_action = np.full(MAX_LAUNCHERS, MAX_THREATS, dtype=np.int64)
        model_hold = self._blue_model_max_threats
        for i, a in enumerate(model_action):
            if i >= MAX_LAUNCHERS:
                break
            a_int = int(a)
            if a_int == model_hold:
                env_action[i] = MAX_THREATS
            elif a_int < MAX_THREATS:
                env_action[i] = a_int
            else:
                env_action[i] = MAX_THREATS
        return env_action

    def _apply_blue_action(self, action: np.ndarray) -> int:
        """Execute Blue's learned-policy action against the world.

        Port of rl.env.MissileInterceptEnv._apply_action. `action` has
        shape (MAX_LAUNCHERS,), values in [0, MAX_THREATS]. Value
        MAX_THREATS means hold; otherwise launcher `l_idx` fires at
        threat-slot `action[l_idx]`. Invalid fires are silently skipped
        — the action mask should have blocked them but we defensively
        re-check (in-range / ready / threat-alive). Threat-slot order
        matches `_alive_threats()` which mirrors env.py's iteration
        order (dict insertion order on `world.threats`), so learned
        Blue's index → threat mapping is consistent with its training.
        Returns the count of successful fires (not currently used, but
        retained for parity with env.py + future info-dict wiring).
        """
        launchers = self.blue_fleet.launchers
        threats = self._alive_threats()
        n_fires = 0
        for l_idx, a in enumerate(action):
            if l_idx >= len(launchers):
                break
            a_int = int(a)
            if a_int >= MAX_THREATS:
                continue  # hold
            if a_int >= len(threats):
                continue  # pad slot target
            lch = launchers[l_idx]
            if lch.reloading or not lch.can_fire(self.world.t):
                continue
            threat = threats[a_int]
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
            self.world.blue_budget = max(
                0, self.world.blue_budget - spec.usd_cost
            )
            n_fires += 1
        return n_fires

    # ------------------------------------------------------------------
    def _encode_obs(self) -> dict:
        """Omniscient Dict observation — same shape + fields as Blue env.

        Adapted from rl.env.MissileInterceptEnv._encode_obs:
        `self.blue_fleet` replaces `self.fleet`; other logic is
        identical. Kept as a method (not imported from env.py) because
        it references `self`-bound fleet / world state and the Blue env
        class hierarchy doesn't support the substitution cleanly.
        """
        threats = self._alive_threats()
        launchers = self.blue_fleet.launchers[:MAX_LAUNCHERS]
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
