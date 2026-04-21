"""MaskablePPO training entry — Red-side agent vs rule-based Blue.

Usage:
  py -3 -m rl.red_train --total-steps 1_000_000 --n-envs 8
  py -3 -m rl.red_train --device cuda --n-envs 8 --total-steps 10_000_000

Outputs:
  rl/runs/red_<timestamp>/model.zip      — SB3-loadable policy
  rl/runs/red_<timestamp>/ckpt/          — CheckpointCallback snapshots
  rl/runs/red_<timestamp>/tb/             — tensorboard logs

Mirror of rl.train for the Red side. Hyperparameters, policy architecture,
vec-env setup are identical so cross-machine eval (Blue policy vs Red
policy) is apples-to-apples. The only real diffs from rl.train are:
  * RedEnv replaces MissileInterceptEnv.
  * Run dir / checkpoint prefix / tb tag use `red_` so Boyu's Blue runs
    and Chen's Red runs don't collide in rl/runs/.
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker
from stable_baselines3.common.callbacks import CheckpointCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import SubprocVecEnv, VecMonitor

from rl.red_env import RedEnv


def mask_fn(env: RedEnv) -> np.ndarray:
    """Extract the flat component-wise marginal mask from the env.

    MaskablePPO expects a flat array of length sum(nvec) — here
    N_RED_KINDS + len(SOUTH_SITES) = 5 + n_sites. RedEnv.action_masks
    rebuilds from the current world state, so it's safe to call
    post-step (no stale-obs risk).

    Env may be wrapped (Monitor / ActionMasker); unwrap to the base
    RedEnv so we call action_masks() directly.
    """
    base = env
    while hasattr(base, "env") and not isinstance(base, RedEnv):
        base = base.env
    return base.action_masks()


def make_env(seed: int, episode_time_limit: float):
    def _init():
        env = RedEnv(seed=seed, episode_time_limit=episode_time_limit)
        env = Monitor(env)
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
    # `red_<ts>` visually distinguishes Red training runs from Boyu's
    # Blue runs (which use bare `<ts>`).
    run_name = args.run_name or f"red_{ts}"
    run_dir = Path("rl") / "runs" / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    tb_dir = run_dir / "tb"
    ckpt_dir = run_dir / "ckpt"
    ckpt_dir.mkdir(exist_ok=True)

    vec = build_vec_env(args.n_envs, args.episode_time_limit)

    policy_kwargs = dict(
        net_arch=[256, 256],
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
        name_prefix="red_ppo",
    )

    print(f"=== Training run {run_name} (RED) ===")
    print(f"total-steps={args.total_steps:,} n-envs={args.n_envs} device={args.device}")
    print(f"episode-time-limit={args.episode_time_limit}s")
    print(f"writing to {run_dir}")

    t0 = time.time()
    try:
        model.learn(
            total_timesteps=args.total_steps,
            callback=[ckpt_cb],
            tb_log_name="red_ppo",
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
