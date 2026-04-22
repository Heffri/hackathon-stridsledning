"""Live-demo wrappers — learned policies driving Scenario.red / Scenario.blue.

Two Scenario-compatible wrapper classes (``LearnedRedAI`` / ``LearnedBlueAI``)
that pose as the rule-based ``RedAI`` / ``BlueAI`` from ``sim/`` but drive a
MaskablePPO policy under the hood. Dropped into ``scenario.red`` /
``scenario.blue`` by ``server.py`` when ``RED_POLICY_PATH`` /
``BLUE_POLICY_PATH`` env vars are set.

Design: compose an internal ``_LiveEnv`` (bypasses ``RedEnv.__init__`` so it
doesn't new its own World) and reuse the inherited obs encoders + action
appliers from ``rl/red_env.py``. ``world`` and ``blue_fleet`` are exposed as
properties that resolve to the live Scenario state each call — no per-tick
rebind bookkeeping.

Decision cadence matches training (``DECISION_EVERY`` sim ticks between
``policy.predict`` calls). Intermediate ticks advance launcher timers on
the Blue side; no-op on Red (``RedLauncherFleet`` is ammo-less).

Numpy compat: imports ``_patch_numpy_core_for_legacy_pickle`` from
``rl/red_env.py`` and runs it at module-load so Boyu's numpy-2-pickled Blue
models load cleanly under the local numpy 1.26.

Smoke: ``python -m rl.live_ai`` loads Red2 + Blue1 against a fresh Scenario
and advances 10 ticks. Skips gracefully if models are absent.
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np
import gymnasium as gym

# Apply the numpy-core compat shim BEFORE any sb3_contrib import. Boyu's
# Blue models were pickled under numpy >= 2 where internal modules moved
# from numpy.core.* to numpy._core.*; the shim aliases them for the local
# numpy-1.26 env so MaskablePPO.load unpickles cleanly. Importing red_env
# defines the helper; we call it here (idempotent) so live_ai.py is safe
# whether or not red_env has been imported elsewhere first.
from rl.red_env import RedEnv, _patch_numpy_core_for_legacy_pickle
_patch_numpy_core_for_legacy_pickle()

from rl.env import DECISION_EVERY
from sim import sites as sites_module
from sim.launcher import LauncherFleet, RedLauncherFleet
from sim.types import THREAT_SPECS


def _load_policy(path: str):
    """Load a MaskablePPO policy from disk for CPU inference. Same pattern as
    ``rl/cross_eval.py`` — the numpy shim has already run at module load."""
    from sb3_contrib import MaskablePPO
    return MaskablePPO.load(path, device="cpu")


class _LiveEnv(RedEnv):
    """RedEnv variant bound to a live Scenario.

    Bypasses the normal ``RedEnv.__init__`` (which would new a World + load a
    Blue policy + wire gym spaces) so the wrappers can reuse the inherited
    obs encoders + action appliers without duplicating that logic. ``world``
    and ``blue_fleet`` are exposed as properties that resolve to the live
    Scenario state each call — no per-tick rebind, no stale references.

    A wrapper of the owning side's fleet is passed via ``own_blue_fleet`` for
    ``LearnedBlueAI`` (so its obs encoder reads the fleet it's also firing
    from). ``LearnedRedAI`` passes ``None`` and reads the Scenario's current
    Blue fleet (rule or learned, whichever is installed on ``scenario.blue``).
    """

    def __init__(self, scenario, own_blue_fleet: Optional[LauncherFleet] = None):
        # Skip RedEnv.__init__ entirely — we don't want a fresh World or a
        # second policy load. Only call gym.Env.__init__ so the base class is
        # consistent. We manually set every attribute the inherited obs +
        # action methods touch.
        gym.Env.__init__(self)
        self._scenario = scenario
        self._own_blue_fleet = own_blue_fleet
        self._seed = None
        self._episode_time_limit = float("inf")  # unused — no step() call
        self._n_sites = max(1, len(sites_module.SOUTH_SITES))
        self._total_site_hp = max(
            1, sum(s.hp_max for s in sites_module.SOUTH_SITES)
        )
        self.rng = np.random.default_rng()
        self.red_launchers = RedLauncherFleet()
        # Not used — kept for attribute parity with RedEnv since some
        # inherited methods may reference it in future changes.
        self.blue_policy = None
        self.blue = None
        self._cum_reward = 0.0

    @property
    def world(self):
        return self._scenario.world

    @world.setter
    def world(self, _v):
        # No-op — the Scenario owns the World. RedEnv.reset() would try to
        # reassign here; we never call reset() on this instance, but a
        # settable property is required for the parent's attribute contract.
        pass

    @property
    def blue_fleet(self):
        # LearnedBlueAI: always use the wrapper's own fleet (the one it fires
        # from) so obs encoding sees the same launcher state the policy is
        # driving. LearnedRedAI: read ``scenario.blue.launchers`` — resolves
        # to whatever is installed (rule BlueAI or LearnedBlueAI), preserving
        # cross-side visibility when both sides are learned.
        if self._own_blue_fleet is not None:
            return self._own_blue_fleet
        return self._scenario.blue.launchers

    @blue_fleet.setter
    def blue_fleet(self, _v):
        pass  # see world.setter


class LearnedRedAI:
    """Scenario-compatible learned-policy Red wrapper.

    Interface mirrors rule ``RedAI`` (attributes consumed by
    ``sim/scenarios.py`` and ``Scenario.snapshot``):

      * ``step(t_now, world)`` — called every sim tick by ``Scenario.step``.
      * ``done`` — ``Scenario.winner`` gates Blue-victory on this. Learned
        Red has no wave schedule, so we declare Red "done" via two rules:
        (1) ``world.red_budget < cheapest_threat_cost`` — Red can't afford
        any further spawn (same economic definition as ``cross_eval.py``).
        (2) no successful spawn for ``IDLE_TIMEOUT_S`` consecutive sim
        seconds — guards against a policy that hoards budget and never
        acts. Once True the flag latches (mirrors rule ``RedAI.done``
        which is also write-once).
      * ``log`` — tail shown in ``red_log`` snapshot key. Sparse one-liner
        per spawn decision.
      * ``launchers`` — a ``RedLauncherFleet`` so ``snap["red_launchers"]`` works.
      * ``waves``, ``_next_wave`` — stub-valued (empty / 0). Learned Red has
        no concept of waves; the frontend reads these for the ``wave`` /
        ``total_waves`` snapshot keys but they just show "wave 0/0" which
        is harmless in the learned-policy demo context.

    Decision cadence: policy predicts every ``DECISION_EVERY`` ticks to match
    training. Intermediate ticks are a no-op on Red's side.
    """

    # Idle-timeout window. A learned Red that hoards budget and never
    # spawns would otherwise run matches to the 3600 s safety cap; after
    # this many seconds of no spawn, Scenario.winner treats Red as done.
    IDLE_TIMEOUT_S = 120.0

    def __init__(self, policy_path: str, scenario):
        self._policy = _load_policy(policy_path)
        self._env = _LiveEnv(scenario)
        self._tick_counter = 0
        # Termination state -----------------------------------------------
        # `done` is latched once True — matches rule RedAI.done semantics
        # (all waves exhausted) and avoids flip-flopping if any future
        # bookkeeping change re-credits red_budget mid-match. Tracked
        # alongside the last successful spawn time so the idle-timeout
        # branch can fire against a hoarding policy.
        self._done_latched = False
        self._last_spawn_t = 0.0
        # Scenario attrs ---------------------------------------------------
        self.log: List[str] = []
        self.waves: List = []   # stub — see class docstring
        self._next_wave = 0     # stub
        # Share the RedLauncherFleet with the internal _LiveEnv so
        # ``snap["red_launchers"] = self.red.launchers.fleet_status()``
        # observes the same round-robin index the policy action applier
        # advances via ``_pick_spawn``.
        self.launchers = self._env.red_launchers

    @property
    def done(self) -> bool:
        if self._done_latched:
            return True
        cheapest = min(spec.usd_cost for spec in THREAT_SPECS.values())
        if self._env.world.red_budget < cheapest:
            self._done_latched = True
            return True
        # Idle timeout — only meaningful after the match has actually
        # been running. The `t_now > IDLE_TIMEOUT_S` guard stops the
        # initial zero-initialized `_last_spawn_t` from tripping this
        # at t=IDLE_TIMEOUT_S before Red has had a real chance to act.
        t_now = self._env.world.t
        if t_now > self.IDLE_TIMEOUT_S and (t_now - self._last_spawn_t) > self.IDLE_TIMEOUT_S:
            self._done_latched = True
            return True
        return False

    def step(self, t_now: float, world) -> None:
        # Gate policy prediction to every DECISION_EVERY ticks to match
        # training cadence. RedLauncherFleet has no ammo/CD timers so
        # intermediate ticks don't need any bookkeeping.
        if self._tick_counter % DECISION_EVERY == 0:
            obs = self._env._encode_obs()
            mask = obs["action_mask"]
            action, _ = self._policy.predict(
                obs, deterministic=True, action_masks=mask
            )
            action_arr = np.asarray(action).reshape(-1)
            spawned, cost_usd = self._env._apply_action(action_arr)
            if spawned:
                self._last_spawn_t = t_now
                kind_idx = int(action_arr[0])
                self.log.append(
                    f"[{t_now:6.1f}s] learned_red spawn k{kind_idx} "
                    f"cost=${cost_usd/1e6:.1f}M"
                )
        self._tick_counter += 1


class LearnedBlueAI:
    """Scenario-compatible learned-policy Blue wrapper.

    Interface mirrors rule ``BlueAI``:

      * ``step(t_now, world)`` — called every sim tick.
      * ``log`` — tail shown in ``blue_log`` snapshot key.
      * ``launchers`` — a ``LauncherFleet`` (the one the wrapper fires from).
        ``snap["ammo"]`` and ``snap["launchers"]`` read off this via
        ``fleet_status(t_now)``.

    Decision cadence: policy predicts every ``DECISION_EVERY`` ticks. Fleet
    timers ``.tick(t_now)`` advance every call (matches rule BlueAI's line 1
    in ``BlueAI.step``) so reload/CD are consistent with training.
    """

    def __init__(self, policy_path: str, scenario):
        self._policy = _load_policy(policy_path)
        # Own fleet — policy fires from this, snapshot reads from this.
        self.launchers = LauncherFleet()
        self._env = _LiveEnv(scenario, own_blue_fleet=self.launchers)
        self._tick_counter = 0
        self.log: List[str] = []

    def step(self, t_now: float, world) -> None:
        # Reload/CD timers MUST advance every tick — matches rule BlueAI
        # line 1 (launchers.tick). Policy only predicts at decision ticks.
        self.launchers.tick(t_now)
        if self._tick_counter % DECISION_EVERY == 0:
            obs = self._env._encode_obs_blue()
            # Flat int8 mask for MaskablePPO consumption (parent uses
            # ``.reshape(-1).astype(np.int8)`` in cross_eval.py).
            mask_flat = obs["action_mask"].reshape(-1).astype(np.int8)
            action, _ = self._policy.predict(
                obs, deterministic=True, action_masks=mask_flat
            )
            n_fires = self._env._apply_blue_action(
                np.asarray(action).reshape(-1)
            )
            if n_fires:
                self.log.append(
                    f"[{t_now:6.1f}s] learned_blue fires={n_fires}"
                )
        self._tick_counter += 1


# ----------------------------------------------------------------------
# Smoke test entry point — ``python -m rl.live_ai``
# ----------------------------------------------------------------------
def _smoke_main() -> int:
    """Load Red2 + Blue1 (if available) against a fresh Scenario, advance 10
    sim ticks. Prints progress; skips gracefully if models are absent."""
    import pathlib

    here = pathlib.Path(__file__).resolve().parent
    backend = here.parent
    red2 = backend / "rl" / "runs" / "red_20260421_234425" / "model.zip"
    blue1 = backend / "rl" / "models" / "blue_ai_1m_2xpenalty" / "model.zip"

    print("=== live_ai smoke ===")
    if not red2.exists():
        print(f"[SKIP] Red2 model missing at {red2}")
        return 0

    from sim.config import DT
    from sim.scenarios import build_default_scenario

    scn = build_default_scenario(auto_start=True)
    scn.red = LearnedRedAI(str(red2), scn)
    print(f"[OK] Loaded learned Red: {red2.name}")

    if blue1.exists():
        scn.blue = LearnedBlueAI(str(blue1), scn)
        print(f"[OK] Loaded learned Blue: {blue1.name}")
    else:
        print(f"[INFO] Blue1 missing — using rule BlueAI")

    for i in range(10):
        scn.step(DT)
    print(
        f"[OK] 10 ticks advanced: t={scn.world.t:.3f}s, "
        f"phase={scn.world.phase.value}, "
        f"threats={len(scn.world.threats)}, "
        f"interceptors={len(scn.world.interceptors)}"
    )
    print("Smoke OK.")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_smoke_main())
