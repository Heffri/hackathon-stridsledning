"""Headless balance sweep: run the current 5-wave scenario N times and
print the Blue/Red/Draw tally. Used to tune wave timing and ammo loadouts
so Blue doesn't cruise at 100 % win rate.

Milestone I: Win conditions now come straight from `Scenario.winner`
(site HP depletion, Blue budget exhaustion, Red out of threats, or the
3600 s safety cap). The old leak-count heuristic is gone. Each match
runs until `scenario.done` fires, so wall-clock time per match varies —
most end in 150-400 s of sim time.
"""
from sim import config
from sim.scenarios import build_default_scenario


def run_once() -> str:
    scn = build_default_scenario()
    dt = 0.05
    max_ticks = int(config.MAX_SIM_TIME / dt) + 10
    for _ in range(max_ticks):
        scn.step(dt)
        if scn.done:
            break
    return scn.winner or "draw"


def run_once_verbose(trace_leaks=None) -> tuple[str, int, int, int]:
    scn = build_default_scenario()
    dt = 0.05
    max_ticks = int(config.MAX_SIM_TIME / dt) + 10
    for _ in range(max_ticks):
        scn.step(dt)
        if trace_leaks is not None:
            for ev in scn.world.events:
                if ev.get("type") == "leak":
                    trace_leaks.append(
                        (round(scn.world.t, 1), ev.get("kind", "?"))
                    )
        if scn.done:
            break

    snap = scn.snapshot()
    leaked = snap["stats"]["leaked"]
    spawned = snap["stats"]["spawned"]
    intercepts = snap["stats"]["intercepts"]
    return (scn.winner or "draw"), spawned, intercepts, leaked


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
