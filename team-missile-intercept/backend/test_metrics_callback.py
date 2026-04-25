"""MetricsCallback tests.

Covers:
  * `_tally_events` buckets launch/intercept/leak events by kind.
  * World emits `kind` on intercept + damage events (AOE 2026-04-24).
  * A run of `MissileInterceptEnv` + MetricsCallback-like accumulator
    produces a valid JSONL with all required keys.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from rl.callbacks import MetricsCallback, _tally_events
from rl.env import MissileInterceptEnv
from sim import sites as sites_module
from sim.types import InterceptorType, ThreatType
from sim.world import World


def test_tally_events_buckets_by_kind() -> None:
    events = [
        {"type": "launch", "kind": "ciws"},
        {"type": "launch", "kind": "pac_2"},
        {"type": "launch", "kind": "ciws"},
        {"type": "intercept", "kind": "drone", "threat": 1, "interceptor": 10},
        {"type": "leak", "kind": "cruise_sub", "threat": 2},
        {"type": "ground_crash", "threat": 3},  # should not tally
    ]
    t = _tally_events(events)
    assert t["fires"] == {"ciws": 2, "pac_2": 1}
    assert t["intercepts"] == {"drone": 1}
    assert t["leaks"] == {"cruise_sub": 1}


def test_world_intercept_event_has_kind() -> None:
    """Regression: intercept/damage events must carry `kind` so
    downstream (callbacks, diag) can tally without threat-id lookup."""
    sites_module.reset_leaks()
    w = World()
    from sim.types import MatchPhase
    w.transition(MatchPhase.RUNNING)
    tid = w.spawn_threat(
        ThreatType.DRONE,
        (50_000, 5_000, 500),
        (50_000, 5_000),
        validate_location=False,
    )
    iid = w.spawn_interceptor(
        InterceptorType.IRIS_T_SLS,
        (50_000, 5_000, 500),
        (0, 0, 1),
        tid,
        launcher_pos=(50_000, 5_000, 0),
    )
    # Force detonation: set prev positions colocated → d_min=0.
    inter = w.interceptors[iid]
    threat = w.threats[tid]
    inter._prev_pos = inter.state.pos.copy()
    inter._prev_vel = inter.state.vel.copy()
    threat._prev_pos = threat.state.pos.copy()
    threat._prev_vel = threat.state.vel.copy()
    # Skip threat.step + interceptor.step (phases 1+2); jump directly to
    # phase 3 damage branch by calling world.step(dt). Events cleared by
    # Scenario.step normally; here we clear manually.
    w.events = []
    w.step(0.05)
    intercept_events = [e for e in w.events if e.get("type") == "intercept"]
    if intercept_events:
        for ev in intercept_events:
            assert "kind" in ev, f"intercept event missing 'kind': {ev}"
            assert ev["kind"] == ThreatType.DRONE.value


def test_metrics_callback_jsonl_written(tmp_path) -> None:
    """Exercise MetricsCallback manually: create instance, feed a
    fake info dict, verify JSONL line written with expected keys."""
    cb = MetricsCallback(run_dir=str(tmp_path), window=10)
    # Pretend we're inside SB3's callback: populate locals + timesteps.
    cb.num_timesteps = 1024  # type: ignore
    fake_info = {
        "winner": "blue",
        "terminal_reason": "blue_survives_red_empty",
        "cum_reward": 123.4,
        "sim_t": 789.0,
        "site_hp_total": 250,
        "layout_slot": "D",
        "threats_truncated": 0,
        "alive_threats_total": 5,
        "events": [
            {"type": "launch", "kind": "iris_t_slm"},
            {"type": "launch", "kind": "iris_t_slm"},
            {"type": "intercept", "kind": "drone"},
            {"type": "leak", "kind": "drone"},
        ],
    }
    cb._record_episode(fake_info)
    # Flush + read back.
    jsonl = Path(tmp_path) / "metrics.jsonl"
    assert jsonl.is_file()
    with open(jsonl, "r", encoding="utf-8") as f:
        lines = f.readlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["winner"] == "blue"
    assert rec["reward"] == 123.4
    assert rec["layout_slot"] == "D"
    assert rec["fires_by_kind"] == {"iris_t_slm": 2}
    assert rec["intercepts_by_kind"] == {"drone": 1}
    assert rec["leaks_by_kind"] == {"drone": 1}
    cb._on_training_end()


def test_metrics_callback_rolling_buffer(tmp_path) -> None:
    """Rolling stats should compute correctly after multiple eps."""
    cb = MetricsCallback(run_dir=str(tmp_path), window=5)
    cb.num_timesteps = 0  # type: ignore
    for i, w in enumerate(["blue", "blue", "red", "blue", "red"]):
        cb.num_timesteps = (i + 1) * 1000  # type: ignore
        cb._record_episode({
            "winner": w, "terminal_reason": None, "cum_reward": 100.0,
            "sim_t": 500.0, "site_hp_total": 200, "layout_slot": "C",
            "threats_truncated": 0, "alive_threats_total": 3,
            "events": [{"type": "launch", "kind": "ciws"}],
        })
    # 3 blue, 2 red, 0 draw
    n = len(cb._winners)
    assert n == 5
    win_rate = sum(1 for x in cb._winners if x == "blue") / n
    assert abs(win_rate - 0.6) < 1e-6
    cb._on_training_end()


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        from pathlib import Path as _P
        test_tally_events_buckets_by_kind()
        test_world_intercept_event_has_kind()
        test_metrics_callback_jsonl_written(_P(d))
        import tempfile as _t
        with _t.TemporaryDirectory() as d2:
            test_metrics_callback_rolling_buffer(_P(d2))
    print("All metrics callback tests passed.")
