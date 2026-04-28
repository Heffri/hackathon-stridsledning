"""Unit test: AOE damages threats only — no friendly fire.

Verifies §3.2 constraint:
  * Blue interceptors near detonation are not damaged (they have HP=∞
    in this sim — consumed on detonation, not on AOE splash).
  * Sites near detonation are not damaged (AOE iterates `world.threats`,
    and sites aren't in that dict).

`resolve_aoe` returns a dict of threat_id → damage. Confirming it doesn't
contain non-Threat ids is sufficient — the event loop only applies
damage to entries in `aoe_dmg`.
"""
from __future__ import annotations

import numpy as np

from sim.types import INTERCEPTOR_SPECS, InterceptorType, THREAT_SPECS, ThreatType
from sim.world import World, resolve_aoe


def test_interceptor_not_in_aoe_map() -> None:
    """A live interceptor near the detonation point must not appear in
    the resolve_aoe output dict.

    `resolve_aoe` only iterates `world.threats`; interceptors are in
    `world.interceptors`. Proven by the type of the data structure +
    empirically by running with an interceptor parked next to a threat.
    """
    world = World()
    # One threat near the detonation
    tid = world.spawn_threat(
        ThreatType.DRONE,
        start_xy=(10000.0, 10000.0),
        target_xy=(0.0, 0.0),
        validate_location=False,
    )
    # One Blue interceptor parked 10m away from the threat. In the real
    # engagement the interceptor would be consumed on detonation; this
    # test just verifies it's not in the AOE damage map.
    iid = world.spawn_interceptor(
        InterceptorType.IRIS_T_SLS,
        launch_pos=(10010.0, 10000.0, 0.0),
        initial_dir=(1.0, 0.0, 0.0),
        target_id=tid,
    )
    spec = INTERCEPTOR_SPECS[InterceptorType.IRIS_T_SLS]
    detonation_pos = world.threats[tid].state.pos.copy()
    aoe = resolve_aoe(spec, detonation_pos, world.threats)
    assert iid not in aoe, (
        f"Interceptor id {iid} leaked into AOE dmg dict: {aoe}"
    )


def test_site_not_in_aoe_map() -> None:
    """Sites live in sim.sites.SOUTH_SITES (not in world.threats). AOE
    iterates threats only — a near-site detonation can't damage the
    site through the AOE path. Site damage still flows via the
    ground-impact path (threat crosses site footprint)."""
    from sim import sites as sites_module
    world = World()
    if not sites_module.SOUTH_SITES:
        return  # No sites in arena — test vacuously passes
    site = sites_module.SOUTH_SITES[0]
    # Place threat adjacent to site at the same xy
    tid = world.spawn_threat(
        ThreatType.DRONE,
        start_xy=(float(site.pos[0]), float(site.pos[1])),
        target_xy=(0.0, 0.0),
        validate_location=False,
    )
    spec = INTERCEPTOR_SPECS[InterceptorType.LONG_SAM]  # big r=150
    detonation_pos = world.threats[tid].state.pos.copy()
    aoe = resolve_aoe(spec, detonation_pos, world.threats)
    # Site has an integer id. The AOE dict only contains threat ids.
    assert site.id not in aoe or aoe == {tid: spec.fragment_damage}


if __name__ == "__main__":
    tests = [
        test_interceptor_not_in_aoe_map,
        test_site_not_in_aoe_map,
    ]
    for fn in tests:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\nAll {len(tests)} no-friendly-fire tests passed.")
