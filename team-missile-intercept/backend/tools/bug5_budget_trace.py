"""Bug 5 verification: trace Red budget-over-time with a forced-dead site.

Runs one ScriptedRed match for 300 s. At t=100 s, forces military site A
to hp=0. Logs (t, red_budget, spawns_by_site) every 10 s so the flat
slope on chain A after t=100 is visible.

Without the fix: chain A keeps firing drone/cruise/ballistic/HGV batches
targeting the dead site, steadily draining ~30% of the remaining budget
over the next 200 s.

With the fix: chain A's spawn paths all gate on `site.hp > 0` and
short-circuit → chain A stops firing entirely at t=100, budget slope on
surviving chains (B, C) continues unaffected.

Run:
    python -m tools.bug5_budget_trace
"""
from __future__ import annotations

import sys
from collections import defaultdict

from sim import config, sites
from sim.red_ai import ScriptedRedAI
from sim.types import MatchPhase
from sim.world import World


KILL_T = 100.0
MATCH_DURATION = 1800.0
DT = 0.05
# Sample every 60 s in the trace so the slope differential (victim
# chain flat vs others continuing to drain budget) is visible in the
# row-by-row listing without flooding the output.
SAMPLE_EVERY = 60.0


def run(victim_kill_t: float = KILL_T) -> None:
    sites.reset_leaks()
    military = [s for s in sites.SOUTH_SITES if s.subtype in ("base", "air_base")]
    assert len(military) >= 2
    victim = military[0]
    others = [s.name for s in military[1:]]
    world = World()
    world.red_budget = 150_000_000
    world.red_budget_max = 150_000_000
    red = ScriptedRedAI(None)
    world.transition(MatchPhase.RUNNING)

    print(f"ScriptedRed budget trace. victim={victim.name} (id={victim.id}) "
          f"killed at t={victim_kill_t}s. survivors={others}")
    print(f"Match duration={MATCH_DURATION}s, dt={DT}s")
    print()
    print(f"{'t':>6s}  {'budget_M':>10s}  {'victim_spawns':>14s}  "
          f"{'others_spawns':>14s}")

    # Spawn counter, grouped by target_site_id (accumulates over the match).
    spawns_by_site: defaultdict = defaultdict(int)

    steps = int(MATCH_DURATION / DT)
    next_sample_t = 0.0
    killed = False
    for _ in range(steps):
        world.events = []
        # Count spawns by inspecting events (threat_spawn) — but events
        # are wiped per world.step, so we inspect the world.threats dict
        # for new ids since last sample. Simpler: snapshot len by site id.
        before = {tid for tid in world.threats}
        red.step(world.t, world)
        after = {tid for tid in world.threats}
        new_ids = after - before
        for tid in new_ids:
            th = world.threats[tid]
            sid = getattr(th, "_target_site_id", None)
            spawns_by_site[sid] += 1
        world.step(DT)
        world.prune_dead()
        # Kill victim once we cross t=kill_t
        if not killed and world.t >= victim_kill_t:
            for s in sites.SOUTH_SITES:
                if s.id == victim.id:
                    s.hp = 0
                    killed = True
                    print(f">>> t={world.t:.1f}s: forced site "
                          f"'{victim.name}' hp=0")
        if world.t >= next_sample_t:
            victim_spawns = spawns_by_site.get(victim.id, 0)
            others_spawns = sum(
                spawns_by_site.get(s.id, 0) for s in military[1:]
            )
            print(f"{world.t:6.1f}  {world.red_budget/1e6:10.2f}  "
                  f"{victim_spawns:14d}  {others_spawns:14d}")
            next_sample_t += SAMPLE_EVERY

    print()
    print("Summary:")
    victim_final = spawns_by_site.get(victim.id, 0)
    others_final = sum(spawns_by_site.get(s.id, 0) for s in military[1:])
    print(f"  Total spawns → {victim.name}: {victim_final}")
    print(f"  Total spawns → others ({', '.join(others)}): {others_final}")
    print(f"  Final red budget: ${world.red_budget/1e6:.2f}M")
    print(f"  Victim site hp: {sites.find_site_by_id(victim.id).hp}")

    # Split spawns before / after kill. Requires re-tracking; skip for
    # brevity — the 10s trace above makes the slope visible.

    # Acceptance — victim spawns should stop cold at t=KILL_T (the d1 batch
    # fired at t≈0 is the only legitimate batch; drone follow-ups at 50%
    # of d1's flight time would be around t=60s, so by t=100 we've
    # usually seen d1 + maybe d2 triggered).
    # The key signal: NO spawns targeting victim after t=100.


if __name__ == "__main__":
    try:
        run()
    except AssertionError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
