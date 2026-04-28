"""WS roster API — add_launcher + remove_launcher + ai_auto roster reset
(M-TIER2-J Part 2, Subtask B).

Covers phase-gating, kind validation, terrain validation, budget gating,
refund-clamp behaviour, id uniqueness, and round-trip budget neutrality.
Uses `SimRunner.handle_command` directly so the FastAPI WS layer is not
exercised — same pattern as `test_placement_api.py`.
"""
import sys

from sim import config
from sim.types import MatchPhase


def _fresh_runner():
    from server import SimRunner
    return SimRunner()


def _south_land_pos():
    # A known-good position on south land; reuse the config CIWS slot
    # which is asserted valid at module-import time.
    return config.BLUE_LAUNCHER_POSITIONS["ciws"][0]


def test_add_launcher_valid_deducts_budget_and_appends() -> None:
    runner = _fresh_runner()
    world = runner.scenario.world
    fleet = runner.scenario.blue.launchers
    assert world.phase == MatchPhase.SETUP
    before_budget = world.blue_budget
    before_count = len(fleet.launchers)
    x, y = _south_land_pos()
    resp = runner.handle_command({
        "cmd": "add_launcher",
        "kind": "pac_3",
        "pos": [x, y],
    })
    assert resp is None, f"expected None ack on success, got {resp!r}"
    assert len(fleet.launchers) == before_count + 1
    assert world.blue_budget == before_budget - 15_000_000
    new_lch = fleet.launchers[-1]
    assert new_lch.kind.value == "pac_3"
    assert new_lch.id == "pac_3_1", f"expected pac_3_1 (next after default pac_3_0), got {new_lch.id!r}"
    assert abs(new_lch.pos[0] - x) < 1e-6
    assert abs(new_lch.pos[1] - y) < 1e-6
    # New launcher snapshot entry carries base_cost_usd.
    snap = runner.scenario.snapshot()
    snap_ids = {e["id"] for e in snap["launchers"]}
    assert new_lch.id in snap_ids


def test_add_launcher_insufficient_budget_rejected() -> None:
    runner = _fresh_runner()
    world = runner.scenario.world
    # Drain the budget to under $15M so a pac_3 add can't clear the gate.
    world.blue_budget = 1_000_000
    before_count = len(runner.scenario.blue.launchers.launchers)
    x, y = _south_land_pos()
    resp = runner.handle_command({
        "cmd": "add_launcher",
        "kind": "pac_3",
        "pos": [x, y],
    })
    assert resp is not None
    assert resp["type"] == "error"
    assert resp["reason"] == "insufficient_budget"
    assert "$15000000" in resp["detail"] or "15000000" in resp["detail"]
    assert world.blue_budget == 1_000_000, "budget changed on rejected add"
    assert len(runner.scenario.blue.launchers.launchers) == before_count


def test_add_launcher_unknown_kind_rejected() -> None:
    runner = _fresh_runner()
    resp = runner.handle_command({
        "cmd": "add_launcher",
        "kind": "unobtainium_mk4",
        "pos": list(_south_land_pos()),
    })
    assert resp["type"] == "error"
    assert resp["reason"] == "illegal_placement"
    assert "unknown launcher kind" in resp["detail"]


def test_add_launcher_missing_kind_rejected() -> None:
    runner = _fresh_runner()
    resp = runner.handle_command({
        "cmd": "add_launcher",
        "pos": list(_south_land_pos()),
    })
    assert resp["type"] == "error"
    assert resp["reason"] == "illegal_placement"


def test_add_launcher_bad_pos_shape_rejected() -> None:
    runner = _fresh_runner()
    resp = runner.handle_command({
        "cmd": "add_launcher",
        "kind": "ciws",
        "pos": [1, 2, 3],
    })
    assert resp["type"] == "error"
    assert resp["reason"] == "illegal_placement"


def test_add_launcher_in_strait_rejected() -> None:
    runner = _fresh_runner()
    resp = runner.handle_command({
        "cmd": "add_launcher",
        "kind": "pac_3",
        "pos": [75_000, config.STRAIT_CENTER_Y],
    })
    assert resp["type"] == "error"
    assert resp["reason"] == "illegal_placement"
    assert "south land" in resp["detail"]


def test_add_launcher_from_running_rejected() -> None:
    runner = _fresh_runner()
    runner.handle_command({"cmd": "start"})
    assert runner.scenario.world.phase == MatchPhase.RUNNING
    before_count = len(runner.scenario.blue.launchers.launchers)
    resp = runner.handle_command({
        "cmd": "add_launcher",
        "kind": "pac_3",
        "pos": list(_south_land_pos()),
    })
    assert resp["type"] == "error"
    assert resp["reason"] == "illegal_placement"
    assert "must be setup" in resp["detail"]
    assert len(runner.scenario.blue.launchers.launchers) == before_count


