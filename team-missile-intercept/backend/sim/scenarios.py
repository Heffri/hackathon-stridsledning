"""Demo scenario wiring — combines Red AI waves, Blue AI, and World."""
from typing import Dict, List, Optional, Tuple

from . import config, sites, terrain
from .blue_ai import BlueAI
from .launcher import LauncherFleet
from .red_ai import RedAI, build_demo_waves
from .types import MatchPhase
from .world import World


class Scenario:
    def __init__(self):
        """Assemble a fresh demo scenario: new World (lands in SETUP
        phase), fresh RedAI driving `build_demo_waves()`, fresh
        BlueAI. Calls `sites.reset_leaks()` because `SOUTH_SITES` is
        a module-level singleton that would otherwise carry leak /
        HP state across scenarios in the same process (tests that
        construct multiple scenarios per-process rely on this).
        """
        # Clear per-site leak counters from any previous scenario
        # instance — SOUTH_SITES is a module-level singleton (the HUD
        # and Red AI both need a single source of truth for targetable
        # sites) so state leaks across runs unless we reset it here.
        sites.reset_leaks()
        self.world = World()
        self.red = RedAI(build_demo_waves())
        self.blue = BlueAI()

    def set_layout(self, roster: Dict[str, List[Tuple[float, float]]]) -> None:
        """Swap `config.BLUE_LAUNCHER_POSITIONS` to `roster` and rebuild
        the Blue launcher fleet in-place. Live-demo hook for the front-
        end layout selector (CANDIDATE_LAYOUTS_2026-04-22.json). Only
        legal in SETUP phase — a layout swap mid-match would orphan any
        in-flight interceptors against removed launchers, and the budget
        accounting below assumes a fresh BLUE_BUDGET_START.

        Every (x, y) in `roster` must pass
        `terrain.point_on_south_land` — positions off south-side land
        are rejected before any mutation, so a bad roster leaves the
        scenario untouched.

        Budget: reset to BLUE_BUDGET_START minus the sum of the new
        roster's base costs, matching the initial scenario build so the
        operator can Start the match with the same economics as a fresh
        default layout.
        """
        if self.world.phase != MatchPhase.SETUP:
            raise RuntimeError(
                f"set_layout only legal in SETUP phase; current phase is "
                f"{self.world.phase.value}"
            )
        for kind, positions in roster.items():
            for (x, y) in positions:
                if not terrain.point_on_south_land(float(x), float(y)):
                    raise ValueError(
                        f"layout roster[{kind!r}]: ({x}, {y}) not on "
                        f"south-side land"
                    )
        config.BLUE_LAUNCHER_POSITIONS.clear()
        config.BLUE_LAUNCHER_POSITIONS.update({
            k: [(float(x), float(y)) for (x, y) in v]
            for k, v in roster.items()
        })
        self.blue.launchers = LauncherFleet()
        base_cost_total = 0
        for kind_str, pos_list in config.BLUE_LAUNCHER_POSITIONS.items():
            cost = config.LAUNCHER_BASE_COSTS.get(kind_str, 0)
            base_cost_total += cost * len(pos_list)
        self.world.blue_budget = max(
            0, config.BLUE_BUDGET_START - base_cost_total
        )

    def set_initial_budgets(self, red_usd: int, blue_usd: int) -> None:
        """Override Red / Blue starting budgets. Legal only during SETUP.

        The World constructor reads `config.RED_BUDGET_START` /
        `config.BLUE_BUDGET_START` to seed `red_budget` / `red_budget_max`
        / `blue_budget` / `blue_budget_max`; this method lets the live
        demo operator tune those numbers at runtime from the Budget panel
        on the SETUP ribbon without editing config.py.

        Both `_max` (HUD bar denominator) and the current balance are
        overwritten — during SETUP nothing has been spent yet so they
        stay in sync. Post-SETUP edits are rejected by the caller
        (`server.py::handle_command`) with an error frame; this method
        also asserts on phase so bypass attempts via a test harness
        surface loudly.
        """
        assert self.world.phase == MatchPhase.SETUP, (
            f"set_initial_budgets only legal in SETUP (phase is "
            f"{self.world.phase.value})"
        )
        self.world.red_budget = int(red_usd)
        self.world.red_budget_max = int(red_usd)
        self.world.blue_budget = int(blue_usd)
        self.world.blue_budget_max = int(blue_usd)

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
          'red'  — all military sites destroyed.
          'blue' — Red can't spawn any more threats AND no Red threats
                   still alive. "Can't spawn more" = either every wave
                   has been processed (`red.done`) or Red's budget is
                   exhausted (`world.red_budget <= 0`, M-TIER3 Issue #8).
          'draw' — 3600 s safety cap reached (should basically never fire).
          None   — match still in progress.

        Red-victory check fires first so that a leak that both drops the
        last Blue HP AND was the final threat on the map resolves as a
        Red win rather than a Blue one. This matches operator intent:
        "if Blue is down to a dying site, Red got through."

        Interim multi-site rule (Issue #9, tracked in ISSUES_2026-04-19):
        partial base loss no longer ends the match — Red only wins when
        every military site is at HP 0. Military = subtypes 'air_base'
        and 'base'. Capital short-circuit is deferred to Tier 4 (arena
        rescale needed to re-include Meridia).

        Issue #21 (M-TIER2.8, 2026-04-20): `blue_budget <= 0` no longer
        auto-ends the match as a Red win. Budget is an economic HUD
        indicator; the match continues with Blue defending using its
        remaining in-flight interceptors and magazine reserve. If Blue
        truly can't fight back, remaining Red threats will deplete site
        HP and the military-site HP loss path fires naturally. Scenarios
        where Blue spends its last dollar on a mid-air interceptor that
        then kills the last remaining drone now resolve as a Blue win
        (as they should — base intact, threats resolved, waves done).

        Issue #8 (M-TIER3-RED-BUDGET, 2026-04-20): Red now has a finite
        pool too. The Blue-victory clause extends to fire when Red is
        effectively done spawning — either `red.done` (all scheduled
        waves processed) or `world.red_budget <= 0` (bankrupt Red
        can't afford more threats). Under the current wave-driven Red
        AI `red.done` fires first because default waves cost $54.3 M
        vs $100 M RED_BUDGET_START; the budget disjunct is live for
        the future Boyu Red AI that spawns against a tactical budget
        rather than a wave schedule.
        """
        military = [
            s for s in sites.SOUTH_SITES
            if s.subtype in ("air_base", "base")
        ]
        if military and all(s.hp <= 0 for s in military):
            return "red"
        # Issue #21: budget depletion is NOT an auto-loss anymore. The
        # old `if self.world.blue_budget <= 0: return "red"` block was
        # removed here — see the winner docstring above for rationale.
        red_cant_spawn_more = self.red.done or self.world.red_budget <= 0
        no_threats_alive = all(
            not t.state.alive for t in self.world.threats.values()
        )
        if red_cant_spawn_more and no_threats_alive:
            return "blue"
        if self.world.t >= config.MAX_SIM_TIME:
            return "draw"
        return None

    @property
    def done(self) -> bool:
        return self.winner is not None

    def snapshot(self) -> dict:
        """Full snapshot broadcast every `1/config.STREAM_HZ` seconds
        by `server.py`. Extends `world.snapshot()` with AI log tails,
        launcher state, site HP, winner, `max_sim_time`, and the
        current Match Phase. Keys: see `RUNTIME_MAP.md` + this
        file for the live shape. Runtime shell rule (see
        `common-info/RUNTIME_STABILITY_RULES.md`): prefer additive
        changes; only rename existing keys via a dedicated
        integration change.
        """
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
                "id": s.id,
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
