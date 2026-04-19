"""Engagement-mode infrastructure unit tests (M-TIER2.5 Subtask B).

Covers:
  * Damage model (`sim.world.resolve_damage`) — prox vs htk semantics.
  * `InterceptorSpec` per-type mode choices + defaults.
  * `Launcher.fire` mode validation + default resolution.
  * `Interceptor.__init__` accepts + stores engagement_mode, defaults
    to spec default, rejects illegal modes.
  * `World.spawn_interceptor` plumbs engagement_mode through to the
    constructed Interceptor instance.

Run with `python test_engagement_mode.py`. Exits non-zero on first
failing assertion.
"""
from __future__ import annotations

import numpy as np

from sim.launcher import Launcher, LAUNCHER_TEMPLATES
from sim.entities import Interceptor
from sim.types import INTERCEPTOR_SPECS, InterceptorType
from sim.world import World, resolve_damage


# --- Spec-level mode configuration -----------------------------------

def test_ciws_prox_only() -> None:
    spec = INTERCEPTOR_SPECS[InterceptorType.CIWS]
    assert spec.engagement_mode_choices == ("prox",)
    assert spec.default_engagement_mode == "prox"


def test_dual_mode_interceptors_choices_and_default() -> None:
    for kind in (
        InterceptorType.SHORT_SAM,
        InterceptorType.IRIS_T_SLS,
        InterceptorType.MED_SAM,
        InterceptorType.LONG_SAM,
    ):
        spec = INTERCEPTOR_SPECS[kind]
        assert spec.engagement_mode_choices == ("prox", "htk"), (
            f"{kind.value} choices={spec.engagement_mode_choices}"
        )
        assert spec.default_engagement_mode == "prox", (
            f"{kind.value} default={spec.default_engagement_mode}"
        )


def test_pac_3_htk_only() -> None:
    spec = INTERCEPTOR_SPECS[InterceptorType.HIT_TO_KILL]
    assert spec.engagement_mode_choices == ("htk",)
    assert spec.default_engagement_mode == "htk"


# --- resolve_damage: prox mode ---------------------------------------

def test_prox_direct_band() -> None:
    spec = INTERCEPTOR_SPECS[InterceptorType.MED_SAM]  # direct=2.0, dmg_direct=50
    damage, kind = resolve_damage(spec, "prox", 1.0)
    assert damage == 50
    assert kind == "direct"


def test_prox_prox_band_linear_falloff() -> None:
    spec = INTERCEPTOR_SPECS[InterceptorType.MED_SAM]  # prox=150.0, dmg_prox=25
    # d=60 → fall = 1 - 60/150 = 0.6 → dmg = round(25*0.6) = round(15.0) = 15
    damage, kind = resolve_damage(spec, "prox", 60.0)
    assert damage == 15, f"unexpected damage at prox-band 60m: {damage}"
    assert kind == "prox"


def test_prox_edge_of_prox_band_returns_min_1() -> None:
    spec = INTERCEPTOR_SPECS[InterceptorType.MED_SAM]
    # At d just below radius_prox, falloff → 0; max(1, 0) = 1
    damage, kind = resolve_damage(spec, "prox", 149.99)
    assert damage == 1
    assert kind == "prox"


def test_prox_miss_band_outside_prox_radius() -> None:
    spec = INTERCEPTOR_SPECS[InterceptorType.MED_SAM]  # prox=150.0
    damage, kind = resolve_damage(spec, "prox", 200.0)
    assert damage == 0
    assert kind == "miss"


def test_prox_mode_event_strings_unchanged() -> None:
    """Regression guard: existing 'direct' / 'prox' / 'miss' event
    strings must not be renamed in prox mode. M-TIER2.5 added new
    strings ('htk_direct' / 'htk_miss') for the new mode only."""
    spec = INTERCEPTOR_SPECS[InterceptorType.LONG_SAM]
    _, direct_kind = resolve_damage(spec, "prox", 0.1)
    _, prox_kind = resolve_damage(spec, "prox", spec.radius_prox * 0.5)
    _, miss_kind = resolve_damage(spec, "prox", spec.radius_prox * 2.0)
    assert direct_kind == "direct"
    assert prox_kind == "prox"
    assert miss_kind == "miss"