def test_remove_launcher_valid_refunds_budget() -> None:
    runner = _fresh_runner()
    world = runner.scenario.world
    fleet = runner.scenario.blue.launchers
    # Add a fresh pac_3 so we can remove it without losing a default.
    x, y = _south_land_pos()
    runner.handle_command({"cmd": "add_launcher", "kind": "pac_3", "pos": [x, y]})
    before_budget = world.blue_budget
    before_count = len(fleet.launchers)
    resp = runner.handle_command({
        "cmd": "remove_launcher",
        "launcher_id": "pac_3_1",
    })
    assert resp is None, f"expected None ack on success, got {resp!r}"
    assert len(fleet.launchers) == before_count - 1
    # Refund of $15M — clamp leaves it at BLUE_BUDGET_START since we
    # spent $15M on the add; net zero from that round-trip.
    assert world.blue_budget == before_budget + 15_000_000
    # pac_3_1 is gone; pac_3_0 (default) remains.
    ids = [lch.id for lch in fleet.launchers]
    assert "pac_3_1" not in ids
    assert "pac_3_0" in ids


def test_remove_launcher_refund_clamped_at_start_budget() -> None:
    """Refund must clamp at BLUE_BUDGET_START. Set up a world where
    budget is already at start, remove a default launcher, and confirm
    the budget does not climb above start."""
    runner = _fresh_runner()
    world = runner.scenario.world
    # Fresh scenario: blue_budget == BLUE_BUDGET_START.
    assert world.blue_budget == config.BLUE_BUDGET_START
    # Removing default pac_3_0 (cost $15M) would push budget to
    # $135M if not clamped.
    resp = runner.handle_command({
        "cmd": "remove_launcher",
        "launcher_id": "pac_3_0",
    })
    assert resp is None
    assert world.blue_budget == config.BLUE_BUDGET_START, (
        f"expected clamp at {config.BLUE_BUDGET_START}, got "
        f"{world.blue_budget}"
    )


def test_remove_launcher_unknown_id_rejected() -> None:
    runner = _fresh_runner()
    resp = runner.handle_command({
        "cmd": "remove_launcher",
        "launcher_id": "ciws_999",
    })
    assert resp["type"] == "error"
    assert resp["reason"] == "illegal_placement"
    assert "unknown launcher_id" in resp["detail"]


def test_remove_launcher_missing_id_rejected() -> None:
    runner = _fresh_runner()
    resp = runner.handle_command({"cmd": "remove_launcher"})
    assert resp["type"] == "error"
    assert resp["reason"] == "illegal_placement"


def test_remove_launcher_from_running_rejected() -> None:
    runner = _fresh_runner()
    runner.handle_command({"cmd": "start"})
    before_count = len(runner.scenario.blue.launchers.launchers)
    resp = runner.handle_command({
        "cmd": "remove_launcher",
        "launcher_id": "pac_3_0",
    })
    assert resp["type"] == "error"
    assert resp["reason"] == "illegal_placement"
    assert "must be setup" in resp["detail"]
    assert len(runner.scenario.blue.launchers.launchers) == before_count


def test_add_then_remove_round_trip_net_zero_budget() -> None:
    runner = _fresh_runner()
    world = runner.scenario.world
    before = world.blue_budget
    x, y = _south_land_pos()
    runner.handle_command({"cmd": "add_launcher", "kind": "iris_t_slm", "pos": [x, y]})
    assert world.blue_budget == before - 5_000_000
    # The fresh slm is iris_t_slm_2 (default has _0 and _1).
    runner.handle_command({"cmd": "remove_launcher", "launcher_id": "iris_t_slm_2"})
    assert world.blue_budget == before, (
        f"round-trip not net-zero: {before} → {world.blue_budget}"
    )


def test_add_launcher_id_strictly_next_after_max() -> None:
    """next_idx = max existing within-kind index + 1 — never collides."""
    runner = _fresh_runner()
    x, y = _south_land_pos()
    for expected in ("pac_3_1", "pac_3_2", "pac_3_3"):
        resp = runner.handle_command({
            "cmd": "add_launcher",
            "kind": "pac_3",
            "pos": [x, y],
        })
        assert resp is None, f"add for {expected} failed: {resp!r}"
        latest = runner.scenario.blue.launchers.launchers[-1]
        assert latest.id == expected, f"expected {expected}, got {latest.id!r}"
    ids = [lch.id for lch in runner.scenario.blue.launchers.launchers if lch.kind.value == "pac_3"]
    assert len(ids) == len(set(ids)), f"duplicate pac_3 ids: {ids}"


