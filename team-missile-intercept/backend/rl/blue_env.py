"""Blue-side self-play env — MissileInterceptEnv with a learned Red opponent.

Opt-in subclass that swaps the rule-based RedAI for a learned MaskablePPO
Red policy loaded from a model.zip. When `red_policy_path=None` behaves
identically to `MissileInterceptEnv` (rule Red). Used by `blue_train.py`
for Phase 4a self-play (Blue_3 trained against Red2 opponent).

Symmetric to `red_env.RedEnv(blue_policy_path=...)` which drives the
Red-training side of self-play. The timing mirror: in Red training
(red_env.py) learned Blue acts FIRST at the top of each step so Red's
obs reflects pre-Blue-action state, matching Red's training
distribution. Here, learned Red acts FIRST at the top of each step so
Blue's obs reflects pre-Red-spawn state, matching Blue's training
distribution under rule RedAI (where rule Red's per-tick spawns inside
the inner loop become visible in the NEXT obs, not the current).

numpy._core compat shim: applied at module import time (same pattern as
red_env.py on rl-self-play-v1) so `MaskablePPO.load` can unpickle models
saved under numpy>=2.0 while we run on numpy 1.26.
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np
import gymnasium as gym


def _patch_numpy_core_for_legacy_pickle() -> None:
    """Alias numpy._core.* → numpy.core.* for cross-version model loads.

    Idempotent: each key is only installed if absent. Covers the four
    submodules that SB3's policy pickle references (numeric, multiarray,
    _methods, umath). Called once at module import.
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


_patch_numpy_core_for_legacy_pickle()


from sim import sites as sites_module
from sim.config import (
    ARENA_X,
    RED_BUDGET_START,
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
    THREAT_SPECS,
    ThreatType,
)

from rl.env import MissileInterceptEnv
from rl.red_env import (
    N_RED_KINDS,
    RED_ACTION_KINDS,
)


class _NoOpRedAI:
    """Stand-in for sim.red_ai.RedAI when a learned policy drives spawns.

    Exposes the same `step(t, world)` method and `done` attribute that
    MissileInterceptEnv references — `step` is a no-op (learned Red
    already acted at the top of the outer step), `done=False` means
    Blue's `_winner` path gates only on `red_budget <= 0` rather than
    wave exhaustion (which doesn't apply to a learned opponent).
    """
    done = False

    def step(self, t: float, world) -> None:
        pass


