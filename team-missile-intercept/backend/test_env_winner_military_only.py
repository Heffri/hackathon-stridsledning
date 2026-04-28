"""Bug 1 regression: rl/env.py::_winner mirrors scenarios.Scenario.winner
military-only rule.

Pre-fix the env returned "red" on the FIRST site at hp<=0, which fired
on cities (wrong — cities don't count toward the Red-victory condition)
and cut ScriptedRed matches short after ONE military site died, blocking
the "Blue holds 2/3 sites" outcomes from ever scoring as Blue wins in
the RL reward signal.

After fix: Red only wins when every military site (subtype in
{'base','air_base'}) is at hp<=0.
"""
from __future__ import annotations

import sys

from sim import sites as sites_module
from rl.env import MissileInterceptEnv


def _reset_env() -> MissileInterceptEnv:
    sites_module.reset_leaks()
    env = MissileInterceptEnv(seed=1)
    env.reset(seed=1)
    return env


def test_city_dead_military_alive_returns_none() -> None:
    """City at hp=0, all military sites alive → match continues."""
    env = _reset_env()
    # Zero out every non-military site (cities + capital, if any).
    touched = 0
    for s in sites_module.SOUTH_SITES:
        if s.subtype not in ("base", "air_base"):
            s.hp = 0
            touched += 1
    # Ensure every military site is healthy.
    for s in sites_module.SOUTH_SITES:
        if s.subtype in ("base", "air_base"):
            assert s.hp > 0, (
                f"setup error: military site {s.name} started with hp<=0"
            )
    w = env._winner()
    assert w is None, (
        f"city-dead but military-alive must not be a Red win; got {w!r} "
        f"(touched {touched} non-military site(s))"
    )
    print("ok  test_city_dead_military_alive_returns_none")


def test_all_military_dead_returns_red() -> None:
    """Every military site at hp=0 → Red wins."""
    env = _reset_env()
    count = 0
    for s in sites_module.SOUTH_SITES:
        if s.subtype in ("base", "air_base"):
            s.hp = 0
            count += 1
    assert count >= 1, "sanity: expected at least one military site"
    w = env._winner()
    assert w == "red", f"expected 'red' on all-military-dead, got {w!r}"
    print("ok  test_all_military_dead_returns_red")


def test_partial_military_dead_returns_none() -> None:
    """2 of 3 military sites at hp=0 → match continues (Issue #9 rule)."""
    env = _reset_env()
    military = [s for s in sites_module.SOUTH_SITES
                if s.subtype in ("base", "air_base")]
    assert len(military) >= 2, (
        f"test needs at least 2 military sites; got {len(military)}"
    )
    # Kill all but one
    for s in military[:-1]:
        s.hp = 0
    assert military[-1].hp > 0
    w = env._winner()
    assert w is None, (
        f"partial military loss (all but 1) must not end the match; "
        f"got {w!r} with {len(military)-1}/{len(military)} dead"
    )
    print("ok  test_partial_military_dead_returns_none")


def test_red_done_no_threats_returns_blue() -> None:
    """All military alive + Red done + no threats → Blue wins."""
    env = _reset_env()
    # Force red.done via the underlying waves list (rule-Red).
    # Red was created as RedAI(build_demo_waves()) in reset().
    env.red._next_wave = len(env.red.waves)  # done -> True
    assert env.red.done, "setup: expected red.done=True after fast-forward"
    # No threats in world (fresh reset)
    assert all(not t.state.alive for t in env.world.threats.values())
    # All military alive by default
    for s in sites_module.SOUTH_SITES:
        if s.subtype in ("base", "air_base"):
            assert s.hp > 0
    w = env._winner()
    assert w == "blue", f"expected 'blue', got {w!r}"
    print("ok  test_red_done_no_threats_returns_blue")


def main() -> None:
    test_city_dead_military_alive_returns_none()
    test_all_military_dead_returns_red()
    test_partial_military_dead_returns_none()
    test_red_done_no_threats_returns_blue()
    print("\nAll 4 env-winner-military-only tests passed.")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
