"""Demo-realistic eval: B model + LearnedBlueAI (with Path C strategic
fallback) vs ScriptedRedAI. Mirrors what server.py does — gives us
demo-accurate site survival numbers, NOT the per_layout_eval pure-policy
numbers.

Usage:
    PYTHONPATH=. python eval_demo_b_pathc.py <model_path> <layout_slot> [matches]

Layout slot: C, D, or current (uses default config positions).
"""
import sys
import json
from collections import defaultdict
from pathlib import Path

# Setup
MODEL_PATH = sys.argv[1] if len(sys.argv) > 1 else "rl/runs/blue_local/blue_aoe_aggressive_B_shaped/model.zip"
LAYOUT_SLOT = sys.argv[2] if len(sys.argv) > 2 else "C"
N_MATCHES = int(sys.argv[3]) if len(sys.argv) > 3 else 3
EPISODE_TIME = float(sys.argv[4]) if len(sys.argv) > 4 else 2000.0

import os
os.environ["BLUE_POLICY_PATH"] = MODEL_PATH

from sim.scenarios import build_default_scenario
from sim.config import DT, BLUE_BUDGET_START, RED_BUDGET_START
from sim import sites as sites_module
from sim import config as config_module
from sim.launcher import LauncherFleet
from sim.red_ai import ScriptedRedAI
from sim.types import InterceptorType
from rl.live_ai import LearnedBlueAI

# Load layouts pool
layouts_path = Path("rl/top3_layouts_CD.json")
with open(layouts_path) as f:
    pool_data = json.load(f)
layouts_dict = {L["slot"]: L["roster"] for L in pool_data["layouts"]}


def _build_fleet_for_layout(slot: str) -> LauncherFleet:
    if slot == "current":
        return LauncherFleet()  # uses config.BLUE_LAUNCHER_POSITIONS
    roster = layouts_dict[slot]
    return LauncherFleet(positions=roster)


def run_one_match(seed: int) -> dict:
    """Run one match with B model + LearnedBlueAI + ScriptedRedAI."""
    sites_module.reset_leaks()
    scn = build_default_scenario(auto_start=True)
    # Override budget
    scn.world.blue_budget = 200_000_000
    scn.world.blue_budget_max = 200_000_000
    scn.world.red_budget = 150_000_000
    scn.world.red_budget_max = 150_000_000
    # Swap in LearnedBlueAI (Path C inclusive) + ScriptedRedAI
    scn.blue = LearnedBlueAI(MODEL_PATH, scn)
    # CRITICAL: must update BOTH self.launchers AND _env._own_blue_fleet
    # since the latter is the obs-encoder-side reference that doesn't auto-
    # follow self.launchers reassignment.
    new_fleet = _build_fleet_for_layout(LAYOUT_SLOT)
    scn.blue.launchers = new_fleet
    scn.blue._env._own_blue_fleet = new_fleet
    scn.red = ScriptedRedAI(scn)
    # Debug counters
    fallback_fires = []
    log_seen = 0

    # Per-kind fire counter
    fire_counts = defaultdict(int)

    n_steps = int(EPISODE_TIME / DT)
    last_inter_count = 0
    seen_inter_ids = set()
    for i in range(n_steps):
        scn.step(DT)
        # Track new interceptors (count first appearance per kind)
        for iid, inter in scn.world.interceptors.items():
            if iid not in seen_inter_ids:
                seen_inter_ids.add(iid)
                fire_counts[inter.spec.kind.value] += 1
        # Track strategic_fallback log lines from Blue
        for line in scn.blue.log[log_seen:]:
            if "strategic_fallback" in line:
                fallback_fires.append((scn.world.t, line))
        log_seen = len(scn.blue.log)
        # Early termination: all military sites dead OR no red threats and red done
        military = [s for s in sites_module.SOUTH_SITES if s.subtype in ("base", "air_base")]
        all_dead = military and all(s.hp <= 0 for s in military)
        red_done = scn.red.done or scn.world.red_budget <= 0
        no_threats = all(not t.state.alive for t in scn.world.threats.values())
        if all_dead:
            break
        if red_done and no_threats and i > 100:
            break

    military = [s for s in sites_module.SOUTH_SITES if s.subtype in ("base", "air_base")]
    sites_alive = sum(1 for s in military if s.hp > 0)
    sites_hp_pct = sum(s.hp for s in military) / max(1, sum(s.hp_max for s in military))
    leaked = scn.world.leaked
    intercepts = scn.world.intercepts
    all_dead = military and all(s.hp <= 0 for s in military)
    red_done = scn.red.done or scn.world.red_budget <= 0
    no_threats = all(not t.state.alive for t in scn.world.threats.values())
    if all_dead:
        winner = "red"
    elif red_done and no_threats:
        winner = "blue"
    else:
        winner = "truncated"
    # Count ballistic+HGV that actually spawned (sanity check)
    spawn_counts = {"ballistic": 0, "hgv": 0}
    for ev in scn.world.events:
        pass  # events are flushed
    # Use sites_module leak counts as proxy: for each leak event we don't have
    # access to history. Just count current threats by kind for live ones.
    # Better: track ScriptedRed batches.
    sr_batches = sum(len(c.batches) for c in scn.red._chains) if hasattr(scn.red, '_chains') else 0
    return {
        "seed": seed,
        "sim_t": float(scn.world.t),
        "winner": winner,
        "sites_alive": sites_alive,
        "sites_total": len(military),
        "site_hp_pct": sites_hp_pct,
        "leaked": leaked,
        "intercepts": intercepts,
        "fire_counts": dict(fire_counts),
        "blue_budget_left": int(scn.world.blue_budget),
        "red_budget_left": int(scn.world.red_budget),
        "fallback_fires_total": len(fallback_fires),
        "fallback_fires_first_t": fallback_fires[0][0] if fallback_fires else None,
        "scripted_red_batches": sr_batches,
    }


