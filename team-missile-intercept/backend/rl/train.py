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
from stable_baselines3.common.callbacks import (
    CallbackList,
    CheckpointCallback,
    EvalCallback,
)
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.utils import get_schedule_fn
from stable_baselines3.common.vec_env import SubprocVecEnv, VecMonitor

from rl.env import (
    MAX_LAUNCHERS,
    MAX_THREATS,
    RL_MAX_EPISODE_SIM_TIME,
    MissileInterceptEnv,
)


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
    red_mode: str,
    difficulty: str,
    red_model_path=None,
    red_deterministic: bool = False,
    red_pool_config=None,
    reward_shaping=None,
    blue_positions=None,
    blue_positions_pool=None,
    scripted_config=None,
):
    def _init():
        env = MissileInterceptEnv(
            seed=seed,
            episode_time_limit=episode_time_limit,
            red_mode=red_mode,
            difficulty=difficulty,
            red_model_path=red_model_path,
            red_deterministic=red_deterministic,
            red_pool_config=red_pool_config,
            reward_shaping=reward_shaping,
            blue_positions=blue_positions,
            blue_positions_pool=blue_positions_pool,
            scripted_config=scripted_config,
        )
        env = Monitor(env)  # standard SB3 per-episode stats
        env = ActionMasker(env, mask_fn)
        return env
    return _init