class BlueSelfPlayEnv(MissileInterceptEnv):
    """MissileInterceptEnv with an optional learned Red opponent.

    When `red_policy_path` is provided, a learned MaskablePPO Red policy
    is loaded once per env instance (per subprocess under SubprocVecEnv)
    and produces a single spawn decision at the top of each outer step
    via `policy.predict`. The rule RedAI is replaced with a no-op so
    MissileInterceptEnv's existing inner loop physics run unchanged. All
    other behavior (reward shaping, termination, action mask for Blue,
    observation encoding) is inherited verbatim from the parent class.

    When `red_policy_path=None` behaves identically to the parent —
    useful for local smoke-tests against rule Red without a separate
    code path.
    """

    def __init__(
        self,
        red_policy_path: Optional[str] = None,
        seed: Optional[int] = None,
        episode_time_limit: Optional[float] = None,
    ):
        kwargs = {"seed": seed}
        if episode_time_limit is not None:
            kwargs["episode_time_limit"] = episode_time_limit
        super().__init__(**kwargs)

        self._red_policy_path = red_policy_path
        self._red_seed = seed
        self._n_sites = max(1, len(sites_module.SOUTH_SITES))

        if red_policy_path is not None:
            from sb3_contrib import MaskablePPO
            self.red_policy = MaskablePPO.load(red_policy_path, device="cpu")
        else:
            self.red_policy = None

        self.red_launchers: Optional[RedLauncherFleet] = None
        self._red_rng: Optional[np.random.Generator] = None

    # ------------------------------------------------------------------
    def reset(self, seed: Optional[int] = None, options=None):
        obs, info = super().reset(seed=seed, options=options)
        if seed is not None:
            self._red_seed = seed
        if self.red_policy is not None:
            # Override the rule RedAI the parent just installed with a
            # no-op stand-in. Learned Red drives spawns from `step`.
            self.red = _NoOpRedAI()
            self.red_launchers = RedLauncherFleet()
            self._red_rng = np.random.default_rng(self._red_seed)
        return obs, info

    # ------------------------------------------------------------------
    def step(self, action):
        # Learned Red decides FIRST at the top of each decision tick.
        # Blue's obs (which produced `action`) was captured at the end
        # of the previous step, before Red's current-window spawn — this
        # matches the rule-Red training distribution where rule Red's
        # per-tick spawns inside the inner loop become visible in the
        # NEXT obs, not the current one.
        if self.red_policy is not None and self.world is not None:
            red_obs = self._encode_obs_red()
            red_mask_flat = red_obs["action_mask"].astype(np.int8)
            red_action, _ = self.red_policy.predict(
                red_obs, deterministic=False, action_masks=red_mask_flat
            )
            self._apply_red_action(np.asarray(red_action).reshape(-1))
        return super().step(action)

    # ------------------------------------------------------------------
    # Red obs + mask helpers. Shape matches `rl.red_env.RedEnv`'s flat
    # component-wise mask: length N_RED_KINDS + n_sites. Policy was
    # trained with this layout, so we must produce the same shape here.
    def _encode_obs_red(self) -> dict:
        """Red's observation: parent obs with a Red-shaped action_mask.

        The parent `_encode_obs` uses a 2D Blue action mask of shape
        (MAX_LAUNCHERS, MAX_THREATS+1). MaskablePPO's predict path
        reads obs["action_mask"] and re-wires it via the agent-side
        mask, so we swap that field for Red's 1D marginal mask before
        calling predict.
        """
        obs = self._encode_obs()
        obs = dict(obs)
        obs["action_mask"] = self._build_red_action_mask()
        return obs

    def _build_red_action_mask(self) -> np.ndarray:
        """Component-wise marginal mask for MultiDiscrete([5, n_sites]).

        Mirrors `rl.red_env.RedEnv._build_action_mask`. Slots [0:5] gate
        kind; [5:5+n_sites] gate site (always all-ones).
        """
        n_sites = self._n_sites
        mask = np.zeros(N_RED_KINDS + n_sites, dtype=np.int8)
        mask[0] = 1  # hold is always legal
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
        mask[N_RED_KINDS:N_RED_KINDS + n_sites] = 1
        return mask

    # ------------------------------------------------------------------
    # Red spawn execution. Ports `rl.red_env.RedEnv._apply_action` /
    # `_pick_spawn` / `_build_cruise_waypoints` — kept here so blue_env
    # can be reviewed in isolation without chasing cross-module state.
    def _apply_red_action(self, action: np.ndarray) -> None:
        """Execute learned Red's spawn decision against the world.

        Silently no-ops on hold / budget-exhaustion / sampler rejection
        — the action mask should have blocked these but we defensively
        re-check. No reward side-effects: reward is Blue's, computed
        entirely inside the parent `step` from world events.
        """
        kind_idx = int(action[0])
        site_idx = int(action[1]) if action.shape[0] > 1 else 0
        if kind_idx == 0 or kind_idx < 0 or kind_idx >= N_RED_KINDS:
            return
        kind = RED_ACTION_KINDS[kind_idx]
        spec = THREAT_SPECS[kind]
        if self.world.red_budget < spec.usd_cost:
            return

        sites_list = sites_module.SOUTH_SITES
        if not sites_list:
            return
        target_site = sites_list[site_idx % len(sites_list)]
        target_xy = target_site.pos
        target_site_id = target_site.id

        spawn_pos = self._pick_red_spawn(kind)
        if spawn_pos is None:
            return
        try:
            if kind == ThreatType.CRUISE_SUB:
                wps = self._build_red_cruise_waypoints(spawn_pos, target_xy)
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
            # Spawn-location contract rejected the coord (W14). Treat as
            # a no-op so a mis-configured sampler doesn't crash the
            # episode. Budget stays untouched.
            return

        self.world.red_budget = max(0, self.world.red_budget - spec.usd_cost)

    def _pick_red_spawn(self, kind: ThreatType) -> Optional[tuple]:
        """Pick (x, y, z) for a Red threat of this kind.

        Drone / cruise use the Red launcher fleet's round-robin picker;
        ballistic / HGV use the strategic far-north strip sampler.
        """
        if kind in (ThreatType.DRONE, ThreatType.CRUISE_SUB):
            pos = self.red_launchers.next_pos(kind)
            if pos is None:
                return None
            x, y = pos
            if kind == ThreatType.DRONE:
                z = float(self._red_rng.uniform(*DRONE_ALT_RANGE))
            else:
                z = float(self._red_rng.uniform(*CRUISE_ALT_RANGE))
            return (x, y, z)
        if kind == ThreatType.BALLISTIC:
            x = float(self._red_rng.uniform(0.0, ARENA_X))
            y = float(self._red_rng.uniform(*STRATEGIC_Y_BAND))
            z = max(BALLISTIC_MIN_Z, float(self._red_rng.uniform(*BALLISTIC_ALT_RANGE)))
            return (x, y, z)
        if kind == ThreatType.HGV:
            x = float(self._red_rng.uniform(0.0, ARENA_X))
            y = float(self._red_rng.uniform(*STRATEGIC_Y_BAND))
            z = max(HGV_MIN_Z, float(self._red_rng.uniform(*HGV_ALT_RANGE)))
            return (x, y, z)
        return None

    def _build_red_cruise_waypoints(self, spawn_xyz, target_xy) -> List[tuple]:
        """Port of `rl.red_env.RedEnv._build_cruise_waypoints`. Uses the
        env-local rng so seeded resets are reproducible."""
        sx, sy, sz = spawn_xyz
        tx, ty = target_xy
        n = int(self._red_rng.integers(1, 3))
        progress = sorted(float(self._red_rng.uniform(0.30, 0.70)) for _ in range(n))
        side = 1.0 if self._red_rng.random() < 0.5 else -1.0
        wps: List[tuple] = []
        for i, p in enumerate(progress):
            bx = sx + (tx - sx) * p
            by = sy + (ty - sy) * p
            offset_mag = float(self._red_rng.uniform(5_000.0, 20_000.0))
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
