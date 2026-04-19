"""Match Phase + Scenario integration tests (M-TIER2-PHASE, Subtask E).

Covers end-to-end lifecycles that touch Scenario + World + winner
resolution. Unit-level FSM tests live in `test_match_phase.py`; this
file focuses on the stitch between Scenario.step and the phase FSM:
auto-FINISHED transition, pause mid-match, reset after finish, and
cross-context illegal transitions.

Run with `python test_match_phase_integration.py`.
"""
import numpy as np

from sim.scenarios import Scenario, build_default_scenario
from sim.types import MatchPhase


DT = 0.05


def _force_red_win(scn: Scenario) -> None:
    """Deterministically trigger a Red win by zeroing the Blue budget.
    `Scenario.winner` returns 'red' as soon as `blue_budget <= 0`, so
    the next RUNNING step auto-transitions RUNNING → FINISHED."""
    scn.world.blue_budget = 0


# --- Lifecycle: happy path ---------------------------------------


def test_lifecycle_setup_running_finished() -> None:
    scn = build_default_scenario(auto_start=False)
    assert scn.world.phase == MatchPhase.SETUP

    # SETUP frozen: N ticks, no advance.
    for _ in range(30):
        scn.step(DT)
    assert scn.world.t == 0.0
    assert len(scn.world.threats) == 0

    # SETUP → RUNNING
    assert scn.world.transition(MatchPhase.RUNNING)
    for _ in range(60):
        scn.step(DT)
    assert scn.world.t > 0.0
    assert scn.world.phase == MatchPhase.RUNNING
    assert scn.winner is None

    # RUNNING → FINISHED (winner fires, Scenario.step auto-transitions).
    _force_red_win(scn)
    scn.step(DT)
    assert scn.world.phase == MatchPhase.FINISHED
    assert scn.winner == "red"

    # Any further steps in FINISHED are no-ops.
    t_finished = scn.world.t
    for _ in range(20):
        scn.step(DT)
    assert scn.world.t == t_finished


# --- Lifecycle: pause mid-match ----------------------------------


def test_lifecycle_pause_midmatch_then_finish() -> None:
    scn = build_default_scenario(auto_start=False)
    assert scn.world.transition(MatchPhase.RUNNING)
    for _ in range(60):
        scn.step(DT)
    assert scn.world.phase == MatchPhase.RUNNING

    # Pause and verify sim is frozen: world.t + every threat pos.
    assert scn.world.transition(MatchPhase.PAUSED)
    t_frozen = scn.world.t
    pos_frozen = {
        tid: threat.state.pos.copy()
        for tid, threat in scn.world.threats.items()
    }
    for _ in range(120):
        scn.step(DT)
    assert scn.world.t == t_frozen
    for tid, frozen in pos_frozen.items():
        assert np.allclose(scn.world.threats[tid].state.pos, frozen)

    # Resume and advance one more tick; time should move.
    assert scn.world.transition(MatchPhase.RUNNING)
    scn.step(DT)
    assert scn.world.t > t_frozen

    # Force a Red win and confirm the auto-FINISHED path.
    _force_red_win(scn)
    scn.step(DT)
    assert scn.world.phase == MatchPhase.FINISHED


# --- Lifecycle: reset after finish --------------------------------


def test_reset_after_finish_returns_to_setup() -> None:
    """After FINISHED, the server's `reset` rebuilds the scenario into a
    fresh SETUP. Here we simulate the rebuild directly since the
    integration test is scenario-layer, not WebSocket."""
    scn = build_default_scenario(auto_start=False)
    scn.world.transition(MatchPhase.RUNNING)
    _force_red_win(scn)
    scn.step(DT)
    assert scn.world.phase == MatchPhase.FINISHED

    # The `reset` command rebuilds the scenario in SETUP.
    fresh = build_default_scenario(auto_start=False)
    assert fresh.world.phase == MatchPhase.SETUP
    assert fresh.world.t == 0.0
    assert len(fresh.world.threats) == 0

    # A follow-up `start` transitions into RUNNING.
    assert fresh.world.transition(MatchPhase.RUNNING)
    fresh.step(DT)
    assert fresh.world.t > 0.0


# --- Illegal transitions in real scenarios ------------------------


def test_illegal_transitions_in_scenario_context() -> None:
    scn = build_default_scenario(auto_start=False)

    # SETUP cannot jump straight to PAUSED / FINISHED.
    assert not scn.world.transition(MatchPhase.PAUSED)
    assert not scn.world.transition(MatchPhase.FINISHED)
    assert scn.world.phase == MatchPhase.SETUP

    # SETUP → RUNNING → SETUP is illegal (RUNNING cannot roll back).
    assert scn.world.transition(MatchPhase.RUNNING)
    assert not scn.world.transition(MatchPhase.SETUP)
    assert scn.world.phase == MatchPhase.RUNNING

    # RUNNING → PAUSED → SETUP also illegal — only reset (rebuild)
    # short-circuits the FSM.
    assert scn.world.transition(MatchPhase.PAUSED)
    assert not scn.world.transition(MatchPhase.SETUP)
    assert scn.world.phase == MatchPhase.PAUSED

    # Back to RUNNING, force finish, then FINISHED rejects RUNNING and
    # PAUSED. Only SETUP is a legal exit.
    assert scn.world.transition(MatchPhase.RUNNING)
    _force_red_win(scn)
    scn.step(DT)
    assert scn.world.phase == MatchPhase.FINISHED
    assert not scn.world.transition(MatchPhase.RUNNING)
    assert not scn.world.transition(MatchPhase.PAUSED)
    assert scn.world.transition(MatchPhase.SETUP)
    assert scn.world.phase == MatchPhase.SETUP


# --- Snapshot emits phase --------------------------------------------


def test_snapshot_phase_reflects_transitions() -> None:
    scn = build_default_scenario(auto_start=False)
    assert scn.snapshot()["phase"] == "setup"
    scn.world.transition(MatchPhase.RUNNING)
    assert scn.snapshot()["phase"] == "running"
    scn.world.transition(MatchPhase.PAUSED)
    assert scn.snapshot()["phase"] == "paused"
    scn.world.transition(MatchPhase.RUNNING)
    _force_red_win(scn)
    scn.step(DT)
    assert scn.snapshot()["phase"] == "finished"
    assert scn.snapshot()["winner"] == "red"


# --- Entry point -------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_lifecycle_setup_running_finished,
        test_lifecycle_pause_midmatch_then_finish,
        test_reset_after_finish_returns_to_setup,
        test_illegal_transitions_in_scenario_context,
        test_snapshot_phase_reflects_transitions,
    ]
    for fn in tests:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\nAll {len(tests)} integration tests passed.")
