"""Eval a trained MaskablePPO checkpoint vs rule-based baselines.

Runs N matches per policy (no time-limit truncation), reports:
  * Win rate vs rule-based RedAI
  * Average reward, fires, sim time
  * Leaks by kind

Usage:
  py -3 -m rl.eval --model rl/runs/first_mil/ckpt/blue_ppo_100000_steps.zip --n 20
  py -3 -m rl.eval --model rl/runs/first_mil/model.zip --n 20
"""
from __future__ import annotations

import argparse
import time
from collections import Counter

import numpy as np
from sb3_contrib import MaskablePPO

from rl.env import MAX_LAUNCHERS, MAX_THREATS, MissileInterceptEnv


def random_action(obs, rng):
    mask = obs["action_mask"]
    a = np.zeros(MAX_LAUNCHERS, dtype=np.int64)
    for l in range(MAX_LAUNCHERS):
        legal = np.flatnonzero(mask[l])
        a[l] = rng.choice(legal) if legal.size else MAX_THREATS
    return a


def hold_action(obs):
    return np.full(MAX_LAUNCHERS, MAX_THREATS, dtype=np.int64)


def closest_action(obs):
    mask = obs["action_mask"]
    threats = obs["threats"]
    launchers = obs["launchers"]
    a = np.full(MAX_LAUNCHERS, MAX_THREATS, dtype=np.int64)
    for l in range(MAX_LAUNCHERS):
        legal = np.flatnonzero(mask[l, :MAX_THREATS])
        if legal.size == 0:
            continue
        lx, ly = launchers[l, 0], launchers[l, 1]
        dists = [
            (t, (threats[t, 0] - lx) ** 2 + (threats[t, 1] - ly) ** 2)
            for t in legal
        ]
        a[l] = min(dists, key=lambda pair: pair[1])[0]
    return a


def run_matches(
    policy_fn,
    n_matches,
    time_limit=1200.0,
    base_seed=1000,
    red_mode="demo_fixed",
    difficulty="mixed",
    red_model_path=None,
    red_deterministic=False,
    blue_positions=None,
    scripted_config=None,
    detailed: bool = False,
):
    """Run N matches, collect per-match stats. When `detailed=True`,
    also tally per-launcher-kind fires + per-threat-kind leaks/intercepts
    from the info event stream — matches `rl.diag_scripted_fires` output
    format so `--json-out` dumps include collapse-diagnostic data."""
    from collections import Counter
    results = []
    for i in range(n_matches):
        seed = base_seed + i
        env = MissileInterceptEnv(
            seed=seed,
            episode_time_limit=time_limit,
            red_mode=red_mode,
            difficulty=difficulty,
            red_model_path=red_model_path,
            red_deterministic=red_deterministic,
            blue_positions=blue_positions,
            scripted_config=scripted_config,
        )
        obs, _ = env.reset(seed=seed)
        rng = np.random.default_rng(seed)
        total_r = 0.0
        fires = 0
        fires_by_kind: Counter = Counter()
        intercepts_by_kind: Counter = Counter()
        leaks_by_kind: Counter = Counter()
        while True:
            a = policy_fn(obs, rng)
            obs, r, term, trunc, info = env.step(a)
            total_r += r
            fires += info["n_fires"]
            if detailed:
                for ev in info.get("events", []):
                    et = ev.get("type")
                    k = ev.get("kind")
                    if et == "launch" and k:
                        fires_by_kind[k] += 1
                    elif et == "intercept" and k:
                        intercepts_by_kind[k] += 1
                    elif et == "leak" and k:
                        leaks_by_kind[k] += 1
            if term or trunc:
                break
        entry = {
            "seed": seed,
            "winner": info["winner"],
            "reward": total_r,
            "fires": fires,
            "sim_t": info["sim_t"],
            "site_hp": info["site_hp_total"],
            "budget_left": info["blue_budget"],
        }
        if detailed:
            entry.update({
                "fires_by_kind": dict(fires_by_kind),
                "intercepts_by_kind": dict(intercepts_by_kind),
                "leaks_by_kind": dict(leaks_by_kind),
                "layout_slot": info.get("layout_slot"),
            })
        results.append(entry)
    return results


