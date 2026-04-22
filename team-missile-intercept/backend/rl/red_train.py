"""MaskablePPO training entry — Red-side agent vs rule-based Blue.

Usage:
  py -3 -m rl.red_train --total-steps 1_000_000 --n-envs 8
  py -3 -m rl.red_train --device cuda --n-envs 8 --total-steps 10_000_000

Outputs:
  rl/runs/red_<timestamp>/model.zip      — SB3-loadable policy
  rl/runs/red_<timestamp>/ckpt/          — CheckpointCallback snapshots
  rl/runs/red_<timestamp>/tb/             — tensorboard logs

Mirror of rl.train for the Red side. Policy architecture and vec-env
setup are identical; diffs from rl.train:
  * RedEnv replaces MissileInterceptEnv.
  * Run dir / checkpoint prefix / tb tag use `red_` so Boyu's Blue runs
    and Chen's Red runs don't collide in rl/runs/.
  * gamma default 0.9995 (vs Blue's 0.995). At DECISION_EVERY=10 and
    episode_time_limit=600s the episode is ~1200 decisions long; the
    longer discount horizon is needed for the +/-20 terminal reward to
    shape early-episode spawn choices. CLI `--gamma` overrides.
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


def make_env(
    seed: int,
    episode_time_limit: float,
    blue_policy_path=None,
    blue_opponent_pool=None,
    blue_opponent_weights=None,
):
    def _init():
        env = RedEnv(
            seed=seed,
            episode_time_limit=episode_time_limit,
            blue_policy_path=blue_policy_path,
            blue_opponent_pool=blue_opponent_pool,
            blue_opponent_weights=blue_opponent_weights,
        )
        env = Monitor(env)
        env = ActionMasker(env, mask_fn)
        return env
    return _init


def build_vec_env(
    n_envs: int,
    episode_time_limit: float,
    base_seed: int = 0,
    blue_policy_path=None,
    blue_opponent_pool=None,
    blue_opponent_weights=None,
):
    fns = [
        make_env(
            base_seed + i,
            episode_time_limit,
            blue_policy_path=blue_policy_path,
            blue_opponent_pool=blue_opponent_pool,
            blue_opponent_weights=blue_opponent_weights,
        )
        for i in range(n_envs)
    ]
    vec = SubprocVecEnv(fns, start_method="spawn")
    vec = VecMonitor(vec)
    return vec


def _parse_pool_args(pool_str, weights_str):
    """Parse --opponent-pool / --opponent-weights CLI into env kwargs.

    `--opponent-pool "rule,path1,path2"` splits on commas; whitespace
    around entries is trimmed and empties dropped. The "rule" sentinel
    is propagated verbatim — RedEnv translates it to None (rule BlueAI).
    Returns (pool_list, weights_list) or (None, None) if pool is unset.
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
    ap.add_argument("--total-steps", type=int, default=1_000_000)
    ap.add_argument("--n-envs", type=int, default=8)
    ap.add_argument("--episode-time-limit", type=float, default=600.0)
    ap.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    ap.add_argument("--n-steps", type=int, default=512,
                    help="per-env rollout length before PPO update")
    ap.add_argument("--batch-size", type=int, default=512)
    ap.add_argument("--n-epochs", type=int, default=8)
    ap.add_argument("--lr", type=float, default=3e-4)
    # gamma default lifted 0.995 -> 0.9995 per external-ML-review. At
    # DECISION_EVERY=10 ticks (0.5s sim per decision) and a 600s
    # episode_time_limit, an episode is ~1200 decisions long. Boyu's
    # 0.995 default gives a credit horizon of ~200 decisions (~100s
    # sim) — effectively zero propagation of the +/-20 terminal reward
    # back to early-episode decisions. 0.9995 extends the horizon to
    # ~2000 decisions (covers the full episode) so terminal reward
    # shapes early spawn choices. CLI flag still overrides.
    ap.add_argument("--gamma", type=float, default=0.9995)
    ap.add_argument("--gae-lambda", type=float, default=0.95)
    ap.add_argument("--ent-coef", type=float, default=0.01)
    ap.add_argument("--clip-range", type=float, default=0.2)
    ap.add_argument("--save-every", type=int, default=100_000)
    ap.add_argument("--run-name", default=None)
    # Warmstart: load weights + hyperparameters from an existing run
    # instead of fresh-init. Used for iterative training (e.g. Phase 2b:
    # Red1 → Red2 vs learned Blue). Learning rate, entropy, gamma, etc.
    # are preserved from the saved model unless overridden by env=vec.
    ap.add_argument("--warmstart", default=None,
                    help="Path to model.zip to resume training from")
    # Opponent: path to a learned Blue model.zip. When None, rule-based
    # BlueAI is used (current default). Threaded into each RedEnv via
    # blue_policy_path so every subproc env loads its own inference copy.
    ap.add_argument("--blue-opponent", default=None,
                    help="Path to MaskablePPO Blue model.zip opponent "
                         "(single-opponent shortcut; ignored if "
                         "--opponent-pool is set)")
    # Opponent pool — comma-separated list for self-play robustness. The
    # "rule" entry stands for rule-based BlueAI; every other entry is a
    # path to a Blue model.zip. Weights are optional and default to
    # uniform. Each episode, RedEnv samples one opponent per the
    # weights. Prevents catastrophic forgetting from single-opponent
    # fine-tunes observed in the earlier Phase 4 500K round.
    ap.add_argument("--opponent-pool", default=None,
                    help="Comma-separated Blue opponents: 'rule' or "
                         "model.zip paths. E.g. "
                         "'rule,rl/models/blue1/model.zip,rl/runs/blue_3/model.zip'")
    ap.add_argument("--opponent-weights", default=None,
                    help="Comma-separated per-opponent sampling weights "
                         "(default: uniform). Must match --opponent-pool "
                         "length; auto-normalized to sum=1.")
    args = ap.parse_args()

    opp_pool, opp_weights = _parse_pool_args(args.opponent_pool, args.opponent_weights)

    ts = time.strftime("%Y%m%d_%H%M%S")
    # `red_<ts>` visually distinguishes Red training runs from Boyu's
    # Blue runs (which use bare `<ts>`).
    run_name = args.run_name or f"red_{ts}"
    run_dir = Path("rl") / "runs" / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    tb_dir = run_dir / "tb"
    ckpt_dir = run_dir / "ckpt"
    ckpt_dir.mkdir(exist_ok=True)

    vec = build_vec_env(
        args.n_envs,
        args.episode_time_limit,
        blue_policy_path=args.blue_opponent,
        blue_opponent_pool=opp_pool,
        blue_opponent_weights=opp_weights,
    )

    policy_kwargs = dict(
        net_arch=[256, 256],
    )

    if args.warmstart is not None:
        # Resume training from saved weights + rollout stats. MaskablePPO
        # will re-bind to our vec env (with learned-Blue opponent if set).
        # CLI hyperparams are NOT re-applied — the saved model keeps its
        # own lr / gamma / ent_coef from the original run. Intentional:
        # fine-tuning with the same hyperparams preserves training
        # momentum; if Chen wants a reset, he can edit the loaded model.
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
        name_prefix="red_ppo",
    )

    print(f"=== Training run {run_name} (RED) ===")
    print(f"total-steps={args.total_steps:,} n-envs={args.n_envs} device={args.device}")
    print(f"episode-time-limit={args.episode_time_limit}s")
    print(f"warmstart={args.warmstart or '(none, fresh init)'}")
    if opp_pool is not None:
        print(f"opponent-pool={opp_pool}")
        print(f"opponent-weights={list(opp_weights) if opp_weights else '(uniform)'}")
    else:
        print(f"blue-opponent={args.blue_opponent or '(rule BlueAI)'}")
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
