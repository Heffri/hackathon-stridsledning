"""HGV impact test (M-TIER1.5 Subtask B, Issue #10).

Verifies the new constant-glide-path HGV default: HGV spawned via the
normal Red AI path should reach ground near its pre-selected target
with a CEP comparable to ballistic.

Spawns N HGVs one at a time via `RedAI._spawn_point(HGV, ...)` +
`red_ai._pick_target`. No Blue AI. Runs each to death or 600 s.
Measures ground-impact fraction, horizontal miss at death, and
physics sanity (no NaN, no runaway altitude oscillation).

PASS criteria:
  * ground-impact fraction >= 0.80
  * median horizontal_miss <= 2500 m
  * no physics explosions (NaN, |alt| oscillation > 5 km)
"""
from __future__ import annotations

from math import hypot, isnan

import numpy as np

from sim import config, red_ai
from sim.red_ai import RedAI
from sim.types import ThreatType
from sim.world import World


_N_TRIALS = 30
_SIM_CAP_S = 600.0
_DT = 0.05


def _target_site_name(x: float, y: float) -> str:
    from sim import sites
    best = "?"
    best_d = 1e18
    for s in sites.SOUTH_SITES:
        dx = x - s.pos[0]
        dy = y - s.pos[1]
        d = dx * dx + dy * dy
        if d < best_d:
            best_d = d
            best = s.name
    return best


def _run_one_trial(trial_idx: int) -> dict:
    world = World()
    red = RedAI([])

    base_x = config.BLUE_BASE_POS[0]
    base_y = config.BLUE_BASE_POS[1]
    spawn = red._spawn_point(ThreatType.HGV, base_x, base_y)
    target_xy = red_ai._pick_target(red.rng)
    tid = world.spawn_threat(ThreatType.HGV, spawn, target_xy)
    thr = world.threats[tid]

    pre_target = (float(thr.waypoint[0]), float(thr.waypoint[1]))
    spawn_xyz = (float(spawn[0]), float(spawn[1]), float(spawn[2]))

    alt_trace: list[float] = []
    nan_detected = False

    max_ticks = int(_SIM_CAP_S / _DT) + 10
    impact_xy = None
    impact_z = None
    leak_site_name = None
    final_alive = True
    for _ in range(max_ticks):
        world.step(_DT)
        for ev in world.events:
            if ev.get("type") == "leak" and ev.get("threat") == tid:
                leak_site_name = ev.get("site")
        if thr.state.alive:
            z = float(thr.state.pos[2])
            if isnan(z) or isnan(float(thr.state.pos[0])) or isnan(float(thr.state.pos[1])):
                nan_detected = True
                break
            alt_trace.append(z)
        else:
            impact_xy = (float(thr.state.pos[0]), float(thr.state.pos[1]))
            impact_z = float(thr.state.pos[2])
            final_alive = False
            break

    if nan_detected:
        return {
            "trial": trial_idx,
            "spawn": spawn_xyz,
            "target": pre_target,
            "impact": None,
            "impact_z": None,
            "miss": None,
            "alive_at_end": False,
            "nan": True,
            "t_end": float(world.t),
            "leak_site": None,
            "alt_oscillation": None,
        }

    if impact_xy is None:
        miss = None
        impact_xy = (float(thr.state.pos[0]), float(thr.state.pos[1]))
        impact_z = float(thr.state.pos[2])
    else:
        miss = hypot(impact_xy[0] - pre_target[0], impact_xy[1] - pre_target[1])

    # Altitude oscillation: peak-to-peak within mid-flight slice (exclude
    # the very first 10 samples and the last 10 samples, which include
    # spawn transient and terminal dive).
    alt_arr = np.array(alt_trace)
    if alt_arr.size >= 40:
        mid = alt_arr[10:-10]
        # Detrend: subtract the linear best-fit so we measure oscillation,
        # not monotonic descent.
        idx = np.arange(mid.size)
        a, b = np.polyfit(idx, mid, 1)
        residual = mid - (a * idx + b)
        alt_osc = float(residual.max() - residual.min())
    else:
        alt_osc = 0.0

    return {
        "trial": trial_idx,
        "spawn": spawn_xyz,
        "target": pre_target,
        "impact": impact_xy,
        "impact_z": impact_z,
        "miss": miss,
        "alive_at_end": final_alive,
        "nan": False,
        "t_end": float(world.t),
        "leak_site": leak_site_name,
        "alt_oscillation": alt_osc,
    }


