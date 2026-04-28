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


def run_matches(policy_fn, n_matches, time_limit=2500.0, base_seed=1000):
    results = []
    for i in range(n_matches):
        seed = base_seed + i
        env = MissileInterceptEnv(seed=seed, episode_time_limit=time_limit)
        obs, _ = env.reset(seed=seed)
        rng = np.random.default_rng(seed)
        total_r = 0.0
        fires = 0
        while True:
            a = policy_fn(obs, rng)
            obs, r, term, trunc, info = env.step(a)
            total_r += r
            fires += info["n_fires"]
            if term or trunc:
                break
        results.append({
            "seed": seed,
            "winner": info["winner"],
            "reward": total_r,
            "fires": fires,
            "sim_t": info["sim_t"],
            "site_hp": info["site_hp_total"],
            "budget_left": info["blue_budget"],
        })
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
    ap.add_argument("--time-limit", type=float, default=2500.0)
    ap.add_argument("--skip-baselines", action="store_true")
    args = ap.parse_args()

    print(f"=== Eval {args.n} matches each, time_limit={args.time_limit}s ===")

    # Baselines first
    if not args.skip_baselines:
        t0 = time.time()
        res_hold = run_matches(lambda o, _: hold_action(o), args.n)
        summary("baseline hold", res_hold)
        print(f"  ({time.time()-t0:.1f}s)")

        t0 = time.time()
        res_rand = run_matches(lambda o, r: random_action(o, r), args.n)
        summary("baseline random", res_rand)
        print(f"  ({time.time()-t0:.1f}s)")

        t0 = time.time()
        res_close = run_matches(lambda o, _: closest_action(o), args.n)
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

    t0 = time.time()
    res_trained = run_matches(trained_action, args.n)
    summary(f"trained (deterministic)", res_trained)
    print(f"  ({time.time()-t0:.1f}s)")

    def trained_stochastic(obs, rng):
        batched = {k: np.expand_dims(v, 0) for k, v in obs.items()}
        action_mask = obs["action_mask"].reshape(-1).astype(np.int8)
        a, _ = model.predict(batched, action_masks=action_mask, deterministic=False)
        return np.asarray(a).reshape(-1).astype(np.int64)

    t0 = time.time()
    res_stoch = run_matches(trained_stochastic, args.n)
    summary(f"trained (stochastic)", res_stoch)
    print(f"  ({time.time()-t0:.1f}s)")


if __name__ == "__main__":
    main()
