"""Headless balance sweep: run the current 5-wave scenario N times and
print the Blue/Red/Draw tally. Used to tune wave timing and ammo loadouts
so Blue doesn't cruise at 100 % win rate.

Win conditions (per run):
  * Blue win : 0-1 leaked (clean or minor damage absorbed)
  * Red win  : ≥ 3 leaked (base overwhelmed)
  * Draw     : 2 leaked (scraping through)
"""
from sim.scenarios import build_default_scenario


def run_once() -> str:
    scn = build_default_scenario()
    dt = 0.05
    # 1200 s covers all 5 waves PLUS the long drone flight now that
    # drones spawn 125 km north of the base (Milestone G strait-origin
    # rework). At 120 m/s a drone takes ~1040 s to reach the base, so
    # the old 400 s window left most drones still in flight at sim end.
    total_ticks = int(1200.0 / dt)
    for _ in range(total_ticks):
        scn.step(dt)

    snap = scn.snapshot()
    leaked = snap["stats"]["leaked"]
    spawned = snap["stats"]["spawned"]
    intercepts = snap["stats"]["intercepts"]

    if leaked <= 1:
        return "blue"
    if leaked >= 3:
        return "red"
    return "draw"


def run_once_verbose(trace_leaks=None) -> tuple[str, int, int, int]:
    scn = build_default_scenario()
    dt = 0.05
    # See run_once — 1200 s required for drone transit after Milestone G.
    total_ticks = int(1200.0 / dt)
    for _ in range(total_ticks):
        scn.step(dt)
        if trace_leaks is not None:
            for ev in scn.world.events:
                if ev.get("type") == "leak":
                    trace_leaks.append(
                        (round(scn.world.t, 1), ev.get("kind", "?"))
                    )

    snap = scn.snapshot()
    leaked = snap["stats"]["leaked"]
    spawned = snap["stats"]["spawned"]
    intercepts = snap["stats"]["intercepts"]

    if leaked <= 1:
        result = "blue"
    elif leaked >= 3:
        result = "red"
    else:
        result = "draw"
    return result, spawned, intercepts, leaked


def main(n: int = 20) -> None:
    tally = {"blue": 0, "red": 0, "draw": 0}
    spawned_list = []
    intercept_list = []
    leak_list = []
    leak_kinds = {}
    for i in range(n):
        leaks_trace = []
        res, spawned, intercepts, leaked = run_once_verbose(leaks_trace)
        tally[res] += 1
        spawned_list.append(spawned)
        intercept_list.append(intercepts)
        leak_list.append(leaked)
        for _, k in leaks_trace:
            leak_kinds[k] = leak_kinds.get(k, 0) + 1
    print(
        f"Blue win {tally['blue']}/{n}, "
        f"draw {tally['draw']}/{n}, "
        f"Red win {tally['red']}/{n}"
    )
    print(
        f"  avg spawned={sum(spawned_list)/n:.1f}  "
        f"avg intercepts={sum(intercept_list)/n:.1f}  "
        f"avg leaks={sum(leak_list)/n:.1f}  "
        f"leak range={min(leak_list)}..{max(leak_list)}"
    )
    if leak_kinds:
        print(f"  leaks by kind: {leak_kinds}")


if __name__ == "__main__":
    main(20)