def main():
    print(f"=== Demo-realistic eval ===")
    print(f"Model: {MODEL_PATH}")
    print(f"Layout: {LAYOUT_SLOT} | Matches: {N_MATCHES} | Episode cap: {EPISODE_TIME}s")
    print(f"Blue 200M / Red 150M (full Hack Day pressure)")
    print(f"Wrapper: LearnedBlueAI with Path C strategic_fallback")
    print()
    results = []
    for i in range(N_MATCHES):
        seed = 1000 + i
        r = run_one_match(seed)
        print(f"  [{i+1}/{N_MATCHES}] seed={seed} winner={r['winner']:9s} "
              f"sites={r['sites_alive']}/{r['sites_total']} "
              f"hp={r['site_hp_pct']*100:5.1f}% "
              f"leak={r['leaked']:2d} int={r['intercepts']:3d} "
              f"t={r['sim_t']:.0f}s")
        # show fire breakdown
        fc = r["fire_counts"]
        print(f"      fires: ciws={fc.get('ciws',0)} rbs_70={fc.get('rbs_70',0)} "
              f"sls={fc.get('iris_t_sls',0)} slm={fc.get('iris_t_slm',0)} "
              f"pac2={fc.get('pac_2',0)} pac3={fc.get('pac_3',0)}")
        print(f"      fallback={r['fallback_fires_total']} (first @ t={r['fallback_fires_first_t']})  "
              f"sr_batches={r['scripted_red_batches']}")
        results.append(r)

    print()
    print("=== Summary ===")
    n = len(results)
    avg_sites = sum(r["sites_alive"] for r in results) / n
    avg_hp = sum(r["site_hp_pct"] for r in results) / n
    avg_leak = sum(r["leaked"] for r in results) / n
    avg_int = sum(r["intercepts"] for r in results) / n
    blue_wins = sum(1 for r in results if r["winner"] == "blue")
    print(f"Avg sites alive: {avg_sites:.2f}/{results[0]['sites_total']}")
    print(f"Avg HP%: {avg_hp*100:.1f}%")
    print(f"Avg leaks: {avg_leak:.1f}")
    print(f"Avg intercepts: {avg_int:.1f}")
    print(f"Blue wins: {blue_wins}/{n}")
    # Aggregate fire counts
    total_fires = defaultdict(int)
    for r in results:
        for k, v in r["fire_counts"].items():
            total_fires[k] += v
    print(f"Total fires across all matches:")
    print(f"  CIWS: {total_fires.get('ciws',0)}  RBS-70: {total_fires.get('rbs_70',0)}  "
          f"SLS: {total_fires.get('iris_t_sls',0)}  SLM: {total_fires.get('iris_t_slm',0)}  "
          f"PAC-2: {total_fires.get('pac_2',0)}  PAC-3: {total_fires.get('pac_3',0)}")


if __name__ == "__main__":
    main()
