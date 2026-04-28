"""LAUNCHER_BASE_COSTS config + snapshot exposure (M-TIER2-J Part 2, Subtask A).

Locks the per-kind base-cost table and the additive `base_cost_usd` field
on each snapshot launcher entry. The default-roster invariant ($42.5 M)
is asserted so any later config tweak to `LAUNCHER_BASE_COSTS` that would
silently break the pre-paid-roster assumption fails loudly here.
"""
import sys

from sim import config
from sim.scenarios import build_default_scenario


EXPECTED_BASE_COSTS = {
    "ciws":         500_000,
    "rbs_70":     1_000_000,
    "iris_t_sls": 2_000_000,
    "iris_t_slm": 5_000_000,
    "pac_2":     10_000_000,
    "pac_3":     15_000_000,
}


def test_config_exposes_all_six_kinds() -> None:
    for kind, cost in EXPECTED_BASE_COSTS.items():
        assert kind in config.LAUNCHER_BASE_COSTS, (
            f"LAUNCHER_BASE_COSTS missing kind {kind!r}"
        )
        assert config.LAUNCHER_BASE_COSTS[kind] == cost, (
            f"LAUNCHER_BASE_COSTS[{kind!r}] = "
            f"{config.LAUNCHER_BASE_COSTS[kind]}, expected {cost}"
        )


def test_snapshot_launchers_carry_base_cost_usd() -> None:
    scn = build_default_scenario(auto_start=False)
    snap = scn.snapshot()
    entries = snap["launchers"]
    assert entries, "snapshot has empty launchers list"
    for entry in entries:
        assert "base_cost_usd" in entry, (
            f"snapshot launcher missing base_cost_usd: {entry}"
        )
        kind = entry["kind"]
        assert entry["base_cost_usd"] == EXPECTED_BASE_COSTS[kind], (
            f"snapshot launcher {entry['id']} kind={kind} "
            f"base_cost_usd={entry['base_cost_usd']}, "
            f"expected {EXPECTED_BASE_COSTS[kind]}"
        )


def test_default_roster_total_base_cost_is_41_5M() -> None:
    """Default roster pre-paid invariant: 1 ciws + 2 rbs_70 + 2 iris_t_sls
    + 2 iris_t_slm + 1 pac_2 + 1 pac_3 = $41.5 M (per actual config
    `BLUE_LAUNCHER_POSITIONS` counts — the W9 prompt assumed 3 ciws and
    listed $42.5 M; the real roster has 1 ciws). Sum-from-config instead
    of sum-from-snapshot so config drift is flagged even if the snapshot
    path breaks."""
    total = 0
    for kind, positions in config.BLUE_LAUNCHER_POSITIONS.items():
        total += len(positions) * config.LAUNCHER_BASE_COSTS[kind]
    assert total == 41_500_000, (
        f"default roster total base cost is ${total:,}, expected $41,500,000 "
        f"(1 ciws + 2 rbs_70 + 2 iris_t_sls + 2 iris_t_slm + 1 pac_2 + 1 pac_3)"
    )


def test_default_roster_total_base_cost_from_snapshot_matches() -> None:
    scn = build_default_scenario(auto_start=False)
    snap = scn.snapshot()
    total = sum(entry["base_cost_usd"] for entry in snap["launchers"])
    assert total == 41_500_000, (
        f"snapshot roster total base cost is ${total:,}, expected $41,500,000"
    )


def test_default_scenario_budget_untouched_by_pre_paid_roster() -> None:
    """Scenario construction must NOT charge base_cost for the config-default
    roster — operator starts with the full BLUE_BUDGET_START for
    interceptors / roster tweaks."""
    scn = build_default_scenario(auto_start=False)
    assert scn.world.blue_budget == config.BLUE_BUDGET_START


if __name__ == "__main__":
    tests = [
        test_config_exposes_all_six_kinds,
        test_snapshot_launchers_carry_base_cost_usd,
        test_default_roster_total_base_cost_is_41_5M,
        test_default_roster_total_base_cost_from_snapshot_matches,
        test_default_scenario_budget_untouched_by_pre_paid_roster,
    ]
    passed = 0
    for fn in tests:
        try:
            fn()
        except AssertionError as exc:
            print(f"FAIL {fn.__name__}: {exc}")
            sys.exit(1)
        print(f"ok  {fn.__name__}")
        passed += 1
    print(f"\nAll {passed} launcher-base-cost tests passed.")
