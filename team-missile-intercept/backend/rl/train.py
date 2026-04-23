"""MaskablePPO training entry — Blue-side agent vs rule-based Red.

Usage:
  py -3 -m rl.train --total-steps 1_000_000 --n-envs 8
  py -3 -m rl.train --device cuda --n-envs 8 --total-steps 10_000_000

Outputs:
  rl/runs/<timestamp>/model.zip      — SB3-loadable policy
  rl/runs/<timestamp>/vecnormalize.pkl (if vecnormalize used)
  rl/runs/<timestamp>/tb/             — tensorboard logs

Design notes:
  * MaskablePPO (sb3-contrib) honors the per-sub-action legal-action
    mask produced by the env. Invalid fire actions never get sampled,
    so the policy's logits for invalid slots don't affect training.
  * SubprocVecEnv = OS-process-per-env. Default 8 workers saturates
    ~8 cores at ~10000 aggregate tick/s (matches earlier benchmark).
  * GPU handles batched network forward/backward; sim stays CPU.
  * MultiInputPolicy uses SB3's CombinedExtractor by default — each
    dict sub-space is flattened + concat'd into one MLP input. For
    MVP we accept this (attention-based extractor is a later upgrade).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker
from stable_baselines3.common.callbacks import CheckpointCallback, EvalCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import SubprocVecEnv, VecMonitor

from rl.env import MAX_LAUNCHERS, MAX_THREATS, MissileInterceptEnv


def _load_layouts_pool(path: str) -> list:
    """Load and validate a top3_layouts-shaped JSON file. Exits with
    code 2 on any structural problem — we want loud failure, not a
    silent fallback to the default layout.
    """
    try:
        data = json.loads(Path(path).read_text())
    except Exception as exc:
        print(f"[layouts-pool] failed to read {path}: {exc}", file=sys.stderr)
        sys.exit(2)
    layouts = data.get("layouts")
    if not isinstance(layouts, list) or not layouts:
        print(f"[layouts-pool] {path}: 'layouts' must be a non-empty list",
              file=sys.stderr)
        sys.exit(2)
    for i, entry in enumerate(layouts):
        if not isinstance(entry, dict) or not isinstance(entry.get("roster"), dict):
            print(f"[layouts-pool] {path}: layout[{i}] missing 'roster' dict",
                  file=sys.stderr)
            sys.exit(2)
    return layouts


def _filter_layouts_pool(pool: list, slot_whitelist: list) -> list:
    """If `slot_whitelist` is non-empty, keep only entries whose `slot`
    field matches. Empty whitelist means no filter. Exits with code 2
    if the filter drops everything.
    """
    if not slot_whitelist:
        return pool
    wl = {s.upper() for s in slot_whitelist}
    filtered = [L for L in pool if str(L.get("slot", "")).upper() in wl]
    if not filtered:
        slots = sorted({str(L.get("slot", "?")) for L in pool})
        print(f"[layouts-pool] filter {sorted(wl)} matched nothing "
              f"(available: {slots})", file=sys.stderr)
        sys.exit(2)
    return filtered


def mask_fn(env: MissileInterceptEnv) -> np.ndarray:
    """Extract per-sub-action legal masks from the env's latest obs.

    MaskablePPO expects a flat concatenated array for MultiDiscrete
    action spaces of length sum(nvec) — here MAX_LAUNCHERS *
    (MAX_THREATS + 1). The mask is the same `action_mask` field we
    pack into the observation; we flatten it row-major so the agent's
    nvec ordering matches.
    """
    # env may be wrapped (Monitor / ActionMasker); unwrap to base.
    base = env
    while hasattr(base, "env") and not isinstance(base, MissileInterceptEnv):
        base = base.env
    # Rebuild mask from current world state (stale obs risk after step).
    threats = base._alive_threats()
    launchers = base.fleet.launchers[:MAX_LAUNCHERS]
    mask2d = base._build_action_mask(threats, launchers)
    return mask2d.reshape(-1).astype(np.int8)


def make_env(
    seed: int,
    episode_time_limit: float,
    layouts_pool=None,
    red_mode: str = "default",
    blue_budget_start=None,
    red_budget_start=None,
):
    def _init():
        env = MissileInterceptEnv(
            seed=seed,
            episode_time_limit=episode_time_limit,
            layouts_pool=layouts_pool,
            red_mode=red_mode,
            blue_budget_start=blue_budget_start,
            red_budget_start=red_budget_start,
        )
        env = Monitor(env)  # standard SB3 per-episode stats
        env = ActionMasker(env, mask_fn)
        return env
    return _init


def build_vec_env(
    n_envs: int,
    episode_time_limit: float,
    base_seed: int = 0,
    layouts_pool=None,
    red_mode: str = "default",
    blue_budget_start=None,
    red_budget_start=None,
):
    fns = [
        make_env(
            base_seed + i,
            episode_time_limit,
            layouts_pool=layouts_pool,
            red_mode=red_mode,
            blue_budget_start=blue_budget_start,
            red_budget_start=red_budget_start,
        )
        for i in range(n_envs)
    ]
    vec = SubprocVecEnv(fns, start_method="spawn")
    vec = VecMonitor(vec)
    return vec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--total-steps", type=int, default=1_000_000)
    ap.add_argument("--n-envs", type=int, default=8)
    ap.add_argument("--episode-time-limit", type=float, default=600.0)
    ap.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    ap.add_argument("--n-steps", type=int, default=512,
                    help="per-env rollout length before PPO update")
    ap.add_argument("--batch-size", type=int, default=512)
    ap.add_argument("--n-epochs", type=int, default=8)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--gamma", type=float, default=0.995)
    ap.add_argument("--gae-lambda", type=float, default=0.95)
    ap.add_argument("--ent-coef", type=float, default=0.01)
    ap.add_argument("--clip-range", type=float, default=0.2)
    ap.add_argument("--save-every", type=int, default=100_000,
                    help="(alias for --checkpoint-every)")
    ap.add_argument("--checkpoint-every", type=int, default=None)
    ap.add_argument("--run-name", default=None)
    ap.add_argument("--warmstart", default=None,
                    help="path to prior model.zip to continue from")
    ap.add_argument("--red-mode", default="default",
                    choices=["default", "scripted"],
                    help="'scripted' swaps rule-RedAI for ScriptedRedAI")
    ap.add_argument("--blue-budget", type=int, default=None,
                    help="override config.BLUE_BUDGET_START for training")
    ap.add_argument("--red-budget", type=int, default=None,
                    help="override config.RED_BUDGET_START for training")
    ap.add_argument("--layouts-pool", default=None,
                    help="path to a top3_layouts-shaped JSON for per-episode "
                         "Blue layout sampling")
    ap.add_argument("--layouts-pool-slots", nargs="*", default=None,
                    help="optional whitelist of slot letters (e.g. C D)")
    args = ap.parse_args()

    # Resolve checkpoint cadence: --checkpoint-every wins if given.
    ckpt_every = args.checkpoint_every if args.checkpoint_every is not None else args.save_every

    # Layouts pool (optional)
    layouts_pool = None
    if args.layouts_pool:
        layouts_pool = _load_layouts_pool(args.layouts_pool)
        layouts_pool = _filter_layouts_pool(layouts_pool, args.layouts_pool_slots or [])
        slots = [L.get("slot", "?") for L in layouts_pool]
        print(f"[layouts-pool] loaded {len(layouts_pool)} layout(s): {slots}")

    ts = time.strftime("%Y%m%d_%H%M%S")
    run_name = args.run_name or ts
    run_dir = Path("rl") / "runs" / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    tb_dir = run_dir / "tb"
    ckpt_dir = run_dir / "ckpt"
    ckpt_dir.mkdir(exist_ok=True)

    vec = build_vec_env(
        args.n_envs,
        args.episode_time_limit,
        layouts_pool=layouts_pool,
        red_mode=args.red_mode,
        blue_budget_start=args.blue_budget,
        red_budget_start=args.red_budget,
    )

    policy_kwargs = dict(
        net_arch=[256, 256],  # both pi and vf
    )

    if args.warmstart:
        warm = Path(args.warmstart)
        if not warm.exists():
            print(f"[warmstart] file not found: {warm} — falling back to "
                  f"fresh init. Report wall-clock penalty at end.", flush=True)
            model = MaskablePPO(
                "MultiInputPolicy",
                vec,
                learning_rate=args.lr,
                n_steps=args.n_steps,
                batch_size=args.batch_size,
                n_epochs=args.n_epochs,
                gamma=args.gamma,
                gae_lambda=args.gae_lambda,
                clip_range=args.clip_range,
                ent_coef=args.ent_coef,
                policy_kwargs=policy_kwargs,
                tensorboard_log=str(tb_dir),
                device=args.device,
                verbose=1,
            )
        else:
            print(f"[warmstart] loading {warm}", flush=True)
            try:
                model = MaskablePPO.load(
                    str(warm),
                    env=vec,
                    device=args.device,
                    tensorboard_log=str(tb_dir),
                )
                print(f"[warmstart] loaded OK", flush=True)
            except Exception as exc:
                print(f"[warmstart] load failed ({exc}) — falling back to "
                      f"fresh init. Report wall-clock penalty at end.",
                      flush=True)
                model = MaskablePPO(
                    "MultiInputPolicy",
                    vec,
                    learning_rate=args.lr,
                    n_steps=args.n_steps,
                    batch_size=args.batch_size,
                    n_epochs=args.n_epochs,
                    gamma=args.gamma,
                    gae_lambda=args.gae_lambda,
                    clip_range=args.clip_range,
                    ent_coef=args.ent_coef,
                    policy_kwargs=policy_kwargs,
                    tensorboard_log=str(tb_dir),
                    device=args.device,
                    verbose=1,
                )
    else:
        model = MaskablePPO(
            "MultiInputPolicy",
            vec,
            learning_rate=args.lr,
            n_steps=args.n_steps,
            batch_size=args.batch_size,
            n_epochs=args.n_epochs,
            gamma=args.gamma,
            gae_lambda=args.gae_lambda,
            clip_range=args.clip_range,
            ent_coef=args.ent_coef,
            policy_kwargs=policy_kwargs,
            tensorboard_log=str(tb_dir),
            device=args.device,
            verbose=1,
        )
    ckpt_cb = CheckpointCallback(
        save_freq=max(ckpt_every // args.n_envs, 1),
        save_path=str(ckpt_dir),
        name_prefix="blue_ppo",
    )

    print(f"=== Training run {run_name} ===")
    print(f"total-steps={args.total_steps:,} n-envs={args.n_envs} device={args.device}")
    print(f"episode-time-limit={args.episode_time_limit}s")
    print(f"writing to {run_dir}")

    t0 = time.time()
    try:
        model.learn(
            total_timesteps=args.total_steps,
            callback=[ckpt_cb],
            tb_log_name="ppo",
            progress_bar=True,
        )
    except KeyboardInterrupt:
        print("Interrupted, saving model...")

    final_path = run_dir / "model.zip"
    model.save(str(final_path))
    vec.close()

    print(f"Done. Trained {args.total_steps:,} steps in {time.time()-t0:.1f}s")
    print(f"Model: {final_path}")


if __name__ == "__main__":
    main()