def test_add_launcher_after_remove_re_uses_freed_slot_at_max_plus_one() -> None:
    """Remove pac_3_0, add a new pac_3 — it should land as pac_3_1 (one
    past the now-empty max, since no pac_3 remains). No stale-id
    collision."""
    runner = _fresh_runner()
    runner.handle_command({"cmd": "remove_launcher", "launcher_id": "pac_3_0"})
    x, y = _south_land_pos()
    runner.handle_command({
        "cmd": "add_launcher",
        "kind": "pac_3",
        "pos": [x, y],
    })
    ids = [lch.id for lch in runner.scenario.blue.launchers.launchers if lch.kind.value == "pac_3"]
    # No pac_3 was left, so next_idx started at 0.
    assert ids == ["pac_3_0"], f"expected [pac_3_0], got {ids}"


def test_ai_auto_restores_full_roster_even_after_adds() -> None:
    """AI Auto removes extras + re-creates missing defaults. ai_auto
    is atomic so refunds don't clamp internally; the final budget
    reflects only the operator's non-refundable sunk cost (zero in
    SETUP since the sim is frozen) — returns to BLUE_BUDGET_START."""
    runner = _fresh_runner()
    world = runner.scenario.world
    fleet = runner.scenario.blue.launchers
    x, y = _south_land_pos()
    # Add 2 extras + remove 1 default.
    runner.handle_command({"cmd": "add_launcher", "kind": "pac_3", "pos": [x, y]})
    runner.handle_command({"cmd": "add_launcher", "kind": "iris_t_slm", "pos": [x, y]})
    runner.handle_command({"cmd": "remove_launcher", "launcher_id": "ciws_0"})
    # Confirm the roster is not the default.
    default_count = sum(len(p) for p in config.BLUE_LAUNCHER_POSITIONS.values())
    # default 9 + 2 extras - 1 removed = 10
    assert len(fleet.launchers) == default_count + 1

    resp = runner.handle_command({"cmd": "ai_auto"})
    assert resp is None
    assert len(fleet.launchers) == default_count
    # Every launcher now matches the config slot identified by its id.
    counters: dict[str, int] = {}
    for each in fleet.launchers:
        k = each.kind.value
        idx = counters.get(k, 0)
        counters[k] = idx + 1
        exp_x, exp_y = config.BLUE_LAUNCHER_POSITIONS[k][idx]
        assert abs(each.pos[0] - exp_x) < 1e-6
        assert abs(each.pos[1] - exp_y) < 1e-6
    # Net-zero invariant: SETUP freezes the sim, so no interceptor fires
    # debit; ai_auto's atomic refund+re-add restores budget to the
    # starting $120 M.
    assert world.blue_budget == config.BLUE_BUDGET_START, (
        f"expected ai_auto to return budget to ${config.BLUE_BUDGET_START:,}, "
        f"got ${world.blue_budget:,}"
    )


def test_ai_auto_on_default_state_is_net_zero() -> None:
    """From a pristine default state, AI Auto is exactly net-zero
    (same roster in, same roster out, budget unchanged) — this is the
    common "revert placements" click after the operator has only
    dragged, not added/removed."""
    runner = _fresh_runner()
    world = runner.scenario.world
    before_budget = world.blue_budget
    assert before_budget == config.BLUE_BUDGET_START
    resp = runner.handle_command({"cmd": "ai_auto"})
    assert resp is None
    assert world.blue_budget == before_budget, (
        f"expected ai_auto on default state to be net-zero: "
        f"${before_budget:,} → ${world.blue_budget:,}"
    )


if __name__ == "__main__":
    tests = [
        test_add_launcher_valid_deducts_budget_and_appends,
        test_add_launcher_insufficient_budget_rejected,
        test_add_launcher_unknown_kind_rejected,
        test_add_launcher_missing_kind_rejected,
        test_add_launcher_bad_pos_shape_rejected,
        test_add_launcher_in_strait_rejected,
        test_add_launcher_from_running_rejected,
        test_remove_launcher_valid_refunds_budget,
        test_remove_launcher_refund_clamped_at_start_budget,
        test_remove_launcher_unknown_id_rejected,
        test_remove_launcher_missing_id_rejected,
        test_remove_launcher_from_running_rejected,
        test_add_then_remove_round_trip_net_zero_budget,
        test_add_launcher_id_strictly_next_after_max,
        test_add_launcher_after_remove_re_uses_freed_slot_at_max_plus_one,
        test_ai_auto_restores_full_roster_even_after_adds,
        test_ai_auto_on_default_state_is_net_zero,
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
    print(f"\nAll {passed} roster-API tests passed.")
