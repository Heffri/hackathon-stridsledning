"""Bug 5 regression: ScriptedRedAI skips spawns targeting dead sites.

Pre-fix, ScriptedRed chains kept attacking a site whose HP had reached
zero, burning ~30% of Red's 150M budget on threats targeting a corpse
for the rest of the match. Both demo optics (watching Red keep bombing
a smoking crater) and Red's effective saturation (budget concentrated
on surviving sites) suffered.

After fix: every ScriptedRed spawn-path checks `site.hp <= 0` before
deducting budget / spawning the threat. Chains for surviving sites
continue normally.
"""
from __future__ import annotations

import sys

from sim import config, sites
from sim.red_ai import ScriptedRedAI
from sim.types import MatchPhase
from sim.world import World


def _spawn_ids_by_site(world: World) -> dict:
    """Group alive threat ids by their target_site_id."""
    out: dict = {}
    for tid, th in world.threats.items():
        sid = getattr(th, "_target_site_id", None)
        out.setdefault(sid, []).append(tid)
    return out


def _run_scripted_red(duration_s: float, dt: float = 0.05,
                      kill_site_id: int = None) -> tuple:
    """Run one ScriptedRed match for `duration_s`. If `kill_site_id` is
    set, force that site's HP to 0 at t=0 before the Red AI initialises.
    Returns (world, red)."""
    sites.reset_leaks()
    world = World()
    world.blue_budget = int(config.BLUE_BUDGET_START)
    world.blue_budget_max = int(config.BLUE_BUDGET_START)
    world.red_budget = 150_000_000
    world.red_budget_max = 150_000_000
    # Zero the target site BEFORE ScriptedRed initialises.
    if kill_site_id is not None:
        target_site = sites.find_site_by_id(kill_site_id)
        assert target_site is not None, f"site {kill_site_id} not found"
        target_site.hp = 0
    red = ScriptedRedAI(None)
    world.transition(MatchPhase.RUNNING)
    steps = int(duration_s / dt)
    for _ in range(steps):
        world.events = []
        red.step(world.t, world)
        world.step(dt)
        world.prune_dead()
    return world, red


def test_dead_site_receives_no_spawns() -> None:
    """Kill site A's HP to 0 at t=0. A 200 s scripted-Red match must
    spawn zero threats targeting A, while B and C chains continue."""
    # Build a throwaway world to enumerate military sites.
    sites.reset_leaks()
    military = [s for s in sites.SOUTH_SITES if s.subtype in ("base", "air_base")]
    assert len(military) >= 2, (
        f"test needs >=2 military sites, got {len(military)}"
    )
    victim = military[0]
    survivor_ids = {s.id for s in military[1:]}
    world, red = _run_scripted_red(duration_s=200.0, kill_site_id=victim.id)
    by_site = _spawn_ids_by_site(world)
    # All threats ever recorded in `world.threats` include pruned-ids too;
    # but we need to check threats that GOT SPAWNED, not just alive ones.
    # `world.threats` only keeps threats that haven't been deleted; for a
    # 200s match with cheap drones dying mid-flight the dict may prune
    # some. However `world.spawn_threat` assigns stable ids and we don't
    # track spawned-ever. So approximate: track spawn events via the
    # ScriptedRed log lines AND check world.threats by target_site_id.
    # Simpler: rely on Red's log which records every spawn attempt.
    victim_mentions = [
        line for line in red.log
        if victim.name in line and ("drone" in line or "cruise" in line or
                                     "ballistic" in line or "hgv" in line)
    ]
    # In the fix, zero spawns for victim chain. In the no-fix world, the
    # chain would have fired the initial d1 drone batch at t=0 (10 drones).
    # Allow ONLY the init-chain announcement ("ScriptedRed init — N chains")
    # which mentions the site name but doesn't start with "[t] victim.name
    # dN:" etc. Our filter is substring-based so we must be stricter:
    victim_batch_lines = [
        line for line in red.log
        # Example batch line: "[  1.0s] Main Base d1: 10/10 drone(s) ..."
        if f"] {victim.name} " in line and ("/10 drone" in line
                                             or "/5 cruise" in line
                                             or " ballistic from" in line
                                             or " hgv from" in line)
    ]
    assert len(victim_batch_lines) == 0, (
        f"dead site {victim.name!r} received {len(victim_batch_lines)} "
        f"spawn-batches despite hp=0 at t=0:\n" + "\n".join(victim_batch_lines)
    )
    # And the surviving sites should have spawned SOMETHING (at least
    # the initial drone batch) — regression guard for the healthy-path.
    survivor_names = {s.name for s in military[1:]}
    survivor_batches = [
        line for line in red.log
        if any(f"] {name} " in line for name in survivor_names)
        and ("/10 drone" in line or "/5 cruise" in line)
    ]
    assert len(survivor_batches) > 0, (
        f"surviving sites {survivor_names} got no batches in 200s — "
        f"regression vs healthy default path. Red log:\n"
        + "\n".join(red.log)
    )
    print(f"ok  test_dead_site_receives_no_spawns  "
          f"(victim={victim.name}, survivor batches={len(survivor_batches)})")


def test_healthy_default_all_sites_spawn() -> None:
    """All military sites alive → every chain fires its initial drone
    batch in the first few seconds. Regression guard for the default
    path after adding the gate."""
    world, red = _run_scripted_red(duration_s=5.0, kill_site_id=None)
    sites.reset_leaks()  # post-run cleanup
    military_names = {s.name for s in sites.SOUTH_SITES
                      if s.subtype in ("base", "air_base")}
    mentioned = set()
    for line in red.log:
        for name in military_names:
            if f"] {name} d1:" in line and "drone" in line:
                mentioned.add(name)
    assert mentioned == military_names, (
        f"healthy path regression: expected d1 batches for all of "
        f"{military_names}, got {mentioned}. Red log:\n"
        + "\n".join(red.log)
    )
    print(f"ok  test_healthy_default_all_sites_spawn  sites={mentioned}")


def main() -> None:
    test_dead_site_receives_no_spawns()
    test_healthy_default_all_sites_spawn()
    print("\nAll 2 red-skip-dead-site tests passed.")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