def summary(label, results):
    n = len(results)
    wins = sum(r["winner"] == "blue" for r in results)
    losses = sum(r["winner"] == "red" for r in results)
    draws = sum(r["winner"] is None for r in results)
    avg_r = np.mean([r["reward"] for r in results])
    avg_fires = np.mean([r["fires"] for r in results])
    avg_sim = np.mean([r["sim_t"] for r in results])
    avg_hp = np.mean([r["site_hp"] for r in results])
    print(
        f"{label:24s} | "
        f"W {wins}/{n} ({100*wins/n:4.0f}%)  "
        f"L {losses}/{n}  D {draws}/{n}  | "
        f"r={avg_r:+7.1f}  fires={avg_fires:5.1f}  "
        f"sim={avg_sim:6.0f}s  hp={avg_hp:5.0f}"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="path to SB3 .zip")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--time-limit", type=float, default=1200.0,
                    help="RL horizon (default 1200s; unified with env)")
    ap.add_argument("--skip-baselines", action="store_true")
    ap.add_argument("--red-mode", default="demo_fixed",
                    choices=["demo_fixed", "training_random", "trained", "scripted"],
                    help="demo_fixed = fixed build_demo_waves() for regression "
                         "comparison (default); training_random = randomised "
                         "waves matching training distribution; trained = "
                         "frozen MaskablePPO Red policy (requires --red-model)")
    ap.add_argument("--difficulty", default="mixed",
                    choices=["easy", "mixed", "hard"],
                    help="difficulty preset when --red-mode training_random")
    ap.add_argument("--red-model", default=None,
                    help="path to Red-side .zip — required with --red-mode=trained")
    ap.add_argument("--red-deterministic", action="store_true",
                    help="sample trained Red actions deterministically")
    ap.add_argument("--blue-layout-json", default=None,
                    help="path to a layout catalog JSON (see rl/layouts/). "
                         "Pair with --blue-layout-slot to select one entry. "
                         "Overrides config.BLUE_LAUNCHER_POSITIONS for this "
                         "eval so baselines + trained policy score against "
                         "the selected tactical layout, not the repo default.")
    ap.add_argument("--blue-layout-slot", default=None,
                    help="slot id in the catalog (e.g. A, B, C). Required "
                         "with --blue-layout-json.")
    # Scripted curriculum knobs (AOE 2026-04-24) — match rl.train CLI so
    # eval can stage against the same curriculum level as training.
    ap.add_argument("--scripted-chain-count", type=int, default=3,
                    choices=[1, 2, 3],
                    help="ScriptedRedAI: chain_count (1..3). Only honored "
                         "when --red-mode=scripted.")
    ap.add_argument("--scripted-max-rounds", type=int, default=3,
                    choices=[1, 2, 3],
                    help="ScriptedRedAI: max_rounds (1..3). Only honored "
                         "when --red-mode=scripted.")
    ap.add_argument("--scripted-max-layer", default="hgv",
                    choices=["drone", "cruise", "ballistic", "hgv"],
                    help="ScriptedRedAI: max_layer. Only honored when "
                         "--red-mode=scripted.")
    ap.add_argument("--json-out", default=None,
                    help="Path to write a JSON dump of per-match "
                         "results (includes fires_by_kind / leaks_by_kind / "
                         "intercepts_by_kind). Post-run plotting consumes "
                         "this. Trained policy runs are always detailed; "
                         "baselines are also included when --json-out set.")
    args = ap.parse_args()

    if args.red_mode == "trained" and not args.red_model:
        ap.error("--red-mode=trained requires --red-model")
    if args.blue_layout_json or args.blue_layout_slot:
        if not (args.blue_layout_json and args.blue_layout_slot):
            ap.error("--blue-layout-json and --blue-layout-slot must be used together")
    blue_positions = None
    blue_layout_name = None
    if args.blue_layout_json:
        from rl.layout_catalog import get_positions, load_catalog
        cat = load_catalog(args.blue_layout_json)
        blue_positions = get_positions(cat, args.blue_layout_slot)
        entry = cat["layouts"][args.blue_layout_slot]
        blue_layout_name = (
            f"{args.blue_layout_slot} ({entry.get('name', '?')})"
        )

    scripted_config = None
    scripted_tag = ""
    if args.red_mode == "scripted":
        scripted_config = {
            "chain_count": args.scripted_chain_count,
            "max_rounds": args.scripted_max_rounds,
            "max_layer": args.scripted_max_layer,
        }
        scripted_tag = (
            f" scripted={args.scripted_chain_count}chain×"
            f"{args.scripted_max_rounds}round×{args.scripted_max_layer}"
        )

    print(
        f"=== Eval {args.n} matches each, time_limit={args.time_limit}s, "
        f"red-mode={args.red_mode} difficulty={args.difficulty}"
        + scripted_tag
        + (f" blue-layout={blue_layout_name}" if blue_layout_name else "")
        + " ==="
    )

    match_kwargs = dict(
        time_limit=args.time_limit,
        red_mode=args.red_mode,
        difficulty=args.difficulty,
        red_model_path=args.red_model,
        red_deterministic=args.red_deterministic,
        blue_positions=blue_positions,
        scripted_config=scripted_config,
    )

    # Baselines first
    if not args.skip_baselines:
        t0 = time.time()
        res_hold = run_matches(lambda o, _: hold_action(o), args.n, **match_kwargs)
        summary("baseline hold", res_hold)
        print(f"  ({time.time()-t0:.1f}s)")

        t0 = time.time()
        res_rand = run_matches(lambda o, r: random_action(o, r), args.n, **match_kwargs)
        summary("baseline random", res_rand)
        print(f"  ({time.time()-t0:.1f}s)")

        t0 = time.time()
        res_close = run_matches(lambda o, _: closest_action(o), args.n, **match_kwargs)
        summary("baseline closest", res_close)
        print(f"  ({time.time()-t0:.1f}s)")

    # Trained policy
    print(f"\nLoading {args.model}...")
    model = MaskablePPO.load(args.model, device="cpu")  # cpu faster for batch=1 inference

    def trained_action(obs, rng):
        # sb3 predict expects batched obs; wrap dict
        batched = {k: np.expand_dims(v, 0) for k, v in obs.items()}
        action_mask = obs["action_mask"].reshape(-1).astype(np.int8)
        a, _ = model.predict(batched, action_masks=action_mask, deterministic=True)
        return np.asarray(a).reshape(-1).astype(np.int64)

    detailed = args.json_out is not None
    t0 = time.time()
    res_trained = run_matches(trained_action, args.n, detailed=detailed, **match_kwargs)
    summary(f"trained (deterministic)", res_trained)
    print(f"  ({time.time()-t0:.1f}s)")

    def trained_stochastic(obs, rng):
        batched = {k: np.expand_dims(v, 0) for k, v in obs.items()}
        action_mask = obs["action_mask"].reshape(-1).astype(np.int8)
        a, _ = model.predict(batched, action_masks=action_mask, deterministic=False)
        return np.asarray(a).reshape(-1).astype(np.int64)

    t0 = time.time()
    res_stoch = run_matches(trained_stochastic, args.n, detailed=detailed, **match_kwargs)
    summary(f"trained (stochastic)", res_stoch)
    print(f"  ({time.time()-t0:.1f}s)")

    if args.json_out:
        import json
        payload = {
            "model": args.model,
            "red_mode": args.red_mode,
            "difficulty": args.difficulty,
            "scripted_config": scripted_config,
            "blue_layout_slot": args.blue_layout_slot,
            "blue_layout_name": blue_layout_name,
            "n_matches": args.n,
            "time_limit": args.time_limit,
            "results": {
                "trained_deterministic": res_trained,
                "trained_stochastic": res_stoch,
            },
        }
        import os
        os.makedirs(os.path.dirname(args.json_out) or ".", exist_ok=True)
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"\n[eval] wrote {args.json_out}")


if __name__ == "__main__":
    main()
