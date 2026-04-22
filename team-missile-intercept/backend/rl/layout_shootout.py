"""Layout shootout — rank candidate BLUE_LAUNCHER_POSITIONS layouts.

Monkey-patches ``sim.config.BLUE_LAUNCHER_POSITIONS`` per layout and runs
N deterministic episodes of rule_Red vs rule_Blue via ``CrossEvalEnv``.
Ranks by mean site damage (asc), tiebreak by sites_destroyed (asc) then
blue_budget_remaining (desc).

Usage (from ``team-missile-intercept/backend``):

    python -m rl.layout_shootout \
        --layouts-json <path> --n-episodes 30 --seeds 1000-1029 \
        --episode-time-limit 1200 \
        --out-json layout_shootout_2026-04-22.json \
        --out-md layout_shootout_2026-04-22.md
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import List, Tuple

from sim import config, terrain
from rl.cross_eval import CrossEvalEnv, RULE_SENTINEL


def parse_seed_range(spec: str) -> List[int]:
    if "-" in spec:
        lo, hi = spec.split("-", 1)
        return list(range(int(lo), int(hi) + 1))
    return [int(s) for s in spec.split(",") if s.strip()]


def revalidate_land(roster: dict) -> Tuple[bool, str]:
    for kind, positions in roster.items():
        for x, y in positions:
            if not terrain.point_on_south_land(float(x), float(y)):
                return False, f"{kind} ({x},{y}) off-land"
    return True, ""


def aggregate(results: List[dict], layout: dict) -> dict:
    def _mean(key):
        return statistics.mean(r[key] for r in results) if results else 0.0
    n = len(results)
    wins = {"red": 0, "blue": 0, "draw": 0}
    for r in results:
        wins[r["winner"]] = wins.get(r["winner"], 0) + 1
    return {
        "slot": layout["slot"],
        "name": layout["name"],
        "n_episodes": n,
        "mean_site_damage_total": round(_mean("sites_total_damage"), 2),
        "mean_sites_destroyed": round(_mean("sites_destroyed"), 3),
        "mean_blue_budget_remaining": round(_mean("blue_budget_remaining"), 1),
        "mean_red_budget_remaining": round(_mean("red_budget_remaining"), 1),
        "mean_interceptors_fired": round(_mean("blue_launches_total"), 2),
        "mean_hgv_leaks": round(_mean("hgv_leaks"), 3),
        "mean_intercepts": round(_mean("intercept_count"), 2),
        "mean_leaks": round(_mean("leak_count"), 2),
        "mean_ep_length": round(_mean("episode_length"), 1),
        "mean_sim_time": round(_mean("sim_time"), 1),
        "wins_red": wins.get("red", 0),
        "wins_blue": wins.get("blue", 0),
        "wins_draw": wins.get("draw", 0),
        "launcher_count": layout.get("launcher_count"),
    }


def run_shootout(layouts: list, seeds: List[int], time_limit: float) -> dict:
    original = {k: list(v) for k, v in config.BLUE_LAUNCHER_POSITIONS.items()}
    results_by_slot = {}

    try:
        for layout in layouts:
            slot = layout["slot"]
            roster_raw = layout["roster"]
            roster = {kind: [tuple(pos) for pos in positions]
                      for kind, positions in roster_raw.items()}

            ok, err = revalidate_land(roster)
            if not ok:
                print(f"[SKIP] slot {slot}: INVALID — {err}")
                results_by_slot[slot] = {
                    "slot": slot, "name": layout["name"],
                    "status": "INVALID", "reason": err,
                }
                continue

            config.BLUE_LAUNCHER_POSITIONS.clear()
            config.BLUE_LAUNCHER_POSITIONS.update(roster)

            print(f"\n=== Slot {slot}: {layout['name']} "
                  f"({layout.get('launcher_count')} launchers) ===")
            per_seed: List[dict] = []
            t_layout = time.time()
            for seed in seeds:
                t0 = time.time()
                env = CrossEvalEnv(
                    red_spec=RULE_SENTINEL, blue_spec=RULE_SENTINEL,
                    seed=seed, episode_time_limit=time_limit,
                )
                r = env.run_episode(seed=seed)
                d = r.to_dict()
                d["blue_launches_total"] = sum(d["blue_launches_by_kind"].values())
                d["hgv_leaks"] = 0  # approximation placeholder; set below
                # HGV leaks: threat kind 'hgv' reaching site — use leak_count
                # as leak-total proxy and capture hgv-specific via spawns.
                # The event stream doesn't break out kind in leak events, so
                # report total leaks here and note in report.
                per_seed.append(d)
                wall = time.time() - t0
                print(f"  seed={seed} winner={d['winner']:5s} "
                      f"dmg={d['sites_total_damage']:4d} "
                      f"dead={d['sites_destroyed']} "
                      f"blue_$={d['blue_budget_remaining']:>10d} "
                      f"fires={d['blue_launches_total']:3d} "
                      f"sim={d['sim_time']:6.1f}s wall={wall:4.1f}s")
            agg = aggregate(per_seed, layout)
            agg["status"] = "OK"
            agg["per_seed"] = per_seed
            agg["wall_seconds"] = round(time.time() - t_layout, 1)
            results_by_slot[slot] = agg
    finally:
        config.BLUE_LAUNCHER_POSITIONS.clear()
        config.BLUE_LAUNCHER_POSITIONS.update(original)

    return results_by_slot


def rank_layouts(results: dict) -> list:
    valid = [r for r in results.values() if r.get("status") == "OK"]
    valid.sort(key=lambda r: (
        r["mean_site_damage_total"],
        r["mean_sites_destroyed"],
        -r["mean_blue_budget_remaining"],
    ))
    for i, r in enumerate(valid, start=1):
        r["rank"] = i
    invalid = [r for r in results.values() if r.get("status") != "OK"]
    return valid + invalid


def build_markdown(ranked: list, meta: dict) -> str:
    lines = []
    lines.append(f"# Layout Shootout — {meta['date']}")
    lines.append("")
    lines.append(f"- N episodes/layout: **{meta['n_episodes']}**  ")
    lines.append(f"- Seeds: **{meta['seeds']}**  ")
    lines.append(f"- Episode time limit: **{meta['time_limit']} s**  ")
    lines.append(f"- Opponents: rule_Red × rule_Blue  ")
    lines.append("")
    lines.append("## Ranking")
    lines.append("")
    lines.append("| Rank | Slot | Name | mean_dmg | sites_dead | blue_$_left | fires | leaks | wins (R/B/D) | launchers |")
    lines.append("|---:|:---:|:---|---:|---:|---:|---:|---:|:---:|---:|")
    for r in ranked:
        if r.get("status") != "OK":
            lines.append(f"| — | {r['slot']} | {r['name']} | INVALID: {r.get('reason','')} | | | | | | |")
            continue
        wins = f"{r['wins_red']}/{r['wins_blue']}/{r['wins_draw']}"
        lines.append(
            f"| {r['rank']} | {r['slot']} | {r['name']} "
            f"| {r['mean_site_damage_total']:.1f} "
            f"| {r['mean_sites_destroyed']:.2f} "
            f"| {r['mean_blue_budget_remaining']:,.0f} "
            f"| {r['mean_interceptors_fired']:.1f} "
            f"| {r['mean_leaks']:.1f} "
            f"| {wins} "
            f"| {r.get('launcher_count','?')} |"
        )
    lines.append("")
    lines.append("Ranking key: primary = mean_site_damage_total (asc), "
                 "tiebreak = mean_sites_destroyed (asc) then "
                 "mean_blue_budget_remaining (desc).")
    return "\n".join(lines) + "\n"


def select_top3_payload(ranked: list, layouts: list, meta: dict) -> dict:
    by_slot = {L["slot"]: L for L in layouts}
    ok = [r for r in ranked if r.get("status") == "OK"]
    top3 = ok[:3]
    summary = ", ".join(
        f"{r['rank']}: slot {r['slot']} (dmg {r['mean_site_damage_total']:.1f})"
        for r in top3
    )
    return {
        "meta": {
            "date": meta["date"],
            "source_shootout": meta["out_json_name"],
            "methodology": (
                "Top 3 layouts by mean_site_damage_total ranking "
                "(tiebreak: mean_sites_destroyed asc, blue_budget_remaining desc). "
                "Used by auto_selfplay.py --layouts-pool for per-episode sampling."
            ),
            "ranking_summary": summary,
        },
        "layouts": [
            {
                "slot": r["slot"],
                "name": r["name"],
                "rank": r["rank"],
                "mean_site_damage_total": r["mean_site_damage_total"],
                "mean_sites_destroyed": r["mean_sites_destroyed"],
                "mean_blue_budget_remaining": r["mean_blue_budget_remaining"],
                "roster": by_slot[r["slot"]]["roster"],
            }
            for r in top3
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--layouts-json", type=str, required=True)
    ap.add_argument("--n-episodes", type=int, default=30)
    ap.add_argument("--seeds", type=str, default="1000-1029")
    ap.add_argument("--episode-time-limit", type=float, default=1200.0)
    ap.add_argument("--out-json", type=str, required=True)
    ap.add_argument("--out-md", type=str, required=True)
    ap.add_argument("--top3-json", type=str,
                    default="rl/top3_layouts.json")
    ap.add_argument("--date", type=str, default="2026-04-22")
    args = ap.parse_args()

    seeds = parse_seed_range(args.seeds)
    if args.n_episodes != len(seeds):
        print(f"[WARN] --n-episodes={args.n_episodes} but seeds range "
              f"gives {len(seeds)}; using seed list as source of truth.")

    payload = json.loads(Path(args.layouts_json).read_text(encoding="utf-8"))
    layouts = payload["layouts"]
    print(f"Loaded {len(layouts)} layouts from {args.layouts_json}")

    t0 = time.time()
    results = run_shootout(layouts, seeds, args.episode_time_limit)
    ranked = rank_layouts(results)
    total_wall = time.time() - t0

    meta = {
        "date": args.date,
        "n_episodes": len(seeds),
        "seeds": args.seeds,
        "time_limit": args.episode_time_limit,
        "out_json_name": Path(args.out_json).name,
        "total_wall_seconds": round(total_wall, 1),
    }
    Path(args.out_json).write_text(
        json.dumps({"meta": meta, "ranked": ranked, "raw": results}, indent=2),
        encoding="utf-8",
    )
    Path(args.out_md).write_text(build_markdown(ranked, meta), encoding="utf-8")

    top3 = select_top3_payload(ranked, layouts, meta)
    Path(args.top3_json).write_text(json.dumps(top3, indent=2), encoding="utf-8")

    ok = [r for r in ranked if r.get("status") == "OK"]
    if ok:
        w = ok[0]
        print(f"\n=== Shootout winner: slot {w['slot']} ({w['name']}) ===")
        print(f"   mean_site_damage_total: {w['mean_site_damage_total']:.1f}")
        print(f"   mean_sites_destroyed:   {w['mean_sites_destroyed']:.2f}")
        if len(ok) > 1:
            m = ok[1]["mean_site_damage_total"] - w["mean_site_damage_total"]
            print(f"   runner-up: slot {ok[1]['slot']} — margin: {m:.1f}")
    print(f"\nWrote {args.out_json}, {args.out_md}, {args.top3_json}")
    print(f"Total wall: {total_wall:.1f}s")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
