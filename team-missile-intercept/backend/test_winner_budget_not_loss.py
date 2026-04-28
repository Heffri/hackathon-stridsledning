"""Test Scenario.winner no longer treats budget=0 as instant Red win.

Issue #21 (M-TIER2.8, 2026-04-20): the old rule `if blue_budget <= 0:
return 'red'` in Scenario.winner was too harsh — a match where Blue
spent its last dollar on a mid-air interceptor that then killed the
last drone, with the base essentially untouched, was being resolved
as a Red victory.

After fix: budget depletion is not a win condition. The match only
ends via:
  * Red: all military sites (subtype 'air_base' or 'base') at hp <= 0
  * Blue: all Red waves spawned AND no Red threats alive
  * Draw: max_sim_time reached

This test builds a default scenario, zeroes out blue_budget, and
verifies the winner property behaves correctly in three regimes:
  (1) budget=0, sites full HP, threats alive → None (match continues)
  (2) budget=0, sites full HP, red.done + no threats → 'blue'
  (3) budget=0, any military site hp=0 → 'red' (unrelated path)
"""
from __future__ import annotations

import sys

from sim import sites
from sim.red_ai import RedAI
from sim.scenarios import Scenario
from sim.types import MatchPhase, ThreatType


def _fresh_scenario() -> Scenario:
    sites.reset_leaks()
    scn = Scenario()
    scn.red = RedAI([])  # empty wave list so red.done is True immediately
    scn.world.transition(MatchPhase.RUNNING)
    return scn


def test_budget_zero_with_no_threats_and_red_done_is_blue_win() -> None:
    """Chen's 2026-04-20 scenario: budget spent, last threat resolved,
    base intact → Blue wins."""
    scn = _fresh_scenario()
    scn.world.blue_budget = 0
    # red.done is True (empty waves) and no threats alive
    assert scn.red.done
    assert len(scn.world.threats) == 0
    w = scn.winner
    assert w == "blue", f"expected 'blue', got {w!r}"
    print("ok  test_budget_zero_with_no_threats_and_red_done_is_blue_win")


def test_budget_zero_with_live_threat_is_none() -> None:
    """Budget drained but a threat is still alive — match continues
    regardless of budget."""
    scn = _fresh_scenario()
    scn.world.blue_budget = 0
    # Spawn a single drone to keep the match alive.
    # W14 (Issue #30): location is test setup, not a realistic Red
    # spawn — opt out of the spatial contract.
    scn.world.spawn_threat(
        ThreatType.DRONE, (75_000.0, 100_000.0, 2_000.0),
        (75_000.0, 8_000.0), validate_location=False,
    )
    w = scn.winner
    assert w is None, f"expected None (match in progress), got {w!r}"
    print("ok  test_budget_zero_with_live_threat_is_none")


def test_budget_zero_military_sites_dead_is_red_win() -> None:
    """Budget drained AND every military site dead → Red wins via the
    HP path (not via the old budget path)."""
    scn = _fresh_scenario()
    scn.world.blue_budget = 0
    for s in sites.SOUTH_SITES:
        if s.subtype in ("air_base", "base"):
            s.hp = 0
    w = scn.winner
    assert w == "red", f"expected 'red', got {w!r}"
    print("ok  test_budget_zero_military_sites_dead_is_red_win")


def test_positive_budget_behaviour_unchanged() -> None:
    """Sanity regression: with a positive budget and no threats, empty
    waves still resolves as Blue win (no unintended side effects)."""
    scn = _fresh_scenario()
    assert scn.world.blue_budget > 0
    w = scn.winner
    assert w == "blue", f"expected 'blue', got {w!r}"
    print("ok  test_positive_budget_behaviour_unchanged")


def test_old_behavior_would_have_failed() -> None:
    """Document the pre-fix behaviour: under the old rule,
    `budget=0` alone would have returned 'red'. Now it does not.
    This test asserts the NEW behaviour and implicitly records what
    changed."""
    scn = _fresh_scenario()
    # Spawn a threat so we're clearly mid-match.
    # W14 (Issue #30): location is test setup, not a realistic Red
    # spawn — opt out of the spatial contract.
    scn.world.spawn_threat(
        ThreatType.DRONE, (75_000.0, 100_000.0, 2_000.0),
        (75_000.0, 8_000.0), validate_location=False,
    )
    scn.world.blue_budget = 0
    # Old rule: w == 'red'. New rule: w == None (match continues).
    w = scn.winner
    assert w != "red", (
        f"Issue #21 regression: budget=0 with a live threat and intact "
        f"base returned {w!r}, but the M-TIER2.8 fix requires != 'red'."
    )
    print("ok  test_old_behavior_would_have_failed")


def main() -> None:
    test_budget_zero_with_no_threats_and_red_done_is_blue_win()
    test_budget_zero_with_live_threat_is_none()
    test_budget_zero_military_sites_dead_is_red_win()
    test_positive_budget_behaviour_unchanged()
    test_old_behavior_would_have_failed()
    print("\nAll 5 winner-budget tests passed.")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
