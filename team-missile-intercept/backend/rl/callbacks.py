"""SB3 callbacks for AOE curriculum training.

`MetricsCallback`:
  * Reads `info` from each env's step on episode end (terminated OR
    truncated signal from Monitor wrapper).
  * Tallies per-kind fires / intercepts / leaks from the `info['events']`
    stream (requires `sim.world` to emit `kind` on intercept/damage, and
    already emits `kind` on leak + `launch`).
  * Logs scalars to SB3's tensorboard logger (`custom/...`) on rollout
    end (so the TB cadence matches the default PPO update interval).
  * Appends one JSON line per episode to `run_dir/metrics.jsonl` —
    post-run plotting reads this directly.

Rolling window default: last 100 episodes. Short enough to react to
collapse, long enough to smooth per-episode noise.
"""
from __future__ import annotations

import json
from collections import Counter, deque
from pathlib import Path
from typing import Deque, Dict, List, Optional

from stable_baselines3.common.callbacks import BaseCallback


_LAUNCHER_KINDS = (
    "ciws", "rbs_70", "iris_t_sls", "iris_t_slm", "pac_2", "pac_3",
)
_SHORT_RANGE_KINDS = ("ciws", "rbs_70", "iris_t_sls")
_THREAT_KINDS = ("drone", "cruise_sub", "ballistic", "hgv")


def _tally_events(events: List[dict]) -> Dict[str, Dict[str, int]]:
    """Walk an episode's event stream, bucket by kind. Returns
    `{'fires': {kind: n}, 'intercepts': {kind: n}, 'leaks': {kind: n}}`.

    Fires are counted from `launch` events (interceptor launch by
    BlueAI or RL). Intercepts + leaks track Red threats killed / landed.
    """
    fires = Counter()
    intercepts = Counter()
    leaks = Counter()
    for ev in events:
        et = ev.get("type")
        if et == "launch":
            k = ev.get("kind")
            if k:
                fires[k] += 1
        elif et == "intercept":
            k = ev.get("kind")
            if k:
                intercepts[k] += 1
        elif et == "leak":
            k = ev.get("kind")
            if k:
                leaks[k] += 1
    return {
        "fires": dict(fires),
        "intercepts": dict(intercepts),
        "leaks": dict(leaks),
    }


