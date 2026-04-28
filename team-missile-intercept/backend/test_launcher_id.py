"""Launcher.id + snapshot exposure (M-TIER2-J Part 1, Subtask A).

Stable string IDs of the form `f"{kind}_{within_kind_idx}"` are the
address the place_launcher WebSocket protocol uses to identify which
launcher the operator is dragging. This test locks the ID shape and
verifies the snapshot carries it.
"""
import re
import sys

from sim import config
from sim.launcher import LauncherFleet
from sim.scenarios import build_default_scenario


_ID_RE = re.compile(r"^[a-z_0-9]+_\d+$")


def test_default_scenario_launcher_ids_unique_and_well_formed() -> None:
    scn = build_default_scenario(auto_start=False)
    launchers = scn.blue.launchers.launchers
    assert launchers, "default scenario has no launchers — config drift"
    ids = []
    for lch in launchers:
        assert lch.id, f"launcher {lch.kind} missing id"
        assert _ID_RE.match(lch.id), f"launcher id {lch.id!r} does not match {{kind}}_{{idx}}"
        assert lch.id.startswith(f"{lch.kind.value}_"), (
            f"launcher.id {lch.id!r} does not match its kind {lch.kind.value!r}"
        )
        ids.append(lch.id)
    assert len(ids) == len(set(ids)), f"duplicate launcher ids: {ids}"


def test_snapshot_launchers_carry_id_field() -> None:
    scn = build_default_scenario(auto_start=False)
    snap = scn.snapshot()
    entries = snap["launchers"]
    assert entries, "snapshot has empty launchers list"
    for entry in entries:
        assert "id" in entry, f"snapshot launcher missing id: {entry}"
        assert entry["id"], f"empty id in snapshot launcher: {entry}"
        assert _ID_RE.match(entry["id"]), (
            f"snapshot launcher id {entry['id']!r} does not match {{kind}}_{{idx}}"
        )
        assert entry["id"].startswith(f"{entry['kind']}_"), (
            f"snapshot launcher id {entry['id']!r} does not match kind {entry['kind']!r}"
        )


def test_within_kind_index_matches_config_order() -> None:
    """The `_{idx}` suffix must be the zero-based position within the
    kind's list in `BLUE_LAUNCHER_POSITIONS`. Future drag-drop depends
    on that ordering so a "place_launcher ciws_0" always addresses the
    first CIWS in the config dict regardless of fleet iteration order.
    """
    fleet = LauncherFleet()
    per_kind_pos = {}
    for lch in fleet.launchers:
        per_kind_pos.setdefault(lch.kind.value, []).append((lch.id, lch.pos))
    for kind, entries in per_kind_pos.items():
        expected = config.BLUE_LAUNCHER_POSITIONS[kind]
        for idx, (lid, pos) in enumerate(entries):
            assert lid == f"{kind}_{idx}", (
                f"{kind}: launcher id {lid!r} does not match expected "
                f"{kind}_{idx!r}"
            )
            assert abs(pos[0] - expected[idx][0]) < 1e-6
            assert abs(pos[1] - expected[idx][1]) < 1e-6


def test_legacy_loadout_path_also_assigns_ids() -> None:
    """The count-based loadout path (used by unit tests that skip the
    positions dict) must also produce well-formed IDs so any future test
    that inspects `lch.id` doesn't hit an empty string.
    """
    from sim.types import InterceptorType
    fleet = LauncherFleet(loadout={InterceptorType.CIWS: 2, InterceptorType.HIT_TO_KILL: 1})
    ids = [lch.id for lch in fleet.launchers]
    assert ids == ["ciws_0", "ciws_1", "pac_3_0"], f"unexpected ids: {ids}"


if __name__ == "__main__":
    tests = [
        test_default_scenario_launcher_ids_unique_and_well_formed,
        test_snapshot_launchers_carry_id_field,
        test_within_kind_index_matches_config_order,
        test_legacy_loadout_path_also_assigns_ids,
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
    print(f"\nAll {passed} launcher-id tests passed.")
