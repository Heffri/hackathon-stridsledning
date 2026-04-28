"""Engagement-mode infrastructure unit tests (M-TIER2.5 Subtask B,
updated for arcade AOE in blue_aoe_long Phase 2).

Covers:
  * `InterceptorSpec` per-type mode choices + defaults.
  * `Launcher.fire` mode validation + default resolution.
  * `Interceptor.__init__` accepts + stores engagement_mode, defaults
    to spec default, rejects illegal modes.
  * `World.spawn_interceptor` plumbs engagement_mode through to the
    constructed Interceptor instance.

The old `resolve_damage` CPA-falloff tests are gone — AOE replaces that
damage path with a flat-within-radius model. Fragmentation behaviour is
exercised in `test_aoe_damage.py` / `test_htk_unchanged.py`.

Run with `python test_engagement_mode.py`. Exits non-zero on first
failing assertion.
"""
from __future__ import annotations

import numpy as np

from sim.launcher import Launcher, LAUNCHER_TEMPLATES
from sim.entities import Interceptor
from sim.types import INTERCEPTOR_SPECS, InterceptorType
from sim.world import World


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
