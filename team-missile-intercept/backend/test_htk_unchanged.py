"""Unit test: PAC-3 stays pure hit-to-kill after the AOE rewrite.

§3.6 table: PAC-3 fragment_radius=0, fragment_damage=120. The `d <= r`
gate in resolve_aoe means a threat at d=0 still qualifies, so the
primary target takes full damage while no splash damage is applied to
anything else. This preserves "PAC-3 one-shots ballistic / HGV" game
behaviour.
"""
from __future__ import annotations

import numpy as np

from sim.types import INTERCEPTOR_SPECS, InterceptorType, THREAT_SPECS, ThreatType
from sim.world import World, resolve_aoe


def test_pac3_primary_only_at_zero_distance() -> None:
    """Detonate PAC-3 at exactly the primary's position. Primary takes
    damage; any secondary threat even 1 metre away takes none."""
    world = World()
    t_primary = world.spawn_threat(
        ThreatType.BALLISTIC,
        start_xy=(10000.0, 10000.0),
        target_xy=(0.0, 0.0),
        validate_location=False,
    )
    t_near = world.spawn_threat(
        ThreatType.BALLISTIC,
        start_xy=(10001.0, 10000.0),  # 1 metre away
        target_xy=(0.0, 0.0),
        validate_location=False,
    )
    spec = INTERCEPTOR_SPECS[InterceptorType.HIT_TO_KILL]
    detonation_pos = world.threats[t_primary].state.pos.copy()
    aoe = resolve_aoe(spec, detonation_pos, world.threats)
    # Primary at d=0 is inside r=0 via the `<=` gate.
    assert t_primary in aoe, f"primary missing from PAC-3 AOE: {aoe}"
    assert aoe[t_primary] == 120
    # Near threat at d=1 is strictly > r=0 → excluded.
    assert t_near not in aoe, (
        f"PAC-3 should be pure HTK — t_near at d=1 leaked into AOE: {aoe}"
    )


def test_pac3_one_shots_ballistic() -> None:
    """Apply PAC-3 primary damage to ballistic — HP 80 vs dmg 120
    → one-shot kill. Mirrors pre-AOE behaviour."""
    world = World()
    ballistic_hp = THREAT_SPECS[ThreatType.BALLISTIC].hp
    assert ballistic_hp < 120, (
        f"PAC-3 fragment_damage (120) must exceed ballistic hp "
        f"({ballistic_hp}) to one-shot it"
    )
    tid = world.spawn_threat(
        ThreatType.BALLISTIC,
        start_xy=(10000.0, 10000.0),
        target_xy=(0.0, 0.0),
        validate_location=False,
    )
    spec = INTERCEPTOR_SPECS[InterceptorType.HIT_TO_KILL]
    detonation_pos = world.threats[tid].state.pos.copy()
    aoe = resolve_aoe(spec, detonation_pos, world.threats)
    dmg = aoe[tid]
    world.threats[tid].state.hp = max(0, world.threats[tid].state.hp - dmg)
    assert world.threats[tid].state.hp == 0, (
        f"PAC-3 should one-shot ballistic, got hp="
        f"{world.threats[tid].state.hp}"
    )


def test_pac3_one_shots_hgv() -> None:
    """PAC-3 also one-shots the HGV (HP 60) — its primary raison d'etre
    in the arcade. Preserving this game feel is core to §3.6."""
    world = World()
    hgv_hp = THREAT_SPECS[ThreatType.HGV].hp
    assert hgv_hp < 120, f"PAC-3 should beat HGV HP {hgv_hp}"
    tid = world.spawn_threat(
        ThreatType.HGV,
        start_xy=(10000.0, 10000.0),
        target_xy=(0.0, 0.0),
        validate_location=False,
    )
    spec = INTERCEPTOR_SPECS[InterceptorType.HIT_TO_KILL]
    detonation_pos = world.threats[tid].state.pos.copy()
    aoe = resolve_aoe(spec, detonation_pos, world.threats)
    dmg = aoe[tid]
    world.threats[tid].state.hp = max(0, world.threats[tid].state.hp - dmg)
    assert world.threats[tid].state.hp == 0


def test_fragment_radius_zero_excludes_tiny_offset() -> None:
    """Floating-point edge case: detonation computed from world coords
    may sit exactly at the threat position (we copy it directly). But
    the `<=` gate is strict about d > r being excluded. A threat 0.01 m
    away must not be hit by PAC-3."""
    world = World()
    t1 = world.spawn_threat(
        ThreatType.DRONE,
        start_xy=(10000.0, 10000.0),
        target_xy=(0.0, 0.0),
        validate_location=False,
    )
    t2 = world.spawn_threat(
        ThreatType.DRONE,
        start_xy=(10000.01, 10000.0),  # 1 cm offset
        target_xy=(0.0, 0.0),
        validate_location=False,
    )
    spec = INTERCEPTOR_SPECS[InterceptorType.HIT_TO_KILL]
    detonation_pos = world.threats[t1].state.pos.copy()
    aoe = resolve_aoe(spec, detonation_pos, world.threats)
    assert t1 in aoe
    assert t2 not in aoe


if __name__ == "__main__":
    tests = [
        test_pac3_primary_only_at_zero_distance,
        test_pac3_one_shots_ballistic,
        test_pac3_one_shots_hgv,
        test_fragment_radius_zero_excludes_tiny_offset,
    ]
    for fn in tests:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\nAll {len(tests)} HTK-unchanged tests passed.")
