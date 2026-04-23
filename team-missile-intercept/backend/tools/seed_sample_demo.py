"""Seed sampler for the 2026-04-25 Hack Day demo.

Runs N headless matches with the locked demo configuration:
  * Red: ScriptedRedAI (3 parallel per-site chains, 3 rounds each)
  * Blue: LearnedBlueAI loading `blue_cd_focused`
  * Layout: Slot C (Chen's 23-launcher roster from
    `game-core/CANDIDATE_LAYOUTS_2026-04-22.json`)
  * Budgets: defaults (Red $100M, Blue $120M)

For each seed records: ep_len_sim_seconds, winner, threats spawned by
kind, total interceptor launches, leaks, per-site damage taken, Red
budget drain fraction. Prints a sorted-by-drama table so the operator
can pick 2-3 seeds for the live demo.

Drama score = min(total_site_damage, 60) - abs(ep_len_sim_s - 120).
Weights a match toward "Red scored a partial hit before Blue closed
it out" (exciting) and against shutouts / cap-fires (boring).

Run from backend/:
  py -3 tools/seed_sample_demo.py --seeds 1000-1014 \
    --model "C:/Users/xingy/Documents/github/hackathon-stridsledning/team-missile-intercept/backend/rl/runs/blue_local/blue_cd_focused/model.zip"
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time
from collections import Counter

import numpy as np

# Locate backend/ as sys.path root so `sim` / `rl` import cleanly
# whether the script is launched from tools/ or backend/.
HERE = pathlib.Path(__file__).resolve().parent
BACKEND = HERE.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sim import config, sites  # noqa: E402


# Slot C roster from game-core/CANDIDATE_LAYOUTS_2026-04-22.json —
# embedded here so this script is self-contained and the demo
# configuration does not depend on the JSON being present.
SLOT_C = {
    "ciws": [
        (78_625, 10_331), (72_303, 8_161), (79_064, 5_394),
        (124_226, 3_170), (127_577, 5_178), (129_062, 1_370),
        (79_567, 78_313), (83_655, 78_446),
    ],
    "rbs_70": [
        (81_757, 98_185), (126_422, 119_517), (38_711, 63_703),
    ],
    "iris_t_sls": [
        (80_492, 84_902), (126_750, 102_093),
        (76_686, 12_972), (128_737, 6_810),
    ],
    "iris_t_slm": [
        (81_612, 94_141), (83_023, 18_841),
        (135_844, 10_732), (38_453, 60_796),
    ],
    "pac_2": [(127_480, 114_527), (39_023, 62_606)],
    "pac_3": [(78_981, 76_401), (111_457, 14_345)],
}


def run_seed(seed: int, blue_policy_path: str, max_sim_s: float = 400.0) -> dict:
    # Monkey-patch config.BLUE_LAUNCHER_POSITIONS BEFORE anything reads
    # it. Scenario.__init__ → BlueAI() builds a fleet from this; then
    # LearnedBlueAI.__init__ builds its own fleet, again from this.
    config.BLUE_LAUNCHER_POSITIONS.clear()
    config.BLUE_LAUNCHER_POSITIONS.update({
        k: [(float(x), float(y)) for (x, y) in v]
        for k, v in SLOT_C.items()
    })

    sites.reset_leaks()

    # Import inside the function so any earlier Scenario build that
    # may have cached the default fleet is invalidated when we build
    # a new one here.
    from sim.red_ai import ScriptedRedAI
    from sim.scenarios import build_default_scenario
    from sim.types import MatchPhase
    from rl.live_ai import LearnedBlueAI

    scn = build_default_scenario(auto_start=False)

    scn.red = ScriptedRedAI(scn)
    scn.red.rng = np.random.default_rng(seed)

    scn.blue = LearnedBlueAI(blue_policy_path, scn)

    scn.world.transition(MatchPhase.RUNNING)

    dt = config.DT
    steps = int(max_sim_s / dt)
    threats_by_kind: Counter = Counter()
    interceptor_launches = 0
    site_initial_hp = {s.id: s.hp for s in sites.SOUTH_SITES if s.subtype in ("base", "air_base")}

    for _ in range(steps):
        scn.step(dt)
        for ev in scn.world.events:
            et = ev.get("type")
            if et == "threat_spawn":
                threats_by_kind[ev.get("kind")] += 1
            elif et == "launch":
                interceptor_launches += 1
        if scn.done:
            break

    site_damage = {
        s.name: site_initial_hp.get(s.id, 0) - s.hp
        for s in sites.SOUTH_SITES
        if s.subtype in ("base", "air_base")
    }
    total_site_damage = sum(site_damage.values())
    sites_dead = sum(1 for s in sites.SOUTH_SITES if s.subtype in ("base", "air_base") and s.hp <= 0)

    red_drain_frac = 1.0 - scn.world.red_budget / max(1, scn.world.red_budget_max)
    blue_drain_frac = 1.0 - scn.world.blue_budget / max(1, scn.world.blue_budget_max)

    return {
        "seed": seed,
        "winner": scn.winner,
        "ep_len_sim_s": round(scn.world.t, 1),
        "threats_by_kind": dict(threats_by_kind),
        "total_threats": sum(threats_by_kind.values()),
        "interceptor_launches": interceptor_launches,
        "leaked": scn.world.leaked,
        "intercepts": scn.world.intercepts,
        "site_damage": site_damage,
        "total_site_damage": total_site_damage,
        "sites_dead": sites_dead,
        "red_drain_frac": round(red_drain_frac, 3),
        "blue_drain_frac": round(blue_drain_frac, 3),
    }


def drama_score(rec: dict) -> float:
    # Best drama for a 4-min demo:
    #   * Red scored SOME damage (partial breach) but didn't wipe us
    #   * Match ended decisively (winner != None) — not a cap-fire
    #   * No more than 1 site destroyed
    # Worst: sites_dead >= 2 (Red runaway), shutout (boring),
    #        winner=None at cap (undecided).
    dmg = rec["total_site_damage"]
    if 0 < dmg <= 60:
        dmg_component = dmg                      # partial breach, dramatic
    elif dmg == 0:
        dmg_component = -20.0                    # shutout, boring
    else:
        dmg_component = max(-60.0, 60 - (dmg - 60))  # >60: one site dying, ok but less
    resolved = 20.0 if rec["winner"] is not None else -30.0
    runaway = -50.0 if rec["sites_dead"] >= 2 else 0.0
    # Mild penalty for matches far off a nominal 1500s (so demo
    # picks don't all skew to 2000s cap-fires).
    duration_penalty = 0.03 * abs(rec["ep_len_sim_s"] - 1500.0)
    return dmg_component + resolved + runaway - duration_penalty


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--seeds", default="1000-1014",
        help="Seed range, e.g. '1000-1014' or '1000,1003,1007'",
    )
    ap.add_argument(
        "--model", required=True,
        help="Absolute path to blue_cd_focused model.zip",
    )
    ap.add_argument(
        "--max-sim-s", type=float, default=400.0,
        help="Safety cap per match in sim seconds (default 400)",
    )
    ap.add_argument(
        "--json-out", default=None,
        help="Optional path to dump raw results as JSON",
    )
    args = ap.parse_args()

    if "-" in args.seeds:
        lo, hi = args.seeds.split("-", 1)
        seeds = list(range(int(lo), int(hi) + 1))
    else:
        seeds = [int(s) for s in args.seeds.split(",")]

    if not os.path.exists(args.model):
        print(f"[ERR] Model not found: {args.model}", file=sys.stderr)
        return 2

    print(f"=== seed_sample_demo: {len(seeds)} seed(s), Slot C + ScriptedRed + blue_cd_focused ===")
    records = []
    t0 = time.time()
    for seed in seeds:
        t_start = time.time()
        rec = run_seed(seed, args.model, max_sim_s=args.max_sim_s)
        rec["wall_s"] = round(time.time() - t_start, 1)
        records.append(rec)
        tb = rec["threats_by_kind"]
        tb_s = " ".join(f"{k[:4]}={v}" for k, v in sorted(tb.items()))
        print(
            f"seed {seed}: winner={str(rec['winner'] or 'none'):5s} "
            f"len={rec['ep_len_sim_s']:5.1f}s "
            f"threats={rec['total_threats']:2d} ({tb_s}) "
            f"fires={rec['interceptor_launches']:3d} "
            f"leaks={rec['leaked']:2d} "
            f"site_dmg={rec['total_site_damage']:3d} "
            f"sites_dead={rec['sites_dead']} "
            f"red_drain={rec['red_drain_frac']:.2f} "
            f"blue_drain={rec['blue_drain_frac']:.2f} "
            f"(wall {rec['wall_s']}s)"
        )

    print(f"\nTotal wall time: {time.time()-t0:.1f}s")

    # Drama ranking
    records_sorted = sorted(records, key=drama_score, reverse=True)
    print("\n=== Ranked by drama score (high to low) ===")
    for rec in records_sorted:
        score = drama_score(rec)
        sd = rec["site_damage"]
        sd_s = " ".join(f"{k[:5]}:{v}" for k, v in sorted(sd.items()))
        print(
            f"seed {rec['seed']}: drama={score:+6.1f} "
            f"len={rec['ep_len_sim_s']:5.1f}s "
            f"dmg=({sd_s}) "
            f"winner={str(rec['winner'] or 'none')}"
        )

    if args.json_out:
        pathlib.Path(args.json_out).write_text(
            json.dumps({"records": records, "ranked_seeds": [r["seed"] for r in records_sorted]}, indent=2)
        )
        print(f"\nJSON dumped to {args.json_out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
