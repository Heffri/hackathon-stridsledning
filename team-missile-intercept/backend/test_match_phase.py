"""Match Phase FSM unit + integration tests (M-TIER2-PHASE).

Covers the legal transition table in `sim.types.LEGAL_PHASE_TRANSITIONS`
and enforced by `World.transition`, plus Subtask-B integration checks
that `Scenario.step` freezes the sim in non-RUNNING phases. Run with
`python test_match_phase.py`.
"""
import numpy as np

from sim.scenarios import Scenario, build_default_scenario
from sim.types import LEGAL_PHASE_TRANSITIONS, MatchPhase
from sim.world import World


ALL_PHASES = [
    MatchPhase.SETUP,
    MatchPhase.RUNNING,
    MatchPhase.PAUSED,
    MatchPhase.FINISHED,
]


def _fresh_world_in(phase: MatchPhase) -> World:
    """Put a new World into `phase` by walking the legal path from SETUP.

    Paths used by the tests below:
      SETUP      : default-constructed World (no transition needed).
      RUNNING    : SETUP → RUNNING.
      PAUSED     : SETUP → RUNNING → PAUSED.
      FINISHED   : SETUP → RUNNING → FINISHED.
    """
    w = World()
    assert w.phase == MatchPhase.SETUP
    if phase == MatchPhase.SETUP:
        return w
    assert w.transition(MatchPhase.RUNNING)
    if phase == MatchPhase.RUNNING:
        return w
    if phase == MatchPhase.PAUSED:
        assert w.transition(MatchPhase.PAUSED)
        return w
    if phase == MatchPhase.FINISHED:
        assert w.transition(MatchPhase.FINISHED)
        return w
    raise AssertionError(f"unreachable phase {phase}")


def test_default_phase_is_setup() -> None:
    w = World()
    assert w.phase == MatchPhase.SETUP


def test_all_legal_transitions_succeed() -> None:
    """Every edge in LEGAL_PHASE_TRANSITIONS should return True and
    leave the world in the target phase."""
    for (src, dst) in LEGAL_PHASE_TRANSITIONS:
        w = _fresh_world_in(src)
        ok = w.transition(dst)
        assert ok, f"legal transition {src.value} → {dst.value} returned False"
        assert w.phase == dst, (
            f"after {src.value} → {dst.value}, phase is {w.phase.value}"
        )


def test_all_illegal_transitions_refused() -> None:
    """Every (src, dst) pair NOT in the legal table must return False
    and leave the phase unchanged."""
    illegal_count = 0
    for src in ALL_PHASES:
        for dst in ALL_PHASES:
            if (src, dst) in LEGAL_PHASE_TRANSITIONS:
                continue
            w = _fresh_world_in(src)
            ok = w.transition(dst)
            assert not ok, (
                f"illegal transition {src.value} → {dst.value} "
                f"returned True (state now {w.phase.value})"
            )
            assert w.phase == src, (
                f"after refused {src.value} → {dst.value}, phase changed "
                f"to {w.phase.value}"
            )
            illegal_count += 1
    # Sanity: 4 phases × 4 phases − 6 legal = 10 illegal pairs (incl.
    # self-loops, which we also treat as illegal).
    assert illegal_count == 10, f"expected 10 illegal pairs, got {illegal_count}"


def test_finished_only_exits_via_setup() -> None:
    """FINISHED must refuse direct transitions to RUNNING or PAUSED;
    the only legal exit is SETUP (reset)."""
    for forbidden in (MatchPhase.RUNNING, MatchPhase.PAUSED, MatchPhase.FINISHED):
        w = _fresh_world_in(MatchPhase.FINISHED)
        ok = w.transition(forbidden)
        assert not ok
        assert w.phase == MatchPhase.FINISHED

    w = _fresh_world_in(MatchPhase.FINISHED)
    assert w.transition(MatchPhase.SETUP)
    assert w.phase == MatchPhase.SETUP


def test_self_transitions_refused() -> None:
    """A no-op same-phase transition must be refused so double-clicks
    surface as an error rather than being silently swallowed."""
    for p in ALL_PHASES:
        w = _fresh_world_in(p)
        assert not w.transition(p)
        assert w.phase == p


