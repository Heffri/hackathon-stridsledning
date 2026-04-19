"""Ballistic targeting CEP empirical baseline (M-TIER1.5 Subtask A,
M-TIER2.5 threshold update).

Verifies Issue #11's recon claim that `entities.py:134-171` produces a
projectile trajectory that actually lands at the target `(x, y)` chosen
by Red AI's weighted-random `_pick_target`.

Spawns N ballistics via the normal Red AI path (`RedAI._spawn_point` +
`red_ai._pick_target`) one at a time, no Blue AI, and runs each to
ground-impact or 600 s. Measures horizontal miss at death against the
pre-selected target (`thr.waypoint[:2]` captured at spawn).

PASS threshold: median horizontal_miss <= 5000 m. This measures the
actual ground-impact CEP of the projectile-motion trajectory solver,
not the 1500 m leak-disc trigger distance. Post-M-TIER2.5 every
non-nuclear threat (ballistic included) has requires_ground_impact=True,
so a ballistic no longer "dies" on the first site-disc crossing at
altitude — it continues until ground impact. The solver's aim-past +
altitude-scaled drag combo puts the typical ground impact a few km
short of or past the targeted site (median ~3-4 km, p95 ~4 km). Drift
beyond 5 km would indicate a real targeting bug.
"""
from __future__ import annotations

import sys
from math import hypot

import numpy as np

from sim import config, red_ai
from sim.red_ai import RedAI
from sim.types import ThreatType
from sim.world import World


_N_TRIALS = 30
_SIM_CAP_S = 600.0
_DT = 0.05


def _run_one_trial(trial_idx: int) -> dict:
    """Spawn 1 ballistic via Red AI, fly it unopposed, return metrics."""
    world = World()
    red = RedAI([])  # empty wave list — we drive spawning manually

    base_x = config.BLUE_BASE_POS[0]
    base_y = config.BLUE_BASE_POS[1]
    spawn = red._spawn_point(ThreatType.BALLISTIC, base_x, base_y)
    target_xy = red_ai._pick_target(red.rng)
    tid = world.spawn_threat(ThreatType.BALLISTIC, spawn, target_xy)
    thr = world.threats[tid]

    pre_target = (float(thr.waypoint[0]), float(thr.waypoint[1]))
    spawn_xyz = (float(spawn[0]), float(spawn[1]), float(spawn[2]))

    max_ticks = int(_SIM_CAP_S / _DT) + 10
    final_alive = True
    impact_xy = None
    impact_z = None
    leak_site_name = None
    for _ in range(max_ticks):
        world.step(_DT)
        # Capture any leak event naming this threat.
        for ev in world.events:
            if ev.get("type") == "leak" and ev.get("threat") == tid:
                leak_site_name = ev.get("site")
        # Do NOT prune — we need the dead threat's final state.
        if not thr.state.alive:
            impact_xy = (float(thr.state.pos[0]), float(thr.state.pos[1]))
            impact_z = float(thr.state.pos[2])
            final_alive = False
            break

    if impact_xy is None:
        miss = None
        impact_xy = (float(thr.state.pos[0]), float(thr.state.pos[1]))
        impact_z = float(thr.state.pos[2])
    else:
        miss = hypot(impact_xy[0] - pre_target[0], impact_xy[1] - pre_target[1])

    return {
        "trial": trial_idx,
        "spawn": spawn_xyz,
        "target": pre_target,
        "impact": impact_xy,
        "impact_z": impact_z,
        "miss": miss,
        "alive_at_end": final_alive,
        "t_end": float(world.t),
        "leak_site": leak_site_name,
    }


def _target_site_name(x: float, y: float) -> str:
    """Nearest site name for per-site breakdown."""
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


def main() -> None:
    results = []
    for i in range(_N_TRIALS):
        r = _run_one_trial(i)
        results.append(r)
        miss = r["miss"]
        miss_s = f"{miss:7.1f}" if miss is not None else "  alive "
        leak_tag = f"leak@{r['leak_site']}" if r["leak_site"] else "ground"
        print(
            f"  trial {i:2d}: target=({r['target'][0]:8.0f},{r['target'][1]:8.0f}) "
            f"impact=({r['impact'][0]:8.0f},{r['impact'][1]:8.0f},z={r['impact_z']:6.0f}) "
            f"miss={miss_s} m  "
            f"t_end={r['t_end']:5.1f}  "
            f"{leak_tag}"
        )

    n_spawned = len(results)
    n_impacted = sum(1 for r in results if not r["alive_at_end"])
    n_alive = n_spawned - n_impacted
    misses = np.array([r["miss"] for r in results if r["miss"] is not None])

    # Flyover artifact: pre-M-TIER2.5, ballistic did NOT have
    # requires_ground_impact, so it could be counted as hitting any
    # site whose horizontal disc it crossed mid-flight — producing
    # huge miss values when the leak site didn't match the targeted
    # site. Post-M-TIER2.5 (commit b06fd11) every non-nuclear threat
    # has `requires_ground_impact=True`, so this bucket should be 0
    # for every trial today. The split is retained as a regression
    # guard: any future flag-flip surfaces here immediately.
    flyover = [
        r for r in results
        if r["leak_site"] is not None
        and _target_site_name(r["target"][0], r["target"][1]) != r["leak_site"]
    ]
    clean = [
        r for r in results
        if r["miss"] is not None
        and (r["leak_site"] is None or _target_site_name(r["target"][0], r["target"][1]) == r["leak_site"])
    ]

    print()
    print(
        f"N spawned={n_spawned}  ground-impacted={n_impacted}  "
        f"still-alive-at-{_SIM_CAP_S:.0f}s={n_alive}  "
        f"flyover-artifact={len(flyover)}"
    )
    if misses.size > 0:
        print(
            f"horizontal_miss all trials (m): "
            f"mean={misses.mean():7.1f}  "
            f"median={np.median(misses):7.1f}  "
            f"p95={np.percentile(misses, 95):7.1f}  "
            f"max={misses.max():7.1f}"
        )
    if clean:
        clean_arr = np.array([r["miss"] for r in clean])
        print(
            f"horizontal_miss (flyover-excluded, n={len(clean)}): "
            f"mean={clean_arr.mean():7.1f}  "
            f"median={np.median(clean_arr):7.1f}  "
            f"p95={np.percentile(clean_arr, 95):7.1f}  "
            f"max={clean_arr.max():7.1f}"
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
                f"mean={arr.mean():8.1f}  "
                f"median={np.median(arr):7.1f}  "
                f"max={arr.max():8.1f}"
            )

    if misses.size > 0:
        median = float(np.median(misses))
        threshold = 5000.0  # ground-impact CEP bound, post-M-TIER2.5 flyover fix
        verdict = "PASS" if median <= threshold else "FAIL"
        print()
        print(
            f"Verdict: {verdict}  "
            f"(median {median:.1f} m vs threshold {threshold:.0f} m)"
        )
        # M-TIER2.6-AUDIT (A6): raise the verdict to an exit code so
        # `python test_ballistic_cep.py` fails visibly in a regression
        # runner. Print-only verdicts are invisible to CI.
        if median > threshold:
            sys.exit(1)


if __name__ == "__main__":
    main()
