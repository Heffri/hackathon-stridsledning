"""WS placement API — place_launcher + ai_auto (M-TIER2-J Part 1, Subtask B).

Covers phase-gating, terrain validation, unknown-id rejection, and the
ai_auto reset-to-default stub. Uses `SimRunner.handle_command` directly
so the FastAPI WS layer is not exercised — same pattern as
`test_match_phase.py`'s `_fresh_runner()`.
"""
import sys

from sim import config
from sim.types import MatchPhase


def _fresh_runner():
    from server import SimRunner
    return SimRunner()


def _first_ciws(runner):
    for lch in runner.scenario.blue.launchers.launchers:
        if lch.kind.value == "ciws":
            return lch
    raise AssertionError("no ciws in default loadout")


def test_place_launcher_from_setup_valid_land_updates_pos() -> None:
    runner = _fresh_runner()
    assert runner.scenario.world.phase == MatchPhase.SETUP
    lch = _first_ciws(runner)
    # Pick a known south-land coord — the PAC-2 default slot is on
    # south_mainland and guaranteed to be on land (config.py asserts it).
    new_x, new_y = config.BLUE_LAUNCHER_POSITIONS["pac_2"][0]
    resp = runner.handle_command({
        "cmd": "place_launcher",
        "launcher_id": lch.id,
        "pos": [new_x, new_y],
    })
    # No ack on success — the snapshot path publishes the new position.
    assert resp is None, f"expected None ack on success, got {resp!r}"
    assert abs(lch.pos[0] - new_x) < 1e-6
    assert abs(lch.pos[1] - new_y) < 1e-6


def test_place_launcher_in_strait_rejected() -> None:
    runner = _fresh_runner()
    lch = _first_ciws(runner)
    before = lch.pos
    # Strait centre (STRAIT_CENTER_Y = 120_000) is not on south land.
    resp = runner.handle_command({
        "cmd": "place_launcher",
        "launcher_id": lch.id,
        "pos": [75_000, config.STRAIT_CENTER_Y],
    })
    assert resp is not None
    assert resp["type"] == "error"
    assert resp["reason"] == "illegal_placement"
    assert "south land" in resp["detail"]
    assert lch.pos == before, "position changed on rejected placement"


def test_place_launcher_unknown_id_rejected() -> None:
    runner = _fresh_runner()
    resp = runner.handle_command({
        "cmd": "place_launcher",
        "launcher_id": "no_such_id_99",
        "pos": [75_000, 5_000],
    })
    assert resp["type"] == "error"
    assert resp["reason"] == "illegal_placement"
    assert "unknown launcher_id" in resp["detail"]


def test_place_launcher_missing_fields_rejected() -> None:
    runner = _fresh_runner()
    lch = _first_ciws(runner)
    # Missing pos.
    resp = runner.handle_command({"cmd": "place_launcher", "launcher_id": lch.id})
    assert resp["type"] == "error"
    assert resp["reason"] == "illegal_placement"
    # Bad pos shape.
    resp = runner.handle_command({
        "cmd": "place_launcher",
        "launcher_id": lch.id,
        "pos": [1, 2, 3],
    })
    assert resp["type"] == "error"
    # Missing launcher_id.
    resp = runner.handle_command({
        "cmd": "place_launcher",
        "pos": [75_000, 5_000],
    })
    assert resp["type"] == "error"


def test_place_launcher_from_running_rejected() -> None:
    runner = _fresh_runner()
    runner.handle_command({"cmd": "start"})
    assert runner.scenario.world.phase == MatchPhase.RUNNING
    lch = _first_ciws(runner)
    before = lch.pos
    resp = runner.handle_command({
        "cmd": "place_launcher",
        "launcher_id": lch.id,
        "pos": [75_000, 5_000],
    })
    assert resp["type"] == "error"
    assert resp["reason"] == "illegal_placement"
    assert "must be setup" in resp["detail"]
    assert lch.pos == before


def test_place_launcher_from_paused_rejected() -> None:
    runner = _fresh_runner()
    runner.handle_command({"cmd": "start"})
    runner.handle_command({"cmd": "pause"})
    assert runner.scenario.world.phase == MatchPhase.PAUSED
    lch = _first_ciws(runner)
    before = lch.pos
    resp = runner.handle_command({
        "cmd": "place_launcher",
        "launcher_id": lch.id,
        "pos": [75_000, 5_000],
    })
    assert resp["type"] == "error"
    assert resp["reason"] == "illegal_placement"
    assert "must be setup" in resp["detail"]
    assert lch.pos == before


def test_ai_auto_from_setup_resets_to_config_defaults() -> None:
    runner = _fresh_runner()
    lch = _first_ciws(runner)
    # Move it somewhere legal but not the default.
    default_x, default_y = config.BLUE_LAUNCHER_POSITIONS["ciws"][0]
    moved_x, moved_y = config.BLUE_LAUNCHER_POSITIONS["pac_2"][0]
    runner.handle_command({
        "cmd": "place_launcher",
        "launcher_id": lch.id,
        "pos": [moved_x, moved_y],
    })
    assert abs(lch.pos[0] - moved_x) < 1e-6

    resp = runner.handle_command({"cmd": "ai_auto"})
    assert resp is None, f"expected None ack on success, got {resp!r}"
    # ciws_0 restored to its config default.
    assert abs(lch.pos[0] - default_x) < 1e-6
    assert abs(lch.pos[1] - default_y) < 1e-6
    # Every launcher now matches the config slot identified by its id.
    counters: dict[str, int] = {}
    for each in runner.scenario.blue.launchers.launchers:
        k = each.kind.value
        idx = counters.get(k, 0)
        counters[k] = idx + 1
        exp_x, exp_y = config.BLUE_LAUNCHER_POSITIONS[k][idx]
        assert abs(each.pos[0] - exp_x) < 1e-6
        assert abs(each.pos[1] - exp_y) < 1e-6


def test_ai_auto_from_running_rejected() -> None:
    runner = _fresh_runner()
    runner.handle_command({"cmd": "start"})
    # Move the ciws via direct attribute write before we check it doesn't
    # revert — ai_auto must be a no-op when RUNNING.
    lch = _first_ciws(runner)
    lch.pos = (1234.0, 5678.0)
    resp = runner.handle_command({"cmd": "ai_auto"})
    assert resp["type"] == "error"
    assert resp["reason"] == "illegal_placement"
    assert "must be setup" in resp["detail"]
    assert lch.pos == (1234.0, 5678.0), "ai_auto ran despite RUNNING phase"


if __name__ == "__main__":
    tests = [
        test_place_launcher_from_setup_valid_land_updates_pos,
        test_place_launcher_in_strait_rejected,
        test_place_launcher_unknown_id_rejected,
        test_place_launcher_missing_fields_rejected,
        test_place_launcher_from_running_rejected,
        test_place_launcher_from_paused_rejected,
        test_ai_auto_from_setup_resets_to_config_defaults,
        test_ai_auto_from_running_rejected,
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
    print(f"\nAll {passed} placement-API tests passed.")
