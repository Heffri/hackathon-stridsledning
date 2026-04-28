"""Balance regression baseline (M-TIER1.5 Subtask C).

Runs three controlled headless scenarios and writes a structured JSON
blob. Future workers (RK4 refactor, unified threat-control contract,
Blue AI learned policy, etc.) diff their output against the committed
baseline to confirm no silent balance drift.

Scenarios:
  1. full_match  — default BLUE_LAUNCHER_POSITIONS + default waves +
                    Blue AI on. Per-kind {spawned, intercepted, leaked,
                    ground_impacted, still_alive_at_end}.
  2. no_blue     — same but Blue AI disabled. Measures intrinsic threat
                    effectiveness independent of defense.
  3. per_kind_cep — 30 trials per threat kind (drone, cruise_sub,
                    ballistic, HGV). No Blue. Measures horizontal miss
                    at death vs pre-selected target.

Usage:
    cd backend
    python test_balance_baseline.py            # 1800 s scenario cap
    python test_balance_baseline.py --quick    # 600 s cap (fast check)

Output:
    backend/balance_baseline_2026-04-19.json
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import subprocess
import sys
import time
from math import hypot, isnan
from pathlib import Path

import numpy as np

from sim import config, red_ai, sites
from sim.red_ai import RedAI, build_demo_waves
from sim.scenarios import Scenario, build_default_scenario
from sim.types import MatchPhase, ThreatType
from sim.world import World


_DT = 0.05
_CEP_N_TRIALS = 30
_THREAT_KINDS = [
    ThreatType.DRONE,
    ThreatType.CRUISE_SUB,
    ThreatType.BALLISTIC,
    ThreatType.HGV,
]
# Per-kind simulation caps. Drone cruises at 120 m/s, cruise_sub at
# 260 m/s; both need a longer cap than ballistic / HGV to reach target.
# Drone worst case: spawn at Y~183 km to Firewatch at Y~2.6 km = 180 km,
# 1500 s flight. Cruise_sub worst case: spawn at Y~243 km to Main Base
# at Y~5 km = 238 km = 915 s, with S-pattern waypoints up to ~1.5× so
# ~1400 s. Padded to 2000 s for margin.
_CEP_CAP_BY_KIND = {
    ThreatType.DRONE.value: 2000.0,
    ThreatType.CRUISE_SUB.value: 2000.0,
    ThreatType.BALLISTIC.value: 300.0,
    ThreatType.HGV.value: 200.0,
}


# --- Scenario 1: full match ---

def _run_full_match(sim_cap_s: float) -> dict:
    """Scenario.step until done OR sim_cap_s reached. Returns per-kind
    outcome dict + overall winner / match time. Event stream carries
    `threat_spawn` (with kind), `intercept` (threat id), `leak` (kind),
    and `ground_crash` (kind); we build a spawn-time id->kind map to
    tag intercept events which don't carry the kind directly.

    M-TIER2-PHASE gated `Scenario.step` on `phase == RUNNING`. A fresh
    `Scenario()` lands in SETUP, so without an explicit transition the
    loop below would be a pure no-op (winner=None, sim_t=0). Use
    `build_default_scenario(auto_start=True)` to walk SETUP → RUNNING
    before stepping.
    """
    scn = build_default_scenario(auto_start=True)
    max_ticks = int(sim_cap_s / _DT) + 10
    kind_of_id: dict[int, str] = {}
    intercepted = {k.value: 0 for k in _THREAT_KINDS}
    leaked = {k.value: 0 for k in _THREAT_KINDS}
    ground_impacted = {k.value: 0 for k in _THREAT_KINDS}
    spawned = {k.value: 0 for k in _THREAT_KINDS}
    for _ in range(max_ticks):
        scn.step(_DT)
        for ev in scn.world.events:
            t = ev.get("type")
            if t == "threat_spawn":
                k = ev.get("kind")
                if k in spawned:
                    spawned[k] += 1
                    kind_of_id[int(ev["id"])] = k
            elif t == "intercept":
                k = kind_of_id.get(int(ev.get("threat", -1)))
                if k in intercepted:
                    intercepted[k] += 1
            elif t == "leak":
                k = ev.get("kind")
                if k in leaked:
                    leaked[k] += 1
            elif t == "ground_crash" and "threat" in ev:
                k = ev.get("kind")
                if k in ground_impacted:
                    ground_impacted[k] += 1
        if scn.done:
            break

    # still_alive_at_end = spawned - intercepted - leaked - ground_impacted
    still_alive = {
        k: spawned[k] - intercepted[k] - leaked[k] - ground_impacted[k]
        for k in spawned
    }

    snap = scn.snapshot()
    return {
        "winner": scn.winner,
        "sim_t_end": float(scn.world.t),
        "total_spawned": snap["stats"]["spawned"],
        "total_intercepts": snap["stats"]["intercepts"],
        "total_leaked": snap["stats"]["leaked"],
        "blue_budget_remaining": snap["stats"]["blue_budget"],
        "blue_budget_max": snap["stats"]["blue_budget_max"],
        "site_hp": {s["name"]: s["hp"] for s in snap["sites"]},
        "per_kind": {
            k: {
                "spawned": spawned[k],
                "intercepted": intercepted[k],
                "leaked": leaked[k],
                "ground_impacted": ground_impacted[k],
                "still_alive_at_end": still_alive[k],
            }
            for k in spawned
        },
    }


# --- Scenario 2: no Blue ---

def _run_no_blue(sim_cap_s: float) -> dict:
    """World + RedAI with default waves; no Blue AI. Threats fly
    unopposed until each dies (leak / ground) or cap hits.
    """
    sites.reset_leaks()
    world = World()
    red = RedAI(build_demo_waves())
    max_ticks = int(sim_cap_s / _DT) + 10

    kind_of_id: dict[int, str] = {}
    spawned = {k.value: 0 for k in _THREAT_KINDS}
    leaked = {k.value: 0 for k in _THREAT_KINDS}
    ground_impacted = {k.value: 0 for k in _THREAT_KINDS}
    for _ in range(max_ticks):
        world.events = []
        red.step(world.t, world)
        world.step(_DT)
        for ev in world.events:
            t = ev.get("type")
            if t == "threat_spawn":
                k = ev.get("kind")
                if k in spawned:
                    spawned[k] += 1
                    kind_of_id[int(ev["id"])] = k
            elif t == "leak":
                k = ev.get("kind")
                if k in leaked:
                    leaked[k] += 1
            elif t == "ground_crash" and "threat" in ev:
                k = ev.get("kind")
                if k in ground_impacted:
                    ground_impacted[k] += 1
        world.prune_dead()
        # Done when all waves spawned AND no live threats
        if red.done and all(not t.state.alive for t in world.threats.values()):
            break

    still_alive = {
        k: spawned[k] - leaked[k] - ground_impacted[k]
        for k in spawned
    }
    return {
        "sim_t_end": float(world.t),
        "total_spawned": world.threats_spawned,
        "total_leaked": world.leaked,
        "site_hp": {s.name: s.hp for s in sites.SOUTH_SITES},
        "per_kind": {
            k: {
                "spawned": spawned[k],
                "intercepted": 0,  # no Blue
                "leaked": leaked[k],
                "ground_impacted": ground_impacted[k],
                "still_alive_at_end": still_alive[k],
            }
            for k in spawned
        },
    }


# --- Scenario 3: per-kind CEP ---

def _run_cep_trial(kind: ThreatType, base_x: float, base_y: float) -> dict | None:
    sites.reset_leaks()
    world = World()
    red = RedAI([])
    # Cruise_sub default spawn builder needs intermediate waypoints so
    # the S-pattern drives the threat toward target. Drone / ballistic
    # / HGV use only the direct target.
    spawn = red._spawn_point(kind, base_x, base_y)
    target_xy = red_ai._pick_target(red.rng)
    if kind == ThreatType.CRUISE_SUB:
        wps = red_ai._build_cruise_waypoints(spawn, target_xy, red.rng)
        tid = world.spawn_threat(kind, spawn, target_xy, intermediate_waypoints=wps)
    else:
        tid = world.spawn_threat(kind, spawn, target_xy)
    thr = world.threats[tid]
    pre_target = (float(thr.waypoint[0]), float(thr.waypoint[1]))
    # Advance waypoint queue to the final target for miss measurement —
    # we want miss vs the site, not vs an intermediate S-waypoint.
    # (thr.waypoint will drift through the queue during flight; we want
    # the pre-selected target for metric purposes.)
    final_target_xy = (float(target_xy[0]), float(target_xy[1]))

    cap_s = _CEP_CAP_BY_KIND.get(kind.value, 600.0)
    max_ticks = int(cap_s / _DT) + 10
    for _ in range(max_ticks):
        world.step(_DT)
        if not thr.state.alive:
            ix = float(thr.state.pos[0])
            iy = float(thr.state.pos[1])
            iz = float(thr.state.pos[2])
            if isnan(ix) or isnan(iy) or isnan(iz):
                return None
            miss = hypot(ix - final_target_xy[0], iy - final_target_xy[1])
            return {"miss": miss, "impact_z": iz, "t_end": float(world.t)}
    # Still alive at cap
    return {"miss": None, "impact_z": None, "t_end": float(world.t)}


def _run_cep_scenario() -> dict:
    base_x = config.BLUE_BASE_POS[0]
    base_y = config.BLUE_BASE_POS[1]
    out: dict[str, dict] = {}
    for kind in _THREAT_KINDS:
        trials: list[dict] = []
        for _ in range(_CEP_N_TRIALS):
            r = _run_cep_trial(kind, base_x, base_y)
            if r is not None:
                trials.append(r)
        valid = [t for t in trials if t["miss"] is not None]
        misses = np.array([t["miss"] for t in valid]) if valid else np.array([])
        out[kind.value] = {
            "n_trials": _CEP_N_TRIALS,
            "n_impacted": len(valid),
            "n_alive_at_cap": _CEP_N_TRIALS - len(valid),
            "miss_mean_m": float(misses.mean()) if misses.size else None,
            "miss_median_m": float(np.median(misses)) if misses.size else None,
            "miss_p95_m": float(np.percentile(misses, 95)) if misses.size else None,
            "miss_max_m": float(misses.max()) if misses.size else None,
        }
    return out


# --- Runner ---

def _git_head() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            cwd=Path(__file__).parent,
        ).decode().strip()
    except Exception:
        return "unknown"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="Use 600 s sim cap instead of 1800 s")
    parser.add_argument("--out", default="balance_baseline_2026-04-19.json")
    args = parser.parse_args()

    sim_cap = 600.0 if args.quick else 1800.0
    start = time.time()
    print(f"[1/3] full_match (cap {sim_cap:.0f} s)...")
    full = _run_full_match(sim_cap)
    t1 = time.time() - start
    print(f"  done in {t1:.1f} s  winner={full['winner']}  sim_t={full['sim_t_end']:.1f}")

    print(f"[2/3] no_blue (cap {sim_cap:.0f} s)...")
    t0 = time.time()
    nb = _run_no_blue(sim_cap)
    t2 = time.time() - t0
    print(f"  done in {t2:.1f} s  sim_t={nb['sim_t_end']:.1f}")

    print(f"[3/3] per_kind_cep (30 trials × 4 kinds, 600 s cap each)...")
    t0 = time.time()
    cep = _run_cep_scenario()
    t3 = time.time() - t0
    print(f"  done in {t3:.1f} s")

    blob = {
        "baseline_name": "M-TIER1.5 post ballistic-drag + HGV glide-path fix",
        "git_head": _git_head(),
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "config": {
            "dt": _DT,
            "sim_cap_s": sim_cap,
            "cep_n_trials": _CEP_N_TRIALS,
            "cep_sim_cap_s_by_kind": _CEP_CAP_BY_KIND,
        },
        "wall_clock_s": {
            "full_match": round(t1, 1),
            "no_blue": round(t2, 1),
            "cep": round(t3, 1),
            "total": round(time.time() - start, 1),
        },
        "scenarios": {
            "full_match": full,
            "no_blue": nb,
            "per_kind_cep": cep,
        },
    }

    out_path = Path(args.out)
    out_path.write_text(json.dumps(blob, indent=2))
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
