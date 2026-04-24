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

from typing import Dict, List, Optional

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

from rl.env import DECISION_EVERY, MAX_THREATS
from sim import sites as sites_module
from sim.config import LAUNCH_RANGE_MARGIN
from sim.launcher import LauncherFleet, RedLauncherFleet
from sim.types import INTERCEPTOR_SPECS, InterceptorType, THREAT_SPECS, ThreatType


# Per-threat saturation cap (W2, 2026-04-23). Cheap threats get a
# tighter cap so the policy can't dump 3 IRIS-T SLM ($3 M) on a single
# $30 K drone — the rule version is one cap-3 across all kinds, which
# is fine when expected-damage gates also stop SLM piling on a low-HP
# target, but the wrapper has no such gate so a per-kind cap is the
# cheapest way to bound over-engagement on cheap targets. CIWS rounds
# stay exempt (cannon class — see Gate 2 below). The 2/3 split mirrors
# the operator brief: hard targets (BALLISTIC / HGV) earn saturation,
# cheap targets (DRONE / CRUISE) don't.
SATURATION_CAP_BY_KIND: Dict[ThreatType, int] = {
    ThreatType.DRONE:      2,
    ThreatType.CRUISE_SUB: 2,
    ThreatType.BALLISTIC:  3,
    ThreatType.HGV:        3,
}
DEFAULT_SATURATION_CAP = 3


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
        # Sentinel-init so the idle-timeout branch can't self-latch before
        # the first spawn (audit 2026-04-22 F3): prior `_last_spawn_t=0.0`
        # with the guard `t_now > 120 and t_now - _last_spawn_t > 120`
        # trips at t=120.05 if Red never spawned, flipping done=True and
        # ending the match via the red_done + no_threats Blue-win path.
        # None = "never spawned"; idle-check skips until the first spawn
        # records a real timestamp.
        self._last_spawn_t: Optional[float] = None
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
        # Idle timeout — only meaningful once Red has actually spawned
        # at least once. With sentinel-init `_last_spawn_t=None`, the
        # idle-check is skipped until the first spawn records a real
        # timestamp; after that, >IDLE_TIMEOUT_S of silence latches done.
        t_now = self._env.world.t
        if (
            self._last_spawn_t is not None
            and (t_now - self._last_spawn_t) > self.IDLE_TIMEOUT_S
        ):
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

    Safety filters on top of the policy: the wrapper now trusts the
    trained policy's cost-exchange and target-selection judgment (the
    blue_aoe_mixed model — 2.3 M cumulative steps — is strong enough
    that the earlier ALLOWED_INTERCEPTORS allowlist and the
    force-ballistic fallback distorted its behaviour more than they
    helped). Two gates remain, both economic:

      * Budget gate — hard refusal if ``world.blue_budget <
        spec.usd_cost`` (no clamp). Prevents the training env's
        ``max(0, ...)`` clamp from letting the policy fire for free
        after the budget empties.
      * Saturation cap — per-kind via ``SATURATION_CAP_BY_KIND``
        (DRONE / CRUISE: 2; BALLISTIC / HGV: 3). CIWS is a cannon,
        exempt from the cap (same carve-out as ``BlueAI.step``).

    Retarget-on-death of orphaned interceptors is handled in
    ``World.step`` (the arcade AOE reacquire hook). The previous
    wrapper-level orphan cleanup that marked any interceptor with a
    dead ``state.target_id`` as dead was removed (2026-04-24, Bug 8):
    it killed retargeted interceptors because retargeting only updates
    ``inter.target_id``, not the mirrored ``state.target_id`` — so
    freshly retargeted interceptors visibly swung onto a new threat,
    then disappeared within a few frames. The live-fix pass also
    restored ``state.target_id`` write-through in World.step so any
    downstream consumer (HUD, telemetry) stays accurate.
    """

    # Mirror ``sim/blue_ai.py::MAX_SIMULTANEOUS_PER_THREAT``. Excludes
    # CIWS (point-defense cannon — has its own per-threat shot budget
    # in the rule AI; simpler here to just exempt it from this cap).
    # W2 (2026-04-23): per-kind cap via ``SATURATION_CAP_BY_KIND``;
    # this constant kept as the legacy default for callers that haven't
    # been migrated.
    MAX_SIMULTANEOUS_PER_THREAT = 3

    def __init__(self, policy_path: str, scenario):
        self._policy = _load_policy(policy_path)
        # Own fleet — policy fires from this, snapshot reads from this.
        self.launchers = LauncherFleet()
        self._env = _LiveEnv(scenario, own_blue_fleet=self.launchers)
        self._tick_counter = 0
        self.log: List[str] = []
        # Saturation-cap bookkeeping: threat_id → list of live
        # interceptor_ids assigned. Mirrors ``BlueAI.assignments`` in
        # ``sim/blue_ai.py``. Pruned each tick before the policy
        # decides.
        self._assignments: Dict[int, List[int]] = {}

    def step(self, t_now: float, world) -> None:
        # Reload/CD timers MUST advance every tick — matches rule BlueAI
        # line 1 (launchers.tick). Policy only predicts at decision ticks.
        self.launchers.tick(t_now)

        # Prune assignments: drop dead threats entirely, and inside each
        # live threat's list drop dead/missing interceptors. Keeps the
        # saturation-cap count accurate.
        for tid in list(self._assignments.keys()):
            threat = world.threats.get(tid)
            if threat is None or not threat.state.alive:
                self._assignments.pop(tid, None)
                continue
            live = [
                iid for iid in self._assignments[tid]
                if iid in world.interceptors
                and world.interceptors[iid].state.alive
            ]
            if live:
                self._assignments[tid] = live
            else:
                self._assignments.pop(tid, None)

        # Retargeting of orphaned interceptors (target died) is handled in
        # ``World.step``'s arcade AOE reacquire hook — it picks the nearest
        # alive threat still in launcher range and swaps ``inter.target_id``
        # (with ``state.target_id`` mirrored since Bug 8). Interceptors
        # that don't find a replacement coast to the
        # ``config.INTERCEPT_TIMEOUT`` (80 s) or stall-out branch in
        # ``entities.Interceptor``. The wrapper does not override this.

        if self._tick_counter % DECISION_EVERY == 0:
            obs = self._env._encode_obs_blue()
            # Flat int8 mask for MaskablePPO consumption (parent uses
            # ``.reshape(-1).astype(np.int8)`` in cross_eval.py).
            mask_flat = obs["action_mask"].reshape(-1).astype(np.int8)
            action, _ = self._policy.predict(
                obs, deterministic=True, action_masks=mask_flat
            )
            n_fires = self._apply_action_gated(
                np.asarray(action).reshape(-1), t_now,
            )
            if n_fires:
                self.log.append(
                    f"[{t_now:6.1f}s] learned_blue fires={n_fires}"
                )
        self._tick_counter += 1

    def _apply_action_gated(self, action: np.ndarray, t_now: float) -> int:
        """Execute the policy's action with rule-layer safety gates.

        Replaces the direct ``_LiveEnv._apply_blue_action`` call. Same
        action contract (``MAX_LAUNCHERS`` ints in ``[0, MAX_THREATS]``,
        ``MAX_THREATS`` = hold, else target-slot index) but adds two
        economic gates the training env doesn't enforce:

          * Budget: refuse if ``world.blue_budget < spec.usd_cost`` —
            hard refusal, not a ``max(0, ...)`` clamp (which was the
            "free fires after $0" bug).
          * Saturation: skip non-CIWS launches once this threat already
            has the per-kind cap of non-CIWS interceptors in flight.
            Cap table in ``SATURATION_CAP_BY_KIND`` (DRONE / CRUISE 2,
            BALLISTIC / HGV 3). CIWS is exempt.
          * Launcher readiness + range: defensive re-check (mask
            already filters these in principle).

        The earlier cost-exchange allowlist (``ALLOWED_INTERCEPTORS``)
        and the post-policy ``_force_ballistic_fallback`` dispatcher
        were removed 2026-04-24 (Bug 7) — the blue_aoe_mixed policy
        (2.3 M cumulative steps) has internalised cost-exchange well
        enough that the allowlist was distorting more than helping,
        and the fallback was originating fires the policy had
        deliberately deferred.

        On a successful spawn the new interceptor's id is recorded in
        ``self._assignments`` so the cap is honoured across ticks in
        the same match. Returns the count of shots fired.
        """
        world = self._env.world
        launchers = self.launchers.launchers
        threats = self._env._alive_threats()
        n_fires = 0
        for l_idx, a in enumerate(action):
            if l_idx >= len(launchers):
                break
            a_int = int(a)
            if a_int >= MAX_THREATS:
                continue  # hold
            if a_int >= len(threats):
                continue  # pad slot
            lch = launchers[l_idx]
            if lch.reloading or not lch.can_fire(t_now):
                continue
            threat = threats[a_int]
            if not threat.state.alive:
                continue
            threat_kind = ThreatType(threat.state.kind)
            spec = INTERCEPTOR_SPECS[lch.kind]
            # Gate 1: budget — hard refusal, no clamp.
            if world.blue_budget < spec.usd_cost:
                continue
            # Gate 2: saturation cap (non-CIWS only). Per-kind via
            # ``SATURATION_CAP_BY_KIND`` (W2): cheap threats (DRONE /
            # CRUISE) cap at 2 to stop the policy spending $3 M of SLM
            # on a $30 K target, hard threats (BALLISTIC / HGV) keep
            # cap-3 so layered defense can stack.
            tid_target = threat.state.id
            if lch.kind != InterceptorType.CIWS:
                cap = SATURATION_CAP_BY_KIND.get(
                    threat_kind, DEFAULT_SATURATION_CAP,
                )
                if len(self._assignments.get(tid_target, [])) >= cap:
                    continue
            # Defensive range re-check (mirrors _apply_blue_action).
            t_pos = threat.state.pos
            dx = float(t_pos[0] - lch.pos[0])
            dy = float(t_pos[1] - lch.pos[1])
            dz = float(t_pos[2])
            if (dx * dx + dy * dy + dz * dz) > \
                    (spec.max_range * LAUNCH_RANGE_MARGIN) ** 2:
                continue
            mode = lch.fire(t_now)
            iid = world.spawn_interceptor(
                lch.kind,
                (lch.pos[0], lch.pos[1], 0.0),
                (dx, dy, dz),
                tid_target,
                mode,
            )
            # Unclamped — gate above guarantees budget >= cost.
            world.blue_budget -= spec.usd_cost
            self._assignments.setdefault(tid_target, []).append(iid)
            n_fires += 1
        return n_fires


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
