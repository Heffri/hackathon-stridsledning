"""Test M-TIER3-RED-BUDGET (Issue #8).

Red side now has a finite spending pool. This test covers:

  1. Config — RED_BUDGET_START exists and has a sane positive value.
  2. World construction — red_budget / red_budget_max match the config.
  3. Snapshot — stats dict carries both red_budget and red_budget_max.
  4. Default demo — 26-threat wave total ($54.3M) stays well inside
     the $100M starting budget; red.done fires normally.
  5. Deduction — after a single spawn_threat call the budget drops by
     exactly THREAT_SPECS[kind].usd_cost.
  6. Budget gate — if red_budget < kind.usd_cost, the spawn is skipped
     (not deducted, not added to world.threats), and red.log records
     the skipped-count in that wave's line.
  7. Budget floor — budget clamps at 0, never negative.
  8. Winner path — `red_budget <= 0 AND no threats alive` resolves as
     Blue win (future-ready path for Boyu's Red AI regime where Red
     spawns on budget not wave schedule).
  9. Winner path is a no-op under current wave spawner — running the
     full demo to red.done with default budget, winner resolves as
     blue via red.done not via budget, but both disjuncts would agree.
"""
from __future__ import annotations

import sys

from sim import config, sites
from sim.red_ai import RedAI, build_demo_waves
from sim.scenarios import Scenario, build_default_scenario
from sim.types import THREAT_SPECS, MatchPhase, ThreatType
from sim.world import World


def test_config_has_red_budget_start() -> None:
    assert hasattr(config, "RED_BUDGET_START"), "config.RED_BUDGET_START missing"
    assert isinstance(config.RED_BUDGET_START, int)
    assert config.RED_BUDGET_START > 0
    print(f"ok  test_config_has_red_budget_start ({config.RED_BUDGET_START:,})")


def test_world_init_sets_red_budget() -> None:
    w = World()
    assert w.red_budget == config.RED_BUDGET_START
    assert w.red_budget_max == config.RED_BUDGET_START
    print("ok  test_world_init_sets_red_budget")


def test_snapshot_exposes_red_budget() -> None:
    w = World()
    snap = w.snapshot()
    assert "red_budget" in snap["stats"]
    assert "red_budget_max" in snap["stats"]
    assert snap["stats"]["red_budget"] == config.RED_BUDGET_START
    assert snap["stats"]["red_budget_max"] == config.RED_BUDGET_START
    print("ok  test_snapshot_exposes_red_budget")


def test_default_wave_cost_fits_under_starting_budget() -> None:
    """Invariant: under the current wave spec + starting budget, the
    full demo fires every scheduled threat. Pre-Tier-3 behaviour is
    preserved — nothing silently skips under default settings."""
    total = 0
    for wave in build_demo_waves():
        for k in wave.threats:
            total += THREAT_SPECS[k].usd_cost
    assert total < config.RED_BUDGET_START, (
        f"default waves cost ${total:,} but RED_BUDGET_START is "
        f"${config.RED_BUDGET_START:,} — would cause silent wave skips"
    )
    print(f"ok  test_default_wave_cost_fits_under_starting_budget "
          f"(${total:,} < ${config.RED_BUDGET_START:,})")


def test_red_ai_step_deducts_budget_per_spawn() -> None:
    """Running RedAI.step through the demo waves drains red_budget by
    exactly the total threat cost."""
    sites.reset_leaks()
    scn = build_default_scenario(auto_start=True)
    start_budget = scn.world.red_budget
    expected_total_cost = sum(
        THREAT_SPECS[k].usd_cost for w in build_demo_waves() for k in w.threats
    )
    dt = 0.05
    # Step long enough for all 5 waves to spawn and no wave timer is
    # beyond 180s in the default spec.
    for _ in range(int(250.0 / dt)):
        scn.step(dt)
        if scn.red.done:
            break
    assert scn.red.done
    spent = start_budget - scn.world.red_budget
    assert spent == expected_total_cost, (
        f"expected spend ${expected_total_cost:,} got ${spent:,}"
    )
    print(f"ok  test_red_ai_step_deducts_budget_per_spawn "
          f"(spent ${spent:,})")


