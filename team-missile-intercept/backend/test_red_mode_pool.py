"""Bug 2 regression: MissileInterceptEnv.red_mode_pool samples both Red
drivers across episodes.

Pre-fix the env instantiated a single Red class (chosen by --red-mode).
That starved the policy of rule-Red exposure when --red-mode scripted,
producing OOD failure on layouts C/D × rule-Red at eval time (zero
fires).

After fix: `red_mode_pool=["scripted", "rule"]` samples uniformly per
reset, and the env exposes the chosen class via `.red` (ScriptedRedAI
or RedAI).
"""
from __future__ import annotations

import sys
from collections import Counter

from rl.env import MissileInterceptEnv
from sim.red_ai import RedAI, ScriptedRedAI


def _kind(red) -> str:
    if isinstance(red, ScriptedRedAI):
        return "scripted"
    if isinstance(red, RedAI):
        return "rule"
    return type(red).__name__


def test_pool_samples_both_modes() -> None:
    """20 resets with pool=['scripted','rule'] should yield both classes."""
    env = MissileInterceptEnv(
        seed=42,
        red_mode_pool=["scripted", "rule"],
    )
    seen: Counter = Counter()
    for i in range(20):
        env.reset(seed=42 + i)  # fresh RNG per reset via seed
        seen[_kind(env.red)] += 1
    assert seen["scripted"] > 0, (
        f"scripted never sampled in 20 resets (got counts {dict(seen)})"
    )
    assert seen["rule"] > 0, (
        f"rule never sampled in 20 resets (got counts {dict(seen)})"
    )
    # Total must account for every reset (no third class)
    assert sum(seen.values()) == 20, f"unexpected classes: {dict(seen)}"
    print(f"ok  test_pool_samples_both_modes  counts={dict(seen)}")


def test_scripted_only_pool_always_scripted() -> None:
    """pool=['scripted'] must always produce ScriptedRedAI."""
    env = MissileInterceptEnv(seed=1, red_mode_pool=["scripted"])
    for i in range(5):
        env.reset(seed=100 + i)
        assert isinstance(env.red, ScriptedRedAI), (
            f"reset {i}: expected ScriptedRedAI, got {type(env.red).__name__}"
        )
    print("ok  test_scripted_only_pool_always_scripted")


def test_rule_only_pool_always_rule() -> None:
    """pool=['rule'] must always produce RedAI."""
    env = MissileInterceptEnv(seed=1, red_mode_pool=["rule"])
    for i in range(5):
        env.reset(seed=200 + i)
        assert isinstance(env.red, RedAI), (
            f"reset {i}: expected RedAI, got {type(env.red).__name__}"
        )
        assert not isinstance(env.red, ScriptedRedAI), (
            f"reset {i}: rule pool unexpectedly gave ScriptedRedAI "
            f"(ScriptedRedAI subclasses RedAI?) — test guards against that"
        )
    print("ok  test_rule_only_pool_always_rule")


def test_no_pool_falls_back_to_red_mode() -> None:
    """Without a pool, the single `red_mode` arg governs (back-compat)."""
    env_default = MissileInterceptEnv(seed=1, red_mode="default")
    env_default.reset(seed=7)
    assert isinstance(env_default.red, RedAI), (
        f"red_mode='default' must give RedAI; got {type(env_default.red)}"
    )
    env_script = MissileInterceptEnv(seed=1, red_mode="scripted")
    env_script.reset(seed=7)
    assert isinstance(env_script.red, ScriptedRedAI), (
        f"red_mode='scripted' must give ScriptedRedAI; got {type(env_script.red)}"
    )
    print("ok  test_no_pool_falls_back_to_red_mode")


def main() -> None:
    test_pool_samples_both_modes()
    test_scripted_only_pool_always_scripted()
    test_rule_only_pool_always_rule()
    test_no_pool_falls_back_to_red_mode()
    print("\nAll 4 red-mode-pool tests passed.")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