def main() -> None:
    results = []
    for i in range(_N_TRIALS):
        r = _run_one_trial(i)
        results.append(r)
        miss_s = f"{r['miss']:7.1f}" if r["miss"] is not None else "   n/a "
        z_s = f"{r['impact_z']:6.0f}" if r["impact_z"] is not None else "  n/a "
        osc_s = f"{r['alt_oscillation']:7.0f}" if r["alt_oscillation"] is not None else "  n/a"
        tag = "NAN" if r["nan"] else (f"leak@{r['leak_site']}" if r["leak_site"] else "ground")
        print(
            f"  trial {i:2d}: target=({r['target'][0]:8.0f},{r['target'][1]:8.0f}) "
            f"impact_z={z_s} "
            f"miss={miss_s} m  "
            f"osc={osc_s} m  "
            f"t_end={r['t_end']:5.1f}  "
            f"{tag}"
        )

    n_spawned = len(results)
    n_nan = sum(1 for r in results if r["nan"])
    n_impacted = sum(1 for r in results if not r["alive_at_end"] and not r["nan"])
    n_alive = sum(1 for r in results if r["alive_at_end"] and not r["nan"])
    misses = np.array([r["miss"] for r in results if r["miss"] is not None])
    oscs = np.array(
        [r["alt_oscillation"] for r in results if r["alt_oscillation"] is not None]
    )

    impact_fraction = n_impacted / n_spawned if n_spawned else 0.0

    print()
    print(
        f"N spawned={n_spawned}  "
        f"ground-impacted={n_impacted}  "
        f"still-alive-at-{_SIM_CAP_S:.0f}s={n_alive}  "
        f"nan={n_nan}"
    )
    print(f"ground-impact fraction={impact_fraction:.2f}")
    if misses.size:
        print(
            f"horizontal_miss (m): "
            f"mean={misses.mean():7.1f}  "
            f"median={np.median(misses):7.1f}  "
            f"p95={np.percentile(misses, 95):7.1f}  "
            f"max={misses.max():7.1f}"
        )
    if oscs.size:
        print(
            f"altitude oscillation (m, detrended, mid-flight p-p): "
            f"mean={oscs.mean():7.0f}  max={oscs.max():7.0f}"
        )

    # Per-target-site breakdown
    by_site: dict[str, list[float]] = {}
    for r in results:
        if r["miss"] is None:
            continue
        name = _target_site_name(r["target"][0], r["target"][1])
        by_site.setdefault(name, []).append(r["miss"])
    if by_site:
        print()
        print("Per-target-site breakdown:")
        for name, ms in sorted(by_site.items()):
            arr = np.array(ms)
            print(
                f"  {name:22s}: n={len(ms):2d}  "
                f"mean={arr.mean():7.1f}  "
                f"median={np.median(arr):7.1f}  "
                f"max={arr.max():7.1f}"
            )

    # Verdict
    pass_impact = impact_fraction >= 0.80
    pass_cep = misses.size > 0 and float(np.median(misses)) <= 2500.0
    pass_nan = n_nan == 0
    pass_osc = oscs.size == 0 or float(oscs.max()) <= 5000.0
    print()
    print(
        f"Verdict: "
        f"impact={'PASS' if pass_impact else 'FAIL'} "
        f"(fraction {impact_fraction:.2f} vs >=0.80)   "
        f"cep={'PASS' if pass_cep else 'FAIL'} "
        f"(median {np.median(misses) if misses.size else 'n/a'} m vs <=2500)   "
        f"nan={'PASS' if pass_nan else 'FAIL'}   "
        f"osc={'PASS' if pass_osc else 'FAIL'}"
    )
    overall = pass_impact and pass_cep and pass_nan and pass_osc
    print(f"Overall: {'PASS' if overall else 'FAIL'}")


if __name__ == "__main__":
    main()
