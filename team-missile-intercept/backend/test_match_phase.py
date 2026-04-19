"""Match Phase FSM unit tests (M-TIER2-PHASE).

Covers the legal transition table defined in `sim.types.LEGAL_PHASE_TRANSITIONS`
and enforced by `World.transition`. No scenario / server coupling — pure
state-machine coverage. Run with `python test_match_phase.py`.
"""
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


# --- Entry point ---------------------------------------------------
if __name__ == "__main__":
    tests = [
        test_default_phase_is_setup,
        test_all_legal_transitions_succeed,
        test_all_illegal_transitions_refused,
        test_finished_only_exits_via_setup,
        test_self_transitions_refused,
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