# --- resolve_damage: htk mode ----------------------------------------

def test_htk_direct_hit_doubles_damage() -> None:
    spec = INTERCEPTOR_SPECS[InterceptorType.HIT_TO_KILL]  # dmg_direct=200
    damage, kind = resolve_damage(spec, "htk", 10.0)  # inside radius_direct=60
    assert damage == 400, f"expected 2× damage_direct=400, got {damage}"
    assert kind == "htk_direct"


def test_htk_at_prox_band_misses_cleanly() -> None:
    spec = INTERCEPTOR_SPECS[InterceptorType.HIT_TO_KILL]  # direct=60, prox=80
    # CPA=70m is in the prox-fallback band for a prox-mode shot, but
    # htk has no fallback — 0 damage, miss.
    damage, kind = resolve_damage(spec, "htk", 70.0)
    assert damage == 0
    assert kind == "htk_miss"


def test_htk_beyond_prox_radius_misses() -> None:
    spec = INTERCEPTOR_SPECS[InterceptorType.HIT_TO_KILL]
    damage, kind = resolve_damage(spec, "htk", 200.0)
    assert damage == 0
    assert kind == "htk_miss"


def test_resolve_damage_rejects_unknown_mode() -> None:
    spec = INTERCEPTOR_SPECS[InterceptorType.MED_SAM]
    try:
        resolve_damage(spec, "nope", 1.0)
    except ValueError as exc:
        assert "nope" in str(exc)
        return
    raise AssertionError("resolve_damage did not raise on unknown mode")


# --- Launcher.fire: validation + default resolution ------------------

def _fresh_launcher(kind: InterceptorType) -> Launcher:
    tmpl = LAUNCHER_TEMPLATES[kind]
    return Launcher(kind=kind, **tmpl)


def test_launcher_fire_default_returns_spec_default() -> None:
    lch = _fresh_launcher(InterceptorType.SHORT_SAM)
    resolved = lch.fire(t_now=0.0)
    assert resolved == "prox"


def test_launcher_fire_explicit_prox_on_dual_mode() -> None:
    lch = _fresh_launcher(InterceptorType.MED_SAM)
    resolved = lch.fire(t_now=0.0, engagement_mode="prox")
    assert resolved == "prox"


def test_launcher_fire_explicit_htk_on_dual_mode() -> None:
    lch = _fresh_launcher(InterceptorType.MED_SAM)
    resolved = lch.fire(t_now=0.0, engagement_mode="htk")
    assert resolved == "htk"


def test_launcher_fire_htk_on_ciws_raises() -> None:
    lch = _fresh_launcher(InterceptorType.CIWS)
    ammo_before = lch.current_ammo
    try:
        lch.fire(t_now=0.0, engagement_mode="htk")
    except ValueError as exc:
        assert "htk" in str(exc)
        assert "ciws" in str(exc).lower()
        # Ammo must NOT have been decremented on a rejected fire.
        assert lch.current_ammo == ammo_before
        return
    raise AssertionError("Launcher.fire did not raise on illegal mode for CIWS")


def test_launcher_fire_prox_on_pac_3_raises() -> None:
    """pac_3 is htk-only by construction; a caller asking for prox is a bug."""
    lch = _fresh_launcher(InterceptorType.HIT_TO_KILL)
    try:
        lch.fire(t_now=0.0, engagement_mode="prox")
    except ValueError as exc:
        assert "prox" in str(exc)
        return
    raise AssertionError("Launcher.fire did not raise on illegal mode for pac_3")


