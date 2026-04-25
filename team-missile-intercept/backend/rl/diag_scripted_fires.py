"""Diagnostic: rollout model vs scripted config, count fires by launcher
kind + intercepts/leaks by threat kind. Used for Slot-C curriculum
investigation.

Usage:
  py -3 -m rl.diag_scripted_fires --model <path> --slot C --n 10 \
      --chain-count 3 --max-rounds 2 --max-layer ballistic
"""
from __future__ import annotations

import argparse
from collections import Counter

import numpy as np
from sb3_contrib import MaskablePPO

from rl.env import MissileInterceptEnv
from rl.layout_catalog import get_positions, load_catalog


def _run(model, slot_positions, scripted_config, n: int, seed_base: int):
    fires_by_kind = Counter()
    intercepts_by_threat = Counter()
    leaks_by_kind = Counter()
    wins = losses = draws = 0
    rews = []
    hps = []
    for i in range(n):
        seed = seed_base + i
        env = MissileInterceptEnv(
            red_mode="scripted",
            episode_time_limit=3000,
            scripted_config=scripted_config,
            blue_positions=slot_positions,
            seed=seed,
        )
        obs, _ = env.reset(seed=seed)
        total = 0.0
        # Track launcher kinds. Fleet persists; index-based kind lookup.
        launcher_kinds = [lch.kind.value for lch in env.fleet.launchers]
        while True:
            b = {k: np.expand_dims(v, 0) for k, v in obs.items()}
            m = obs["action_mask"].reshape(-1).astype(np.int8)
            a, _ = model.predict(b, action_masks=m, deterministic=True)
            a = np.asarray(a).reshape(-1).astype(np.int64)
            # Tally fire per launcher kind BEFORE step — action[l]<MAX_THREATS
            # means fire launcher l.
            from rl.env import MAX_THREATS
            for l_idx, act in enumerate(a):
                if l_idx >= len(launcher_kinds):
                    break
                if act < MAX_THREATS:
                    fires_by_kind[launcher_kinds[l_idx]] += 1
            obs, r, term, trunc, info = env.step(a)
            total += r
            # Track intercepts / leaks from events.
            for ev in info.get("events", []):
                et = ev.get("type")
                tid = ev.get("threat")
                if et == "intercept" and tid is not None:
                    t = env.world.threats.get(tid)
                    if t is not None:
                        intercepts_by_threat[t.state.kind] += 1
                elif et == "leak":
                    k = ev.get("kind")
                    if k is not None:
                        leaks_by_kind[k] += 1
            if term or trunc:
                break
        w = info.get("winner")
        wins += w == "blue"
        losses += w == "red"
        draws += w is None
        rews.append(total)
        hps.append(info.get("site_hp_total", 0))
    return {
        "wins": wins, "losses": losses, "draws": draws,
        "reward_mean": float(np.mean(rews)),
        "hp_mean": float(np.mean(hps)),
        "fires_by_kind": dict(fires_by_kind),
        "intercepts_by_threat": dict(intercepts_by_threat),
        "leaks_by_kind": dict(leaks_by_kind),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--catalog", default="rl/layouts/CANDIDATE_LAYOUTS_2026-04-22.json")
    ap.add_argument("--slot", required=True)
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--seed-base", type=int, default=5000)
    ap.add_argument("--chain-count", type=int, default=3)
    ap.add_argument("--max-rounds", type=int, default=3)
    ap.add_argument("--max-layer", default="hgv")
    args = ap.parse_args()

    cat = load_catalog(args.catalog)
    pos = get_positions(cat, args.slot)
    model = MaskablePPO.load(args.model, device="cpu")
    sc = {
        "chain_count": args.chain_count,
        "max_rounds": args.max_rounds,
        "max_layer": args.max_layer,
    }
    print(
        f"=== {args.model} | slot={args.slot} | scripted={sc} | n={args.n} ==="
    )
    r = _run(model, pos, sc, args.n, args.seed_base)
    print(
        f"W={r['wins']}/{args.n} L={r['losses']} D={r['draws']} "
        f"reward={r['reward_mean']:+.1f} hp={r['hp_mean']:.0f}"
    )
    print(f"fires_by_launcher_kind: {r['fires_by_kind']}")
    print(f"intercepts_by_threat_kind: {r['intercepts_by_threat']}")
    print(f"leaks_by_threat_kind: {r['leaks_by_kind']}")


if __name__ == "__main__":
    main()
