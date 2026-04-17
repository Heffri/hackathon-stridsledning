"""Demo scenario wiring — combines Red AI waves, Blue AI, and World."""
from . import config, sites
from .blue_ai import BlueAI
from .red_ai import RedAI, build_demo_waves
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
        # Clear last tick's events before anyone appends new ones. Doing
        # this at world.step's start would wipe launch events that
        # blue_ai.step just appended.
        self.world.events = []
        self.red.step(self.world.t, self.world)
        self.blue.step(self.world.t, self.world)
        self.world.step(dt)
        self.world.prune_dead()

    @property
    def done(self) -> bool:
        # Done when all waves spawned and nothing active
        return (
            self.red.done
            and all(not t.state.alive for t in self.world.threats.values())
            and all(not i.state.alive for i in self.world.interceptors.values())
            and self.world.t > 180.0
        )

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
        # Per-site state for the HUD's SITE DAMAGE panel + site markers.
        # Position is a list-of-2 for trivial JSON round-trip.
        snap["sites"] = [
            {
                "name": s.name,
                "subtype": s.subtype,
                "pos": [s.pos[0], s.pos[1]],
                "hp": s.hp,
                "leaks": s.leaks,
            }
            for s in sites.SOUTH_SITES
        ]
        return snap


def build_default_scenario() -> Scenario:
    return Scenario()
