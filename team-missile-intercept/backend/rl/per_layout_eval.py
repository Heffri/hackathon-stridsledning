"""Per-layout eval — does a learned Blue policy generalize across layouts?

Runs a fixed trained Blue (MaskablePPO) against one or more Red variants
("scripted" ScriptedRedAI, "rule" rule-based RedAI) across one or more
Blue layout slots. Each (layout, red) cell runs N deterministic seeds.
Produces a JSON + Markdown summary.

CLI:
    python rl/per_layout_eval.py \\
        --blue rl/runs/blue_local/blue_aoe_long/model.zip \\
        --red scripted rule \\
        --layouts C D current \\
        --matches 50 \\
        --output blue_aoe_long_final_eval

Outputs go to `<output>.json` and `<output>.md` in the CWD.

The model is evaluated by composing a `MissileInterceptEnv` per match
with the sampled layout override, then stepping policy.predict at the
agent's decision cadence. Sim cap = 3000s per match (matching training
episode length).
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import List, Optional

import numpy as np

from rl.env import MAX_LAUNCHERS, MAX_THREATS, MissileInterceptEnv


def _load_layouts(layouts_json_path: str) -> dict:
    """Slot letter → roster dict-of-list-of-tuple. 'current' maps to None."""
    data = json.loads(Path(layouts_json_path).read_text())
    out: dict = {"current": None}
    for entry in data.get("layouts", []):
        slot = str(entry.get("slot", "")).upper()
        roster = entry.get("roster", {})
        out[slot] = {
            kind: [tuple(pos) for pos in positions]
            for kind, positions in roster.items()
        }
    return out


def _make_env(
    seed: int,
    episode_time_limit: float,
    layout_override: Optional[dict],
    red_mode: str,
    blue_budget: int,
    red_budget: int,
):
    pool = None
    if layout_override is not None:
        pool = [{"slot": "fixed", "roster": layout_override}]
    env = MissileInterceptEnv(
        seed=seed,
        episode_time_limit=episode_time_limit,
        layouts_pool=pool,
        red_mode=red_mode,
        blue_budget_start=blue_budget,
        red_budget_start=red_budget,
    )
    return env


def _run_match(
    model,
    env: MissileInterceptEnv,
    seed: int,
) -> dict:
    obs, _ = env.reset(seed=seed)
    total_reward = 0.0
    steps = 0
    while True:
        mask = np.asarray(obs["action_mask"]).reshape(-1).astype(np.int8)
        action, _ = model.predict(obs, action_masks=mask, deterministic=True)
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += float(reward)
        steps += 1
        if terminated or truncated:
            break
    # Derive outcome from final world state
    import sim.sites as sites_module
    military = [s for s in sites_module.SOUTH_SITES
                if s.subtype in ("base", "air_base")]
    site_hp = sum(s.hp for s in military)
    site_hp_max = sum(s.hp_max for s in military) or 1
    sites_alive = sum(1 for s in military if s.hp > 0)
    sites_total = len(military)
    leaked = env.world.leaked
    intercepts = env.world.intercepts
    all_dead = military and all(s.hp <= 0 for s in military)
    red_done = env.red.done or env.world.red_budget <= 0
    no_threats = all(not t.state.alive for t in env.world.threats.values())
    if all_dead:
        winner = "red"
    elif red_done and no_threats:
        winner = "blue"
    else:
        winner = "truncated"
    return {
        "winner": winner,
        "sim_t": float(env.world.t),
        "site_hp_frac": site_hp / site_hp_max,
        "sites_alive": sites_alive,
        "sites_total": sites_total,
        "leaked": int(leaked),
        "intercepts": int(intercepts),
        "blue_budget_remaining": int(env.world.blue_budget),
        "red_budget_remaining": int(env.world.red_budget),
        "steps": steps,
        "total_reward": total_reward,
    }


def _summarise(results: List[dict]) -> dict:
    n = len(results)
    wins = sum(1 for r in results if r["winner"] == "blue")
    losses = sum(1 for r in results if r["winner"] == "red")
    truncs = sum(1 for r in results if r["winner"] == "truncated")
    return {
        "n": n,
        "blue_wins": wins,
        "red_wins": losses,
        "truncated": truncs,
        "blue_winrate": wins / n if n else 0.0,
        "mean_site_hp_frac": statistics.mean(r["site_hp_frac"] for r in results),
        "mean_sites_alive": statistics.mean(r["sites_alive"] for r in results),
        "mean_leaked": statistics.mean(r["leaked"] for r in results),
        "mean_intercepts": statistics.mean(r["intercepts"] for r in results),
        "mean_blue_budget_remaining": statistics.mean(
            r["blue_budget_remaining"] for r in results
        ),
        "mean_sim_t": statistics.mean(r["sim_t"] for r in results),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blue", required=True,
                    help="path to Blue model.zip")
    ap.add_argument("--red", nargs="+", default=["scripted"],
                    choices=["scripted", "default", "rule"],
                    help="which Red variants to eval against")
    ap.add_argument("--layouts", nargs="+", default=["current"],
                    help="layout slot letters or 'current'")
    ap.add_argument("--matches", type=int, default=50)
    ap.add_argument("--layouts-json", default="rl/top3_layouts_CD.json")
    ap.add_argument("--episode-time-limit", type=float, default=3000.0)
    ap.add_argument("--base-seed", type=int, default=1000)
    ap.add_argument("--blue-budget", type=int, default=200_000_000)
    ap.add_argument("--red-budget", type=int, default=150_000_000)
    ap.add_argument("--output", default="per_layout_eval")
    args = ap.parse_args()

    # 'rule' is an alias for 'default'
    red_variants = ["default" if r == "rule" else r for r in args.red]
    # Dedupe preserving order
    seen = set()
    red_variants = [r for r in red_variants if not (r in seen or seen.add(r))]

    layouts_dict = _load_layouts(args.layouts_json)
    # Slot letters uppercase unless 'current'
    requested = [L if L.lower() == "current" else L.upper() for L in args.layouts]
    missing = [L for L in requested if L not in layouts_dict]
    if missing:
        print(f"[per_layout_eval] unknown layout slot(s): {missing}. "
              f"Available: {sorted(layouts_dict.keys())}", file=sys.stderr)
        sys.exit(2)

    # Load model
    from sb3_contrib import MaskablePPO
    print(f"[per_layout_eval] loading Blue: {args.blue}", flush=True)
    model = MaskablePPO.load(args.blue, device="auto")

    all_cells = {}
    t0 = time.time()
    for red in red_variants:
        for layout in requested:
            key = f"{layout}_vs_{red}"
            print(f"[per_layout_eval] running {key} x {args.matches}",
                  flush=True)
            override = layouts_dict[layout]
            per_match = []
            for i in range(args.matches):
                seed = args.base_seed + i
                env = _make_env(
                    seed=seed,
                    episode_time_limit=args.episode_time_limit,
                    layout_override=override,
                    red_mode=red,
                    blue_budget=args.blue_budget,
                    red_budget=args.red_budget,
                )
                res = _run_match(model, env, seed)
                res["seed"] = seed
                per_match.append(res)
                print(
                    f"  [{i+1:3d}/{args.matches}] seed={seed} "
                    f"winner={res['winner']:9s} sites={res['sites_alive']}/"
                    f"{res['sites_total']} leak={res['leaked']} "
                    f"int={res['intercepts']} t={res['sim_t']:.0f}s",
                    flush=True,
                )
            summary = _summarise(per_match)
            all_cells[key] = {
                "red": red,
                "layout": layout,
                "summary": summary,
                "per_match": per_match,
            }

    wall = time.time() - t0
    payload = {
        "meta": {
            "blue_model": args.blue,
            "matches_per_cell": args.matches,
            "layouts": requested,
            "reds": red_variants,
            "blue_budget": args.blue_budget,
            "red_budget": args.red_budget,
            "episode_time_limit": args.episode_time_limit,
            "wall_seconds": round(wall, 1),
        },
        "cells": all_cells,
    }

    out_json = Path(args.output + ".json")
    out_json.write_text(json.dumps(payload, indent=2))
    print(f"[per_layout_eval] wrote {out_json}", flush=True)

    # Markdown summary
    lines = []
    lines.append(f"# Per-Layout Eval — {args.blue}")
    lines.append("")
    lines.append(f"Matches per cell: {args.matches}  |  episode cap: "
                 f"{args.episode_time_limit:.0f}s")
    lines.append(f"Blue budget: {args.blue_budget:,}  |  "
                 f"Red budget: {args.red_budget:,}")
    lines.append(f"Wall: {wall/60:.1f} min")
    lines.append("")
    lines.append("| Layout | Red | Blue Win% | Mean Site HP% | Mean Sites Alive | Mean Leaks | Mean Intercepts | Mean $B left |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|")
    for key, cell in all_cells.items():
        s = cell["summary"]
        lines.append(
            f"| {cell['layout']} | {cell['red']} | "
            f"{s['blue_winrate']*100:5.1f} | "
            f"{s['mean_site_hp_frac']*100:5.1f} | "
            f"{s['mean_sites_alive']:.2f} | "
            f"{s['mean_leaked']:.1f} | "
            f"{s['mean_intercepts']:.1f} | "
            f"{s['mean_blue_budget_remaining']/1e6:.1f}M |"
        )
    out_md = Path(args.output + ".md")
    out_md.write_text("\n".join(lines) + "\n")
    print(f"[per_layout_eval] wrote {out_md}", flush=True)


if __name__ == "__main__":
    main()
