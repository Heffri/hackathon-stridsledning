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
import os
import time
from pathlib import Path

import numpy as np
from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker
from stable_baselines3.common.callbacks import CheckpointCallback, EvalCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import SubprocVecEnv, VecMonitor

from rl.env import MAX_LAUNCHERS, MAX_THREATS, MissileInterceptEnv


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


def make_env(seed: int, episode_time_limit: float):
    def _init():
        env = MissileInterceptEnv(seed=seed, episode_time_limit=episode_time_limit)
        env = Monitor(env)  # standard SB3 per-episode stats
        env = ActionMasker(env, mask_fn)
        return env
    return _init


def build_vec_env(n_envs: int, episode_time_limit: float, base_seed: int = 0):
    fns = [make_env(base_seed + i, episode_time_limit) for i in range(n_envs)]
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
    ap.add_argument("--save-every", type=int, default=100_000)
    ap.add_argument("--run-name", default=None)
    args = ap.parse_args()

    ts = time.strftime("%Y%m%d_%H%M%S")
    run_name = args.run_name or ts
    run_dir = Path("rl") / "runs" / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    tb_dir = run_dir / "tb"
    ckpt_dir = run_dir / "ckpt"
    ckpt_dir.mkdir(exist_ok=True)

    vec = build_vec_env(args.n_envs, args.episode_time_limit)

    policy_kwargs = dict(
        net_arch=[256, 256],  # both pi and vf
    )

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
        save_freq=max(args.save_every // args.n_envs, 1),
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