class MetricsCallback(BaseCallback):
    """Per-episode custom metrics → tensorboard + metrics.jsonl.

    Works with VecEnv wrapped via VecMonitor (`stable_baselines3.common
    .vec_env.VecMonitor`). Monitor attaches an `episode` dict to `info`
    when an episode ends; we use our own `info["winner"]` / `terminated`
    / `truncated` signal since Monitor's `episode` only has r + l + t.
    """

    def __init__(self, run_dir: str, log_freq: int = 1, window: int = 100, verbose: int = 0):
        super().__init__(verbose=verbose)
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.jsonl_path = self.run_dir / "metrics.jsonl"
        self.log_freq = log_freq
        self.window = window
        # Rolling buffers (one deque per metric; len == episodes seen)
        self._winners: Deque[str] = deque(maxlen=window)
        self._hp_end: Deque[float] = deque(maxlen=window)
        self._sim_t: Deque[float] = deque(maxlen=window)
        self._fires: Dict[str, Deque[int]] = {
            k: deque(maxlen=window) for k in _LAUNCHER_KINDS
        }
        self._intercepts: Dict[str, Deque[int]] = {
            k: deque(maxlen=window) for k in _THREAT_KINDS
        }
        self._leaks: Dict[str, Deque[int]] = {
            k: deque(maxlen=window) for k in _THREAT_KINDS
        }
        self._truncated: Deque[int] = deque(maxlen=window)
        self._layout_counts: Counter = Counter()
        self._ep_idx = 0
        # Per-env accumulators — info["events"] only carries this-step's
        # events, so we tally across all steps of an episode and reset
        # on episode done. `_per_env` keyed by env index; lazily grown.
        self._per_env_events: Dict[int, List[dict]] = {}
        self._per_env_trunc_peak: Dict[int, int] = {}
        # Open append once (line-buffered for resilience).
        self._fp = open(self.jsonl_path, "a", encoding="utf-8")

    # ------------------------------------------------------------------
    def _on_step(self) -> bool:
        infos = self.locals.get("infos") or []
        dones = self.locals.get("dones")
        if dones is None:
            dones = [False] * len(infos)
        for env_idx, (info, done) in enumerate(zip(infos, dones)):
            # Accumulate this-step's events into the per-env bucket —
            # info["events"] only carries events from the last decision
            # tick, so we need the running tally to compute per-episode
            # fires/intercepts/leaks correctly.
            step_events = info.get("events", []) or []
            if step_events:
                self._per_env_events.setdefault(env_idx, []).extend(step_events)
            trunc = int(info.get("threats_truncated", 0))
            prev = self._per_env_trunc_peak.get(env_idx, 0)
            if trunc > prev:
                self._per_env_trunc_peak[env_idx] = trunc
            if not done:
                continue
            # Episode done — finalize using accumulated events.
            self._record_episode(info, env_idx)
            self._per_env_events.pop(env_idx, None)
            self._per_env_trunc_peak.pop(env_idx, None)
        return True

    # ------------------------------------------------------------------
    def _record_episode(self, info: dict, env_idx: int = -1) -> None:
        self._ep_idx += 1
        if env_idx >= 0 and env_idx in self._per_env_events:
            events = self._per_env_events[env_idx]
            trunc_peak = self._per_env_trunc_peak.get(env_idx, 0)
        else:
            events = info.get("events", []) or []
            trunc_peak = int(info.get("threats_truncated", 0))
        tally = _tally_events(events)
        winner = info.get("winner")
        self._winners.append(winner or "truncated")
        hp_end = float(info.get("site_hp_total", 0))
        self._hp_end.append(hp_end)
        self._sim_t.append(float(info.get("sim_t", 0.0)))
        self._truncated.append(int(trunc_peak))
        slot = info.get("layout_slot")
        if slot is not None:
            self._layout_counts[slot] += 1
        for k in _LAUNCHER_KINDS:
            self._fires[k].append(int(tally["fires"].get(k, 0)))
        for k in _THREAT_KINDS:
            self._intercepts[k].append(int(tally["intercepts"].get(k, 0)))
            self._leaks[k].append(int(tally["leaks"].get(k, 0)))
        # JSONL dump — one line per episode, trivially post-processable.
        record = {
            "ep_idx": self._ep_idx,
            "step": int(self.num_timesteps),
            "winner": winner,
            "terminal_reason": info.get("terminal_reason"),
            "reward": float(info.get("cum_reward", 0.0)),
            "sim_t": float(info.get("sim_t", 0.0)),
            "site_hp_end": hp_end,
            "fires_by_kind": tally["fires"],
            "leaks_by_kind": tally["leaks"],
            "intercepts_by_kind": tally["intercepts"],
            "layout_slot": slot,
            "threats_truncated_max": int(trunc_peak),
            "alive_threats_total": int(info.get("alive_threats_total", 0)),
        }
        self._fp.write(json.dumps(record) + "\n")
        self._fp.flush()

    # ------------------------------------------------------------------
    def _on_rollout_end(self) -> None:
        """Emit rolling-window aggregates to tensorboard. SB3 calls
        this after each n_steps rollout (before the PPO update)."""
        if not self._winners:
            return
        n = len(self._winners)
        win_rate = sum(1 for w in self._winners if w == "blue") / n
        loss_rate = sum(1 for w in self._winners if w == "red") / n
        draw_rate = sum(
            1 for w in self._winners if w == "draw" or w == "truncated" or w is None
        ) / n
        self.logger.record("custom/win_rate_rolling", win_rate)
        self.logger.record("custom/loss_rate_rolling", loss_rate)
        self.logger.record("custom/draw_rate_rolling", draw_rate)
        self.logger.record("custom/site_hp_end_mean", float(sum(self._hp_end) / n))
        self.logger.record("custom/sim_t_mean", float(sum(self._sim_t) / n))
        self.logger.record(
            "custom/threats_truncated_mean",
            float(sum(self._truncated) / n),
        )
        short_range_total = 0
        total_fires = 0
        for k in _LAUNCHER_KINDS:
            if not self._fires[k]:
                continue
            mean = sum(self._fires[k]) / len(self._fires[k])
            self.logger.record(f"custom/fires_per_kind/{k}", float(mean))
            total_fires += sum(self._fires[k])
            if k in _SHORT_RANGE_KINDS:
                short_range_total += sum(self._fires[k])
        if total_fires > 0:
            self.logger.record(
                "custom/fires_short_range_ratio",
                short_range_total / total_fires,
            )
        for k in _THREAT_KINDS:
            if self._intercepts[k]:
                m = sum(self._intercepts[k]) / len(self._intercepts[k])
                self.logger.record(f"custom/intercepts_per_kind/{k}", float(m))
            if self._leaks[k]:
                m = sum(self._leaks[k]) / len(self._leaks[k])
                self.logger.record(f"custom/leaks_per_kind/{k}", float(m))
        total_layout = sum(self._layout_counts.values())
        if total_layout > 0:
            for slot, count in self._layout_counts.items():
                self.logger.record(
                    f"custom/layout_slot_share/{slot}",
                    count / total_layout,
                )

    # ------------------------------------------------------------------
    def _on_training_end(self) -> None:
        try:
            self._fp.close()
        except Exception:
            pass