# --- Subtask B: Scenario.step phase-gating integration -------------


def _step_n(scn: Scenario, n: int, dt: float = 0.05) -> None:
    for _ in range(n):
        scn.step(dt)


def test_setup_phase_freezes_scenario() -> None:
    """A freshly built scenario in SETUP should not advance on step()."""
    scn = build_default_scenario(auto_start=False)
    assert scn.world.phase == MatchPhase.SETUP
    t_before = scn.world.t
    _step_n(scn, 60)  # 3 sim-seconds of attempted ticks
    assert scn.world.t == t_before, (
        f"world.t advanced during SETUP: {t_before} → {scn.world.t}"
    )
    assert len(scn.world.threats) == 0, (
        f"threats spawned during SETUP: {len(scn.world.threats)}"
    )


def test_running_phase_advances_scenario() -> None:
    """After SETUP → RUNNING, sim-time moves and wave 1 (t=2s) fires."""
    scn = build_default_scenario(auto_start=False)
    assert scn.world.transition(MatchPhase.RUNNING)
    _step_n(scn, 60)  # 3 sim-seconds — wave 1 spawns at t = 2.0 s
    assert scn.world.t > 0.0, "world.t did not advance while RUNNING"
    assert len(scn.world.threats) > 0, (
        "no threats spawned after 3 RUNNING seconds — wave 1 never fired"
    )


def test_pause_freezes_mid_match() -> None:
    """RUNNING → PAUSED should freeze world.t and leave threats at the
    same positions; subsequent step() calls are no-ops."""
    scn = build_default_scenario(auto_start=True)
    _step_n(scn, 60)  # roll wave 1 into existence
    assert len(scn.world.threats) > 0

    # Freeze the scene. `world.t` and every threat position should be
    # identical before and after a burst of paused ticks.
    assert scn.world.transition(MatchPhase.PAUSED)
    t_frozen = scn.world.t
    pos_frozen = {
        tid: threat.state.pos.copy()
        for tid, threat in scn.world.threats.items()
    }
    _step_n(scn, 120)  # 6 sim-seconds of attempted ticks
    assert scn.world.t == t_frozen, (
        f"world.t advanced during PAUSED: {t_frozen} → {scn.world.t}"
    )
    for tid, frozen in pos_frozen.items():
        cur = scn.world.threats[tid].state.pos
        assert np.allclose(cur, frozen), (
            f"threat {tid} moved during PAUSED: {frozen} → {cur}"
        )


def test_resume_continues_from_pause() -> None:
    """PAUSED → RUNNING should resume sim-time advancement from the
    frozen value and let the AI keep stepping."""
    scn = build_default_scenario(auto_start=True)
    _step_n(scn, 60)
    assert scn.world.transition(MatchPhase.PAUSED)
    t_before = scn.world.t
    _step_n(scn, 40)  # burn paused ticks
    assert scn.world.t == t_before

    assert scn.world.transition(MatchPhase.RUNNING)
    _step_n(scn, 20)
    assert scn.world.t > t_before, (
        f"world.t did not resume after PAUSED → RUNNING: {t_before} → {scn.world.t}"
    )


def test_auto_start_default_true_for_tests() -> None:
    """Headless callers rely on the default auto_start=True so existing
    tests (test_balance, test_full_scenario, ...) keep working without
    needing to know about phases."""
    scn = build_default_scenario()
    assert scn.world.phase == MatchPhase.RUNNING


def test_auto_start_false_yields_setup() -> None:
    """Server passes auto_start=False so the client drives the real
    SETUP → RUNNING flow through a `start` command."""
    scn = build_default_scenario(auto_start=False)
    assert scn.world.phase == MatchPhase.SETUP


# --- Subtask C: WebSocket command handler semantics ---------------

def _fresh_runner():
    """Import lazily — SimRunner imports FastAPI/asyncio which is only
    relevant to the protocol tests."""
    from server import SimRunner
    return SimRunner()


def test_cmd_start_from_setup_acks_running() -> None:
    runner = _fresh_runner()
    assert runner.scenario.world.phase == MatchPhase.SETUP
    resp = runner.handle_command({"cmd": "start"})
    assert resp == {"type": "phase_change", "phase": "running"}
    assert runner.scenario.world.phase == MatchPhase.RUNNING