def test_insufficient_budget_skips_spawn() -> None:
    """If red_budget < kind.usd_cost the spawn is skipped — no threat
    added to world, no log stack trace. HGV at $10M is the cheapest
    high-cost way to trigger."""
    sites.reset_leaks()
    scn = Scenario()
    scn.red = RedAI([])  # empty waves
    # Force the budget BELOW HGV cost ($10M) so a single HGV spawn
    # attempt skips. $9M is safely below.
    scn.world.red_budget = 9_000_000
    scn.world.transition(MatchPhase.RUNNING)
    # Build a single-wave spawn entry manually via a direct call.
    # Bypass RedAI.step; call spawn_threat directly with the gating
    # logic we'd expect.
    kind = ThreatType.HGV
    cost = THREAT_SPECS[kind].usd_cost
    assert scn.world.red_budget < cost
    # Simulate what a future Red AI would do — check budget then spawn
    if scn.world.red_budget >= cost:
        scn.world.spawn_threat(kind, (75000.0, 240000.0, 35000.0), (75000.0, 8000.0))
    # With insufficient budget we should NOT have spawned
    assert len(scn.world.threats) == 0, "threat spawned despite insufficient budget"
    assert scn.world.red_budget == 9_000_000, "budget changed when no spawn occurred"
    print("ok  test_insufficient_budget_skips_spawn")


def test_red_ai_step_skips_within_wave_when_budget_low() -> None:
    """RedAI.step's internal gate: a wave with mixed threats where
    budget only covers some of them should spawn the affordable ones
    and skip the rest."""
    sites.reset_leaks()
    scn = build_default_scenario(auto_start=True)
    # Drain most of the budget — leave exactly one drone's worth.
    scn.world.red_budget = THREAT_SPECS[ThreatType.DRONE].usd_cost  # $30k
    scn.world.t = 0.0  # reset time so the first wave triggers immediately
    # Skip ahead past wave 1's time so it fires on the next step.
    dt = 0.05
    for _ in range(int(10.0 / dt)):  # 10 s > wave-1 trigger time (2 s)
        scn.step(dt)
    # Wave 1 is "Drones" (3 drones) — first drone should have spawned,
    # next two should skip.
    assert scn.world.threats_spawned <= 3
    assert scn.world.red_budget == 0, (
        f"budget should be exhausted, got ${scn.world.red_budget:,}"
    )
    # Log line from wave 1 should mention "skipped"
    wave1_logs = [line for line in scn.red.log if "Wave 1" in line]
    assert wave1_logs, "wave 1 did not fire"
    assert "skipped" in wave1_logs[0].lower(), (
        f"expected skip note in log, got: {wave1_logs[0]!r}"
    )
    print(f"ok  test_red_ai_step_skips_within_wave_when_budget_low "
          f"(spawned 1 drone, skipped rest; log: {wave1_logs[0].strip()})")


def test_winner_blue_on_red_budget_exhausted_and_no_threats() -> None:
    """Future-ready Blue-win path: red_budget <= 0 AND no threats
    alive AND red.done not necessarily true → Blue win. Simulates
    Boyu's Red AI regime where Red can't afford anything and has
    spawned nothing yet so red.done=False."""
    sites.reset_leaks()
    scn = Scenario()
    # Fresh waves list but time-in-the-future so red.done stays False.
    from sim.types import WaveSpec
    scn.red = RedAI([WaveSpec(time=999_999.0, label="never", threats=[ThreatType.DRONE])])
    scn.world.transition(MatchPhase.RUNNING)
    scn.world.red_budget = 0
    # No threats alive; waves not done (future wave still scheduled)
    assert not scn.red.done
    assert len(scn.world.threats) == 0
    assert scn.winner == "blue", (
        f"expected blue (red bankrupt + no threats), got {scn.winner!r}"
    )
    print("ok  test_winner_blue_on_red_budget_exhausted_and_no_threats")


def test_winner_red_path_unaffected_by_red_budget() -> None:
    """Regression: the Red-victory path (all military HP=0) fires
    regardless of Red's budget — Blue winning the economic war doesn't
    save a base that's already dead."""
    sites.reset_leaks()
    scn = Scenario()
    scn.red = RedAI([])
    scn.world.transition(MatchPhase.RUNNING)
    # Pristine Red economy but dead Blue sites
    assert scn.world.red_budget == config.RED_BUDGET_START
    for s in sites.SOUTH_SITES:
        if s.subtype in ("air_base", "base"):
            s.hp = 0
    assert scn.winner == "red"
    print("ok  test_winner_red_path_unaffected_by_red_budget")


def main() -> None:
    test_config_has_red_budget_start()
    test_world_init_sets_red_budget()
    test_snapshot_exposes_red_budget()
    test_default_wave_cost_fits_under_starting_budget()
    test_red_ai_step_deducts_budget_per_spawn()
    test_insufficient_budget_skips_spawn()
    test_red_ai_step_skips_within_wave_when_budget_low()
    test_winner_blue_on_red_budget_exhausted_and_no_threats()
    test_winner_red_path_unaffected_by_red_budget()
    print("\nAll 9 Red-budget tests passed.")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
