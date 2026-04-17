"""Demo scenario wiring — combines Red AI waves, Blue AI, and World."""
from . import config
from .blue_ai import BlueAI
from .red_ai import RedAI, build_demo_waves
from .world import World


class Scenario:
    def __init__(self):
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
        snap["ammo"] = self.blue.launchers.fleet_status(self.world.t)
        return snap


def build_default_scenario() -> Scenario:
    return Scenario()