def test_cmd_start_while_running_returns_illegal_error() -> None:
    runner = _fresh_runner()
    runner.handle_command({"cmd": "start"})
    resp = runner.handle_command({"cmd": "start"})
    assert resp == {
        "type": "error",
        "reason": "illegal_transition",
        "from": "running",
        "to": "running",
    }
    assert runner.scenario.world.phase == MatchPhase.RUNNING


def test_cmd_pause_resume_round_trip() -> None:
    runner = _fresh_runner()
    runner.handle_command({"cmd": "start"})
    resp = runner.handle_command({"cmd": "pause"})
    assert resp == {"type": "phase_change", "phase": "paused"}
    assert runner.scenario.world.phase == MatchPhase.PAUSED

    resp = runner.handle_command({"cmd": "resume"})
    assert resp == {"type": "phase_change", "phase": "running"}
    assert runner.scenario.world.phase == MatchPhase.RUNNING


def test_cmd_pause_from_setup_errors() -> None:
    runner = _fresh_runner()
    resp = runner.handle_command({"cmd": "pause"})
    assert resp["type"] == "error"
    assert resp["from"] == "setup"
    assert resp["to"] == "paused"
    assert runner.scenario.world.phase == MatchPhase.SETUP


def test_cmd_resume_from_running_errors() -> None:
    runner = _fresh_runner()
    runner.handle_command({"cmd": "start"})
    resp = runner.handle_command({"cmd": "resume"})
    assert resp["type"] == "error"
    assert resp["from"] == "running"
    assert resp["to"] == "running"


def test_cmd_reset_always_returns_to_setup() -> None:
    """Reset rebuilds the World; any source phase is acceptable and the
    response is a phase_change → setup (never an error)."""
    runner = _fresh_runner()
    # From SETUP.
    resp = runner.handle_command({"cmd": "reset"})
    assert resp == {"type": "phase_change", "phase": "setup"}
    assert runner.scenario.world.phase == MatchPhase.SETUP
    # From RUNNING.
    runner.handle_command({"cmd": "start"})
    resp = runner.handle_command({"cmd": "reset"})
    assert resp == {"type": "phase_change", "phase": "setup"}
    assert runner.scenario.world.phase == MatchPhase.SETUP
    # From PAUSED.
    runner.handle_command({"cmd": "start"})
    runner.handle_command({"cmd": "pause"})
    resp = runner.handle_command({"cmd": "reset"})
    assert resp == {"type": "phase_change", "phase": "setup"}


def test_cmd_speed_returns_none() -> None:
    runner = _fresh_runner()
    resp = runner.handle_command({"cmd": "speed", "value": 5.0})
    assert resp is None
    assert runner.speed == 5.0


def test_snapshot_carries_phase_field() -> None:
    scn = build_default_scenario(auto_start=False)
    snap = scn.snapshot()
    assert snap["phase"] == "setup"
    scn.world.transition(MatchPhase.RUNNING)
    snap = scn.snapshot()
    assert snap["phase"] == "running"


# --- Entry point ---------------------------------------------------
if __name__ == "__main__":
    tests = [
        test_default_phase_is_setup,
        test_all_legal_transitions_succeed,
        test_all_illegal_transitions_refused,
        test_finished_only_exits_via_setup,
        test_self_transitions_refused,
        test_setup_phase_freezes_scenario,
        test_running_phase_advances_scenario,
        test_pause_freezes_mid_match,
        test_resume_continues_from_pause,
        test_auto_start_default_true_for_tests,
        test_auto_start_false_yields_setup,
        test_cmd_start_from_setup_acks_running,
        test_cmd_start_while_running_returns_illegal_error,
        test_cmd_pause_resume_round_trip,
        test_cmd_pause_from_setup_errors,
        test_cmd_resume_from_running_errors,
        test_cmd_reset_always_returns_to_setup,
        test_cmd_speed_returns_none,
        test_snapshot_carries_phase_field,
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
    print(f"\nAll {passed} match-phase unit tests passed.")
