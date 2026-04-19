"""Demo scenario wiring — combines Red AI waves, Blue AI, and World."""
from typing import Optional

from . import config, sites
from .blue_ai import BlueAI
from .red_ai import RedAI, build_demo_waves
from .types import MatchPhase
from .world import World


class Scenario:
    def __init__(self):
        # Clear per-site leak counters from any previous scenario
        # instance — SOUTH_SITES is a module-level singleton (the HUD
        # and Red AI both need a single source of truth for targetable
        # sites) so state leaks across runs unless we reset it here.
        sites.reset_leaks()
        self.world = World()
        self.red = RedAI(build_demo_waves())
        self.blue = BlueAI()

    def step(self, dt: float) -> None:
        """Advance one sim tick, respecting the Match Phase FSM.

        M-TIER2-PHASE: if `world.phase` is anything other than RUNNING
        (i.e. SETUP, PAUSED, or FINISHED), the tick is a no-op — events
        are cleared so a stale events list doesn't get re-broadcast, but
        `world.t` does not advance and neither AI steps. This freezes
        every sim-time-based timer (reload / fuel / cooldown
        comparisons against `world.t`) along with the physics, which is
        the correct behaviour for pause / setup.

        At the end of a normal RUNNING tick, if a winner has been
        declared we auto-transition RUNNING → FINISHED so the server /
        frontend can render the end-of-match overlay without the
        Scenario doing any extra bookkeeping.
        """
        # Events are cleared here (before both the phase gate and the
        # AI / world.step calls) rather than inside `world.step` — doing
        # it mid-tick would wipe launch events that `blue_ai.step` just
        # appended.
        self.world.events = []
        if self.world.phase != MatchPhase.RUNNING:
            return
        self.red.step(self.world.t, self.world)
        self.blue.step(self.world.t, self.world)
        self.world.step(dt)
        self.world.prune_dead()
        # Auto-transition to FINISHED as soon as a winner is declared.
        # Scenario.winner inspects world/site/budget state; we only act
        # when we were actually in RUNNING (PAUSED → FINISHED is driven
        # by the server layer when a mid-pause win resolves — unusual
        # but the transition table allows it).
        if self.winner is not None and self.world.phase == MatchPhase.RUNNING:
            self.world.transition(MatchPhase.FINISHED)

    @property
    def winner(self) -> Optional[str]:
        """Milestone I win-condition resolver.

        Returns:
          'red'  — all military sites destroyed, or Blue budget exhausted.
          'blue' — all Red waves spawned AND no Red threats still alive.
          'draw' — 3600 s safety cap reached (should basically never fire).
          None   — match still in progress.

        Red-victory checks fire first so that a leak that both drops the
        last Blue HP AND was the final threat on the map resolves as a
        Red win rather than a Blue one. This matches operator intent:
        "if Blue is down to a dying site, Red got through."

        Interim multi-site rule (Issue #9, tracked in ISSUES_2026-04-19):
        partial base loss no longer ends the match — Red only wins when
        every military site is at HP 0. Military = subtypes 'air_base'
        and 'base'. Capital short-circuit is deferred to Tier 4 (arena
        rescale needed to re-include Meridia).
        """
        if self.world.blue_budget <= 0:
            return "red"
        military = [
            s for s in sites.SOUTH_SITES
            if s.subtype in ("air_base", "base")
        ]
        if military and all(s.hp <= 0 for s in military):
            return "red"
        if self.red.done and all(
            not t.state.alive for t in self.world.threats.values()
        ):
            return "blue"
        if self.world.t >= config.MAX_SIM_TIME:
            return "draw"
        return None

    @property
    def done(self) -> bool:
        return self.winner is not None

    def snapshot(self) -> dict:
        snap = self.world.snapshot()
        snap["wave"] = self.red._next_wave
        snap["total_waves"] = len(self.red.waves)
        snap["red_log"] = self.red.log[-6:]
        snap["blue_log"] = self.blue.log[-6:]
        # fleet_status is now a two-field dict: {'by_kind': ..., 'launchers': ...}.
        # The HUD ammo panel consumes `snap['ammo']` as by_kind; the per-
        # launcher list is hoisted to `snap['launchers']` so the scene
        # code can render a box + arc per instance.
        fleet = self.blue.launchers.fleet_status(self.world.t)
        snap["ammo"] = fleet["by_kind"]
        snap["launchers"] = fleet["launchers"]
        # Visible Red offensive launchers (Milestone H Part 3). One
        # record per drone / cruise box on the north side; ballistic +
        # HGV don't have visible launchers. Infinite-magazine, so no
        # ammo / reload fields.
        snap["red_launchers"] = self.red.launchers.fleet_status()
        # Per-site state for the HUD's SITE DAMAGE panel + site markers.
        # Position is a list-of-2 for trivial JSON round-trip.
        snap["sites"] = [
            {
                "name": s.name,
                "subtype": s.subtype,
                "pos": [s.pos[0], s.pos[1]],
                "hp": s.hp,
                "hp_max": s.hp_max,
                "leaks": s.leaks,
            }
            for s in sites.SOUTH_SITES
        ]
        # Milestone I: publish winner + match timer so the frontend can
        # render the end-of-match overlay AND the countdown to the 3600 s
        # safety cap. `winner` is None while the match is in progress.
        snap["winner"] = self.winner
        snap["max_sim_time"] = config.MAX_SIM_TIME
        # M-TIER2-PHASE: Match Phase is the single source of truth the
        # HUD reads to decide which chip / overlay / button state to
        # render. Always a string value ("setup" / "running" / "paused"
        # / "finished") from the MatchPhase enum.
        snap["phase"] = self.world.phase.value
        return snap


def build_default_scenario(auto_start: bool = True) -> Scenario:
    """Construct the default demo scenario.

    M-TIER2-PHASE adds `auto_start`. A fresh `World` starts in SETUP;
    headless callers (test_balance, test_full_scenario, ...) expect the
    old behaviour where `scn.step(dt)` advances immediately, so the
    default is `True` — we transition SETUP → RUNNING right after the
    scenario is built. The server passes `auto_start=False` so the
    interactive client walks through the real SETUP → (player clicks
    Start) → RUNNING flow needed by the deployment UI (M-TIER2-J).
    """
    scn = Scenario()
    if auto_start:
        scn.world.transition(MatchPhase.RUNNING)
    return scn
