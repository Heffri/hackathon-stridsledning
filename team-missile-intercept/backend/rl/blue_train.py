"""MaskablePPO training entry — Blue-side agent vs learned or rule Red.

Usage (Phase 4a self-play, Blue_3 vs learned Red2):
  py -3 -m rl.blue_train --red-opponent rl/runs/red_20260421_234425/model.zip \
      --timesteps 1_000_000 --output-dir rl/runs/blue_local/blue_3

Usage (warmstart from Blue2, vs learned Red2):
  py -3 -m rl.blue_train --red-opponent rl/runs/red_20260421_234425/model.zip \
      --warmstart rl/models/blue_ai_1m_2xpenalty/model.zip \
      --timesteps 1_000_000 --output-dir rl/runs/blue_local/blue_4

Outputs:
  <output-dir>/model.zip   — SB3-loadable policy
  <output-dir>/ckpt/       — CheckpointCallback snapshots
  <output-dir>/tb/         — tensorboard logs

Mirror of `rl.red_train` for the Blue side of self-play:
  * BlueSelfPlayEnv replaces MissileInterceptEnv, adding an optional
    learned Red opponent that spawns threats via policy.predict at the
    top of each decision step. When `--red-opponent` is unset the env
    falls back to rule RedAI (equivalent to `rl.train`).
  * CLI adds `--red-opponent` (learned Red model.zip) and `--warmstart`
    (resume from a prior Blue model.zip).
  * `--output-dir` allows Chen to pin the run directory (e.g.
    `rl/runs/blue_local/blue_3`) instead of the auto-timestamp used by
    `rl.train`. Directory is created if missing.
  * gamma default 0.9995 matches red_train.py's choice: at
    DECISION_EVERY=10 and episode_time_limit=600s the episode is ~1200
    decisions long, and the longer horizon is needed for the terminal
    reward (+/-100 on Blue's side) to shape early-episode fire choices.
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

from rl.blue_env import BlueSelfPlayEnv
from rl.env import MAX_LAUNCHERS, MAX_THREATS


def mask_fn(env: BlueSelfPlayEnv) -> np.ndarray:
    """Flatten the 2D Blue action mask for MaskablePPO's sum(nvec) shape.

    Blue's action space is MultiDiscrete([MAX_THREATS+1] * MAX_LAUNCHERS);
    sum(nvec) = MAX_LAUNCHERS * (MAX_THREATS+1). Env may be wrapped
    (Monitor / ActionMasker) — unwrap to the base BlueSelfPlayEnv so we
    can rebuild the mask from the current world state (avoids stale-obs
    risk post-step).
    """
    base = env
    while hasattr(base, "env") and not isinstance(base, BlueSelfPlayEnv):
        base = base.env
    threats = base._alive_threats()
    launchers = base.fleet.launchers[:MAX_LAUNCHERS]
    mask2d = base._build_action_mask(threats, launchers)
    return mask2d.reshape(-1).astype(np.int8)


def make_env(
    seed: int,
    episode_time_limit: float,
    red_policy_path=None,
    red_opponent_pool=None,
    red_opponent_weights=None,
):
    def _init():
        env = BlueSelfPlayEnv(
            red_policy_path=red_policy_path,
            seed=seed,
            episode_time_limit=episode_time_limit,
            red_opponent_pool=red_opponent_pool,
            red_opponent_weights=red_opponent_weights,
        )
        env = Monitor(env)
        env = ActionMasker(env, mask_fn)
        return env
    return _init


def build_vec_env(
    n_envs: int,
    episode_time_limit: float,
    base_seed: int = 0,
    red_policy_path=None,
    red_opponent_pool=None,
    red_opponent_weights=None,
):
    fns = [
        make_env(
            base_seed + i,
            episode_time_limit,
            red_policy_path=red_policy_path,
            red_opponent_pool=red_opponent_pool,
            red_opponent_weights=red_opponent_weights,
        )
        for i in range(n_envs)
    ]
    vec = SubprocVecEnv(fns, start_method="spawn")
    vec = VecMonitor(vec)
    return vec


def _parse_pool_args(pool_str, weights_str):
    """Parse --opponent-pool / --opponent-weights CLI into env kwargs.

    Same semantics as red_train._parse_pool_args — duplicated here so
    blue_train is usable without importing from the Red module.
    """
    if pool_str is None:
        return None, None
    pool = [s.strip() for s in pool_str.split(",") if s.strip()]
    if not pool:
        return None, None
    weights = None
    if weights_str is not None:
        weights = [float(s) for s in weights_str.split(",") if s.strip()]
        if len(weights) != len(pool):
            raise ValueError(
                f"--opponent-weights length ({len(weights)}) must match "
                f"--opponent-pool length ({len(pool)})"
            )
    return pool, weights


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timesteps", type=int, default=1_000_000,
                    help="Total PPO training steps (aggregate across envs)")
    ap.add_argument("--n-envs", type=int, default=8)
    ap.add_argument("--episode-time-limit", type=float, default=600.0)
    ap.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    ap.add_argument("--n-steps", type=int, default=512,
                    help="per-env rollout length before PPO update")
    ap.add_argument("--batch-size", type=int, default=512)
    ap.add_argument("--n-epochs", type=int, default=8)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--gamma", type=float, default=0.9995,
                    help="Discount factor. 0.9995 covers the ~1200-decision "
                         "episode for terminal-reward credit propagation.")
    ap.add_argument("--gae-lambda", type=float, default=0.95)
    ap.add_argument("--ent-coef", type=float, default=0.01)
    ap.add_argument("--clip-range", type=float, default=0.2)
    ap.add_argument("--save-every", type=int, default=100_000)
    ap.add_argument("--output-dir", default="rl/runs/blue_local/blue_3",
                    help="Where to write model.zip / ckpt/ / tb/. Created if missing.")
    ap.add_argument("--warmstart", default=None,
                    help="Path to Blue model.zip to resume training from "
                         "(preserves lr/gamma/etc from saved checkpoint)")
    ap.add_argument("--red-opponent", default=None,
                    help="Path to learned Red model.zip. When unset, rule "
                         "RedAI is used (equivalent to rl.train). Ignored "
                         "if --opponent-pool is set.")
    # Opponent pool for self-play robustness. See red_train.py for the
    # symmetric flag on the Red-training side. The "rule" entry stands
    # for rule-based RedAI; every other entry is a path to a Red
    # model.zip. Weights optional, default uniform.
    ap.add_argument("--opponent-pool", default=None,
                    help="Comma-separated Red opponents: 'rule' or "
                         "model.zip paths. E.g. "
                         "'rule,rl/runs/red_1/model.zip,rl/runs/red_3/model.zip'")
    ap.add_argument("--opponent-weights", default=None,
                    help="Comma-separated per-opponent sampling weights "
                         "(default: uniform). Must match --opponent-pool "
                         "length; auto-normalized to sum=1.")
    args = ap.parse_args()

    opp_pool, opp_weights = _parse_pool_args(args.opponent_pool, args.opponent_weights)

    run_dir = Path(args.output_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    tb_dir = run_dir / "tb"
    ckpt_dir = run_dir / "ckpt"
    ckpt_dir.mkdir(exist_ok=True)

    vec = build_vec_env(
        args.n_envs,
        args.episode_time_limit,
        red_policy_path=args.red_opponent,
        red_opponent_pool=opp_pool,
        red_opponent_weights=opp_weights,
    )

    policy_kwargs = dict(
        net_arch=[256, 256],
    )

    if args.warmstart is not None:
        # MaskablePPO.load re-binds the saved policy to our vec env.
        # Saved hyperparams (lr / gamma / ent_coef / etc.) are preserved
        # — fine-tuning with the same config keeps training momentum.
        # The new tensorboard log directory is wired in, so TB will
        # continue under `<run-dir>/tb/` from step 0 of this phase.
        model = MaskablePPO.load(
            args.warmstart,
            env=vec,
            device=args.device,
            tensorboard_log=str(tb_dir),
        )
        print(f"Warmstarted from {args.warmstart}")
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
        save_freq=max(args.save_every // args.n_envs, 1),
        save_path=str(ckpt_dir),
        name_prefix="blue_ppo",
    )

    print(f"=== Training run (BLUE) ===")
    print(f"timesteps={args.timesteps:,} n-envs={args.n_envs} device={args.device}")
    print(f"episode-time-limit={args.episode_time_limit}s gamma={args.gamma}")
    print(f"warmstart={args.warmstart or '(none, fresh init)'}")
    if opp_pool is not None:
        print(f"opponent-pool={opp_pool}")
        print(f"opponent-weights={list(opp_weights) if opp_weights else '(uniform)'}")
    else:
        print(f"red-opponent={args.red_opponent or '(rule RedAI)'}")
    print(f"writing to {run_dir}")

    t0 = time.time()
    try:
        model.learn(
            total_timesteps=args.timesteps,
            callback=[ckpt_cb],
            tb_log_name="blue_ppo",
            progress_bar=True,
        )
    except KeyboardInterrupt:
        print("Interrupted, saving model...")

    final_path = run_dir / "model.zip"
    model.save(str(final_path))
    vec.close()

    elapsed = time.time() - t0
    print(f"Done. Trained {args.timesteps:,} steps in {elapsed:.1f}s "
          f"({elapsed/60:.1f} min)")
    print(f"Model: {final_path}")


if __name__ == "__main__":
    main()