def test_launcher_fire_pac_3_default_is_htk() -> None:
    lch = _fresh_launcher(InterceptorType.HIT_TO_KILL)
    resolved = lch.fire(t_now=0.0)
    assert resolved == "htk"


# --- Interceptor construction: engagement_mode plumbing -------------

def _make_interceptor(kind: InterceptorType, engagement_mode=None) -> Interceptor:
    launch_pos = (0.0, 0.0, 0.0)
    initial_dir = (1.0, 0.0, 1.0)
    return Interceptor(
        1, kind, launch_pos, initial_dir, target_id=0, t_now=0.0,
        engagement_mode=engagement_mode,
    )


def test_interceptor_default_mode_is_spec_default() -> None:
    inter = _make_interceptor(InterceptorType.SHORT_SAM)
    assert inter.engagement_mode == "prox"

    inter_pac3 = _make_interceptor(InterceptorType.HIT_TO_KILL)
    assert inter_pac3.engagement_mode == "htk"


def test_interceptor_explicit_htk_on_dual_mode() -> None:
    inter = _make_interceptor(InterceptorType.MED_SAM, engagement_mode="htk")
    assert inter.engagement_mode == "htk"


def test_interceptor_invalid_mode_raises_on_ciws() -> None:
    try:
        _make_interceptor(InterceptorType.CIWS, engagement_mode="htk")
    except ValueError as exc:
        assert "htk" in str(exc)
        return
    raise AssertionError("Interceptor did not raise on illegal mode")


# --- World.spawn_interceptor: plumbing check ------------------------

def test_spawn_interceptor_passes_engagement_mode() -> None:
    world = World()
    iid = world.spawn_interceptor(
        InterceptorType.MED_SAM,
        launch_pos=(0.0, 0.0, 0.0),
        initial_dir=(1.0, 0.0, 1.0),
        target_id=0,
        engagement_mode="htk",
    )
    inter = world.interceptors[iid]
    assert inter.engagement_mode == "htk"


def test_spawn_interceptor_default_uses_spec_default() -> None:
    world = World()
    iid = world.spawn_interceptor(
        InterceptorType.SHORT_SAM,
        launch_pos=(0.0, 0.0, 0.0),
        initial_dir=(1.0, 0.0, 1.0),
        target_id=0,
    )
    inter = world.interceptors[iid]
    assert inter.engagement_mode == "prox"


# --- Entry point ----------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_ciws_prox_only,
        test_dual_mode_interceptors_choices_and_default,
        test_pac_3_htk_only,
        test_prox_direct_band,
        test_prox_prox_band_linear_falloff,
        test_prox_edge_of_prox_band_returns_min_1,
        test_prox_miss_band_outside_prox_radius,
        test_prox_mode_event_strings_unchanged,
        test_htk_direct_hit_doubles_damage,
        test_htk_at_prox_band_misses_cleanly,
        test_htk_beyond_prox_radius_misses,
        test_resolve_damage_rejects_unknown_mode,
        test_launcher_fire_default_returns_spec_default,
        test_launcher_fire_explicit_prox_on_dual_mode,
        test_launcher_fire_explicit_htk_on_dual_mode,
        test_launcher_fire_htk_on_ciws_raises,
        test_launcher_fire_prox_on_pac_3_raises,
        test_launcher_fire_pac_3_default_is_htk,
        test_interceptor_default_mode_is_spec_default,
        test_interceptor_explicit_htk_on_dual_mode,
        test_interceptor_invalid_mode_raises_on_ciws,
        test_spawn_interceptor_passes_engagement_mode,
        test_spawn_interceptor_default_uses_spec_default,
    ]
    passed = 0
    for fn in tests:
        try:
            fn()
        except AssertionError as exc:
            print(f"FAIL {fn.__name__}: {exc}")
            raise
        print(f"ok  {fn.__name__}")
        passed += 1
    print(f"\nAll {passed} engagement-mode unit tests passed.")