def build_vec_env(
    n_envs: int,
    episode_time_limit: float,
    red_mode: str,
    difficulty: str,
    base_seed: int = 0,
    red_model_path=None,
    red_deterministic: bool = False,
    red_pool_config=None,
    reward_shaping=None,
    blue_positions=None,
    blue_positions_pool=None,
    scripted_config=None,
):
    fns = [
        make_env(
            base_seed + i,
            episode_time_limit,
            red_mode,
            difficulty,
            red_model_path=red_model_path,
            red_deterministic=red_deterministic,
            red_pool_config=red_pool_config,
            reward_shaping=reward_shaping,
            blue_positions=blue_positions,
            blue_positions_pool=blue_positions_pool,
            scripted_config=scripted_config,
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
    ap.add_argument("--episode-time-limit", type=float,
                    default=RL_MAX_EPISODE_SIM_TIME,
                    help=f"RL horizon (default {RL_MAX_EPISODE_SIM_TIME:.0f}s, "
                         "unified with rl.env.RL_MAX_EPISODE_SIM_TIME). "
                         "Live-server safety cap config.MAX_SIM_TIME=3600s.")
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
    ap.add_argument("--resume", default=None,
                    help="path to .zip checkpoint to resume from; keeps the "
                         "policy/optimizer/normalizer state and continues the "
                         "step counter")
    ap.add_argument("--red-mode", default="training_random",
                    choices=["training_random", "demo_fixed", "trained", "pool", "scripted"],
                    help="training_random = per-episode randomised waves "
                         "(default); demo_fixed = the fixed build_demo_waves() "
                         "script for regression comparison; trained = use a "
                         "frozen MaskablePPO Red policy (requires --red-model); "
                         "pool = per-episode weighted sample from a mix of "
                         "scripted + trained Red opponents (requires "
                         "--red-pool-config); scripted = ScriptedRedAI 3-chain "
                         "per-site attack doctrine (no model needed)")
    ap.add_argument("--difficulty", default="mixed",
                    choices=["easy", "mixed", "hard"],
                    help="difficulty preset for training_random waves — "
                         "controls time jitter and threat-count multiplier")
    ap.add_argument("--red-model", default=None,
                    help="path to a Red-side MaskablePPO .zip — required "
                         "when --red-mode=trained")
    ap.add_argument("--red-deterministic", action="store_true",
                    help="sample Red actions deterministically (default: "
                         "stochastic, matches Red's training entropy)")
    ap.add_argument("--red-pool-config", default=None,
                    help="path to a JSON pool config (see rl/pool_configs/) — "
                         "implies --red-mode=pool, overriding that arg")
    ap.add_argument("--reward-shaping", default=None,
                    help="path to JSON with shaping weights: "
                         "survival_per_decision, early_intercept_bonus, "
                         "early_intercept_window, hgv_intercept_bonus")
    ap.add_argument("--blue-layout-json", default=None,
                    help="path to a layout catalog JSON (see rl/layouts/). "
                         "Pair with --blue-layout-slot to select one entry. "
                         "Overrides config.BLUE_LAUNCHER_POSITIONS for this "
                         "run — env / BlueAI / Scenario do not see the "
                         "config default.")
    ap.add_argument("--blue-layout-slot", default=None,
                    help="slot id in the catalog (e.g. A, B, C). Required "
                         "with --blue-layout-json.")
    ap.add_argument("--blue-layout-pool-json", default=None,
                    help="path to a layout POOL JSON (see "
                         "rl/layouts/AOE_CD_POOL.json). When set, each "
                         "env reset samples a roster from the pool. "
                         "Mutually exclusive with --blue-layout-json.")
    # Scripted curriculum knobs (AOE 2026-04-24). Only consulted when
    # --red-mode=scripted. Defaults reproduce full 3×3×hgv behaviour.
    ap.add_argument("--scripted-chain-count", type=int, default=3,
                    choices=[1, 2, 3],
                    help="ScriptedRedAI: number of parallel attack chains "
                         "(1..3). Curriculum Phase 1 uses 1.")
    ap.add_argument("--scripted-max-rounds", type=int, default=3,
                    choices=[1, 2, 3],
                    help="ScriptedRedAI: max rounds per chain (1..3). "
                         "Phase 1/2/3 use 1.")
    ap.add_argument("--scripted-max-layer", default="hgv",
                    choices=["drone", "cruise", "ballistic", "hgv"],
                    help="ScriptedRedAI: deepest layer a chain escalates "
                         "to. Phase 1/2 use 'drone'; Phase 3 'cruise'.")
    args = ap.parse_args()

    ts = time.strftime("%Y%m%d_%H%M%S")
    run_name = args.run_name or ts
    run_dir = Path("rl") / "runs" / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    tb_dir = run_dir / "tb"
    ckpt_dir = run_dir / "ckpt"
    ckpt_dir.mkdir(exist_ok=True)

    red_pool_cfg = None
    if args.red_pool_config:
        from rl.red_pool import load_pool_config
        red_pool_cfg = load_pool_config(args.red_pool_config)
        args.red_mode = "pool"
    shaping_cfg = None
    if args.reward_shaping:
        import json as _json
        with open(args.reward_shaping, "r", encoding="utf-8") as _f:
            shaping_cfg = _json.load(_f)
    blue_positions = None
    blue_layout_name = None
    blue_positions_pool = None
    blue_layout_pool_label = None
    if args.blue_layout_json or args.blue_layout_slot:
        if not (args.blue_layout_json and args.blue_layout_slot):
            ap.error(
                "--blue-layout-json and --blue-layout-slot must be used together"
            )
        from rl.layout_catalog import get_positions, load_catalog
        cat = load_catalog(args.blue_layout_json)
        blue_positions = get_positions(cat, args.blue_layout_slot)
        entry = cat["layouts"][args.blue_layout_slot]
        blue_layout_name = (
            f"{args.blue_layout_slot} ({entry.get('name', '?')}, "
            f"base=${entry.get('base_cost_usd', 0):,}, "
            f"int_budget=${entry.get('interceptor_budget_usd', 0):,})"
        )
    if args.blue_layout_pool_json:
        if args.blue_layout_json:
            ap.error(
                "--blue-layout-pool-json is mutually exclusive with "
                "--blue-layout-json"
            )
        from rl.layout_catalog import load_layout_pool
        blue_positions_pool = load_layout_pool(args.blue_layout_pool_json)
        blue_layout_pool_label = ",".join(sorted({slot for _, _, slot in blue_positions_pool}))
    if args.red_mode == "trained" and not args.red_model:
        ap.error("--red-mode=trained requires --red-model")
    if args.red_mode == "pool" and red_pool_cfg is None:
        ap.error("--red-mode=pool requires --red-pool-config")

    # Build scripted_config dict when red_mode=scripted so curriculum
    # knobs are forwarded to ScriptedRedAI. Non-scripted runs ignore it.
    scripted_config = None
    if args.red_mode == "scripted":
        scripted_config = {
            "chain_count": args.scripted_chain_count,
            "max_rounds": args.scripted_max_rounds,
            "max_layer": args.scripted_max_layer,
        }

    # Emit one-line run config summary to stdout so the log has a
    # grep-able header: red-mode, episode-time-limit, blue-layout-pool,
    # scripted-curriculum, ent-coef, device.
    scripted_tag = ""
    if scripted_config is not None:
        scripted_tag = (
            f"scripted={scripted_config['chain_count']}chain×"
            f"{scripted_config['max_rounds']}round×{scripted_config['max_layer']} "
        )
    print(
        f"[rl.train] run={run_name} red-mode={args.red_mode} "
        f"episode-time-limit={args.episode_time_limit:.0f}s "
        f"device={args.device} n-envs={args.n_envs} "
        f"total-steps={args.total_steps} "
        f"ent-coef={args.ent_coef} "
        + scripted_tag
        + (f"blue-layout={blue_layout_name} " if blue_layout_name else "")
        + (f"blue-layout-pool={blue_layout_pool_label} " if blue_layout_pool_label else ""),
        flush=True,
    )

    vec = build_vec_env(
        args.n_envs,
        args.episode_time_limit,
        args.red_mode,
        args.difficulty,
        red_model_path=args.red_model,
        red_deterministic=args.red_deterministic,
        red_pool_config=red_pool_cfg,
        reward_shaping=shaping_cfg,
        blue_positions=blue_positions,
        blue_positions_pool=blue_positions_pool,
        scripted_config=scripted_config,
    )

    policy_kwargs = dict(
        net_arch=[256, 256],  # both pi and vf
    )

    if args.resume:
        print(f"Resuming from checkpoint: {args.resume}")
        model = MaskablePPO.load(
            args.resume,
            env=vec,
            device=args.device,
            tensorboard_log=str(tb_dir),
        )
        # Override schedules via CLI when resuming. learning_rate and
        # clip_range are Schedule callables internally, so wrap the raw
        # float via get_schedule_fn (constant schedule) — assigning a
        # bare float breaks `self.clip_range(progress)` calls. ent_coef
        # is a plain float attribute and can be overridden directly.
        model.lr_schedule = get_schedule_fn(args.lr)
        model.clip_range = get_schedule_fn(args.clip_range)
        model.ent_coef = args.ent_coef
        print(f"Resume overrides: lr={args.lr} ent_coef={args.ent_coef} clip_range={args.clip_range}")
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
    # AOE 2026-04-24: rich per-episode metrics (fires-by-kind,
    # leaks-by-kind, win-rate rolling, entropy-collapse alerts) +
    # JSONL dump for post-run plotting.
    from rl.callbacks import MetricsCallback
    metrics_cb = MetricsCallback(run_dir=str(run_dir), window=100)
    callbacks = CallbackList([ckpt_cb, metrics_cb])

    print(f"=== Training run {run_name} ===")
    print(f"total-steps={args.total_steps:,} n-envs={args.n_envs} device={args.device}")
    print(f"episode-time-limit={args.episode_time_limit}s")
    print(f"red-mode={args.red_mode} difficulty={args.difficulty}")
    if blue_layout_name:
        print(f"blue-layout={blue_layout_name}")
    else:
        print("blue-layout=config.BLUE_LAUNCHER_POSITIONS (default)")
    if args.red_mode == "trained":
        print(f"red-model={args.red_model} red-deterministic={args.red_deterministic}")
    if args.red_mode == "pool":
        print(f"red-pool-config={args.red_pool_config}")
        for e in red_pool_cfg.get("entries", []):
            print(f"  pool entry: {e.get('name')} type={e.get('type')} weight={e.get('weight')}")
    print(f"writing to {run_dir}")

    t0 = time.time()
    try:
        model.learn(
            total_timesteps=args.total_steps,
            callback=callbacks,
            tb_log_name="ppo",
            progress_bar=True,
            reset_num_timesteps=not bool(args.resume),
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
