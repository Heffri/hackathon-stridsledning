"""Cross-evaluation harness — learned-vs-learned (or rule) Red × Blue play.

Runs one episode of arbitrary Red × Blue controller pairs. Each side is
independently either:

  * ``"rule"``  — rule-based AI (``RedAI(build_demo_waves())`` or ``BlueAI()``)
  * a path str  — MaskablePPO model loaded from disk (CPU inference)

Sim loop mirrors ``rl.env.MissileInterceptEnv`` / ``rl.red_env.RedEnv``:
every ``DECISION_EVERY`` sim ticks each learned side predicts ONCE (masked);
rule sides call their ``.step`` every inner tick. Winner resolution matches
``Scenario.winner`` modulo a configurable episode time limit (default
``MAX_EPISODE_SIM_TIME`` = 600 s, same as training distribution).

Composition: subclasses ``RedEnv`` so the obs encoder, both action-mask
builders (Red flat + Blue 2D), and both action appliers come for free.
``RedEnv.step()`` is not called — ``run_episode()`` is the entry point.

Run ``python -m rl.cross_eval`` for a 2-episode sanity check
(rule_Red vs rule_Blue baseline + Red1 vs Blue1 learned).
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from sim import sites as sites_module
from sim.blue_ai import BlueAI
from sim.config import DT
from sim.launcher import LauncherFleet
from sim.red_ai import RedAI, build_demo_waves
from sim.types import (
    INTERCEPTOR_SPECS,
    InterceptorType,
    MatchPhase,
    THREAT_SPECS,
    ThreatType,
)

from rl.env import DECISION_EVERY, MAX_EPISODE_SIM_TIME
from rl.red_env import RedEnv, _patch_numpy_core_for_legacy_pickle


# Sentinel used in policy spec strings for the rule-based controllers.
RULE_SENTINEL = "rule"


@dataclass
class EpisodeResult:
    """Single-episode rollup. ``winner`` is ``"red" | "blue" | "draw"`` — the
    harness normalises a ``None`` winner at time-limit truncation to
    ``"draw"``.

    ``red_spawns_by_kind`` and ``blue_launches_by_kind`` key on the string
    value of the enum (``"drone"`` / ``"ciws"`` / ...) so JSON round-trip
    is trivial.
    """
    winner: str
    episode_length: int
    sim_time: float
    sites_destroyed: int
    sites_total_damage: int
    red_budget_remaining: int
    blue_budget_remaining: int
    red_spawns_by_kind: Dict[str, int] = field(default_factory=dict)
    blue_launches_by_kind: Dict[str, int] = field(default_factory=dict)
    intercept_count: int = 0
    leak_count: int = 0
    ground_crash_count: int = 0

    def to_dict(self) -> dict:
        return {
            "winner": self.winner,
            "episode_length": self.episode_length,
            "sim_time": self.sim_time,
            "sites_destroyed": self.sites_destroyed,
            "sites_total_damage": self.sites_total_damage,
            "red_budget_remaining": self.red_budget_remaining,
            "blue_budget_remaining": self.blue_budget_remaining,
            "red_spawns_by_kind": self.red_spawns_by_kind,
            "blue_launches_by_kind": self.blue_launches_by_kind,
            "intercept_count": self.intercept_count,
            "leak_count": self.leak_count,
            "ground_crash_count": self.ground_crash_count,
        }


def _is_rule(spec: str) -> bool:
    return spec == RULE_SENTINEL


def _load_policy(path: str):
    """Load a MaskablePPO model from disk with the numpy-core compat shim."""
    _patch_numpy_core_for_legacy_pickle()
    from sb3_contrib import MaskablePPO
    return MaskablePPO.load(path, device="cpu")


class CrossEvalEnv(RedEnv):
    """Cross-evaluation harness (subclass of ``RedEnv``).

    Inherits the obs encoder, both action-mask builders, and both action
    appliers so the eval harness uses bit-identical conventions to
    training (kind orderings, normalization scales, mask layouts). Adds a
    top-level ``run_episode()`` that dispatches rule-vs-learned per side.
    """

    def __init__(
        self,
        red_spec: str,
        blue_spec: str,
        seed: Optional[int] = None,
        episode_time_limit: float = MAX_EPISODE_SIM_TIME,
    ):
        self.red_spec = red_spec
        self.blue_spec = blue_spec

        # Load Red policy once here. Defensive: call the numpy-core shim
        # before any sb3_contrib import even for the Red side — Red1/Red2
        # were pickled under the local numpy 1.26 so the shim is a no-op
        # for them, but nothing breaks by running it.
        if _is_rule(red_spec):
            self.red_policy = None
        else:
            _patch_numpy_core_for_legacy_pickle()
            from sb3_contrib import MaskablePPO
            self.red_policy = MaskablePPO.load(red_spec, device="cpu")

        # Blue policy path is forwarded to RedEnv.__init__ which already
        # handles loading + wiring self.blue_policy / self.blue_fleet in
        # reset(). None → rule Blue (BlueAI owns its own LauncherFleet).
        blue_path = None if _is_rule(blue_spec) else blue_spec
        super().__init__(
            seed=seed,
            episode_time_limit=episode_time_limit,
            blue_policy_path=blue_path,
        )

        # Rule-Red AI (instantiated in reset()). None when learned Red.
        self.red_ai: Optional[RedAI] = None

    # ------------------------------------------------------------------
    def reset(self, seed: Optional[int] = None, options=None):
        """Standard RedEnv reset + rule-Red setup if Red is rule-based.

        Rule RedAI's internal ``rng`` is replaced with a seeded generator
        so paired comparisons (same seed across different Blue opponents)
        produce the same threat-sampling sequence.
        """
        obs, info = super().reset(seed=seed, options=options)
        if _is_rule(self.red_spec):
            self.red_ai = RedAI(build_demo_waves())
            # Seed the AI's private RNG for reproducible spawn sampling
            # under paired comparison. RedAI.__init__ defaults to fresh
            # entropy; we override so identical (seed) → identical
            # rule-Red trajectory regardless of Blue opponent.
            self.red_ai.rng = np.random.default_rng(self._seed)
        else:
            self.red_ai = None

        # Per-episode metrics
        self._red_spawns_by_kind: Dict[str, int] = {
            k.value: 0 for k in ThreatType
        }
        self._blue_launches_by_kind: Dict[str, int] = {
            k.value: 0 for k in InterceptorType
        }
        self._intercept_count = 0
        self._leak_count = 0
        self._ground_crash_count = 0
        self._n_decisions = 0
        return obs, info

    # ------------------------------------------------------------------
    def run_episode(self, seed: Optional[int] = None) -> EpisodeResult:
        """Play one episode end-to-end. Returns ``EpisodeResult``.

        Decision tick:
          * Learned Blue (if any) predicts + fires at the boundary.
          * Learned Red (if any) predicts + spawns at the boundary.
          * DECISION_EVERY inner ticks advance the sim; rule sides step
            each tick, learned-side fleets only tick (no re-predict).

        Event accumulation differs from ``RedEnv.step``: we do NOT clear
        ``world.events`` between inner ticks while counting decision-
        level events. RedEnv clears because its reward fn runs per-tick;
        we only need per-decision aggregate counts.
        """
        self.reset(seed=seed)

        while True:
            # Events emitted by learned-side appliers at the decision
            # boundary (launch / threat_spawn) would be wiped by the
            # inner-loop's ``self.world.events = []`` reset used in
            # RedEnv.step. We explicitly drain them into ``step_events``
            # before the inner loop runs so spawn / launch counts stay
            # accurate even under the event-reset dance.
            step_events: List[dict] = []

            if self.blue_policy is not None:
                blue_obs = self._encode_obs_blue()
                blue_mask_flat = (
                    blue_obs["action_mask"].reshape(-1).astype(np.int8)
                )
                blue_action, _ = self.blue_policy.predict(
                    blue_obs,
                    deterministic=True,
                    action_masks=blue_mask_flat,
                )
                self._apply_blue_action(
                    np.asarray(blue_action).reshape(-1)
                )
                step_events.extend(self.world.events)
                self.world.events = []

            if self.red_policy is not None:
                red_obs = self._encode_obs()
                red_mask = red_obs["action_mask"]
                red_action, _ = self.red_policy.predict(
                    red_obs,
                    deterministic=True,
                    action_masks=red_mask,
                )
                self._apply_action(
                    np.asarray(red_action).reshape(-1)
                )
                step_events.extend(self.world.events)
                self.world.events = []

            self._n_decisions += 1

            for _ in range(DECISION_EVERY):
                self.world.events = []
                if self.red_ai is not None:
                    self.red_ai.step(self.world.t, self.world)
                if self.blue_ai is not None:
                    self.blue_ai.step(self.world.t, self.world)
                else:
                    # Learned Blue: fleet reload / CD timers tick, but
                    # firing decisions already made ONCE at the top of
                    # this decision.
                    self.blue_fleet.tick(self.world.t)
                self.world.step(DT)
                step_events.extend(self.world.events)
                self.world.prune_dead()

                w = self._cross_winner()
                if w is not None:
                    self._count_events(step_events)
                    return self._finalize(w)
                if self.world.t >= self._episode_time_limit:
                    self._count_events(step_events)
                    return self._finalize("draw")

            self._count_events(step_events)

    # ------------------------------------------------------------------
    @property
    def blue_ai(self) -> Optional[BlueAI]:
        """Alias for ``self.blue`` — clearer naming inside the harness.
        Parent sets ``self.blue = BlueAI()`` when blue_policy is None,
        else ``self.blue = None``.
        """
        return self.blue

    # ------------------------------------------------------------------
    def _cross_winner(self) -> Optional[str]:
        """Winner resolver — mirrors ``Scenario.winner`` modulo rule/learned
        Red dispatch.

        * Red wins when all military sites (subtypes air_base + base) are
          at HP=0. Matches ``Scenario.winner`` directly.
        * Blue wins when Red cannot spawn more AND no live Red threats
          remain. "Cannot spawn more":
            * Rule Red: ``red_ai.done`` OR budget < cheapest threat.
            * Learned Red: budget < cheapest threat (no "done" concept).
        * ``None`` otherwise — caller treats time-limit truncation as
          draw.
        """
        military = [
            s for s in sites_module.SOUTH_SITES
            if s.subtype in ("air_base", "base")
        ]
        if military and all(s.hp <= 0 for s in military):
            return "red"

        cheapest = min(spec.usd_cost for spec in THREAT_SPECS.values())
        red_broke = self.world.red_budget < cheapest
        if self.red_ai is not None:
            red_cant_spawn = self.red_ai.done or red_broke
        else:
            red_cant_spawn = red_broke
        no_threats = all(
            not t.state.alive for t in self.world.threats.values()
        )
        if red_cant_spawn and no_threats:
            return "blue"
        return None

    # ------------------------------------------------------------------
    def _count_events(self, events: List[dict]) -> None:
        """Accumulate per-decision event counts into episode totals."""
        for ev in events:
            et = ev.get("type")
            if et == "threat_spawn":
                k = ev.get("kind")
                if k is not None:
                    self._red_spawns_by_kind[k] = (
                        self._red_spawns_by_kind.get(k, 0) + 1
                    )
            elif et == "launch":
                k = ev.get("kind")
                if k is not None:
                    self._blue_launches_by_kind[k] = (
                        self._blue_launches_by_kind.get(k, 0) + 1
                    )
            elif et == "intercept":
                self._intercept_count += 1
            elif et == "leak":
                self._leak_count += 1
            elif et == "ground_crash" and ev.get("threat") is not None:
                # Gate on 'threat' key so interceptor ground crashes
                # (which share the event type) don't count.
                self._ground_crash_count += 1

    # ------------------------------------------------------------------
    def _finalize(self, winner: str) -> EpisodeResult:
        """Build an ``EpisodeResult`` from the current world / metric state."""
        sites = list(sites_module.SOUTH_SITES)
        sites_destroyed = sum(1 for s in sites if s.hp <= 0)
        sites_total_damage = sum(max(0, s.hp_max - s.hp) for s in sites)
        return EpisodeResult(
            winner=winner,
            episode_length=self._n_decisions,
            sim_time=float(self.world.t),
            sites_destroyed=sites_destroyed,
            sites_total_damage=sites_total_damage,
            red_budget_remaining=int(self.world.red_budget),
            blue_budget_remaining=int(self.world.blue_budget),
            red_spawns_by_kind=dict(self._red_spawns_by_kind),
            blue_launches_by_kind=dict(self._blue_launches_by_kind),
            intercept_count=self._intercept_count,
            leak_count=self._leak_count,
            ground_crash_count=self._ground_crash_count,
        )


# ----------------------------------------------------------------------
# Sanity-test entry point
# ----------------------------------------------------------------------
def _print_result(label: str, r: EpisodeResult, wall: float) -> None:
    total_spawns = sum(r.red_spawns_by_kind.values())
    total_launches = sum(r.blue_launches_by_kind.values())
    print(
        f"[OK] {label:30s} winner={r.winner:5s} "
        f"len={r.episode_length:4d} sim={r.sim_time:6.1f}s "
        f"sites_dead={r.sites_destroyed} dmg={r.sites_total_damage:4d} "
        f"red_spawns={total_spawns:3d} blue_fires={total_launches:3d} "
        f"intercepts={r.intercept_count:3d} leaks={r.leak_count:2d} "
        f"| wall={wall:4.1f}s"
    )


def _smoke_main() -> int:
    """Two-episode sanity: rule-vs-rule + Red1-vs-Blue1 learned."""
    import os
    import pathlib

    # Resolve model paths relative to ``backend/`` (where `python -m rl.cross_eval`
    # is launched from). Falls back gracefully if absent.
    here = pathlib.Path(__file__).resolve().parent
    backend = here.parent
    red1 = backend / "rl" / "runs" / "red_20260421_205051" / "model.zip"
    blue1 = backend / "rl" / "models" / "blue_ai_1m_2xpenalty" / "model.zip"

    print("=== CrossEvalEnv smoke (2 episodes) ===")

    # Ep 1: rule Red vs rule Blue — baseline (Boyu's training distribution
    # for Blue's default-rule-Red opponent).
    t0 = time.time()
    env = CrossEvalEnv(
        red_spec=RULE_SENTINEL, blue_spec=RULE_SENTINEL, seed=42,
    )
    r1 = env.run_episode(seed=42)
    _print_result("rule_Red vs rule_Blue", r1, time.time() - t0)

    # Ep 2: Red1 vs Blue1 — main-event cross-eval.
    if not red1.exists() or not blue1.exists():
        print(
            f"[SKIP] Red1 or Blue1 model missing; cannot run learned-vs-learned.\n"
            f"  red1:  {red1}\n"
            f"  blue1: {blue1}"
        )
        return 0

    t0 = time.time()
    env = CrossEvalEnv(
        red_spec=str(red1), blue_spec=str(blue1), seed=42,
    )
    r2 = env.run_episode(seed=42)
    _print_result("Red1 vs Blue1", r2, time.time() - t0)

    print("\nSanity OK.")
    return 0


if __name__ == "__main__":
    sys.exit(_smoke_main())
