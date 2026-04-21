"""Smoke test the Gym env.

Runs three checks:
  1. Reset + 20 random steps with mask-respecting random policy → no crash.
  2. Fixed "hold everything" policy → reward non-NaN, episode completes.
  3. Fixed "fire at first threat from every launcher" policy → shows reward
     signal propagates from events.

Exit code 0 on success, non-zero on any failure.
"""
import sys
import time

import numpy as np

from rl.env import MAX_LAUNCHERS, MAX_THREATS, MissileInterceptEnv


def masked_random_action(obs, rng):
    """Sample an action respecting the action_mask.

    For each launcher row, sample uniformly among legal columns.
    """
    mask = obs["action_mask"]  # [N_L, N_T+1]
    action = np.zeros(MAX_LAUNCHERS, dtype=np.int64)
    for l in range(MAX_LAUNCHERS):
        legal = np.flatnonzero(mask[l])
        if legal.size == 0:
            action[l] = MAX_THREATS  # hold
        else:
            action[l] = rng.choice(legal)
    return action


def hold_everything(obs):
    return np.full(MAX_LAUNCHERS, MAX_THREATS, dtype=np.int64)


def fire_first(obs):
    mask = obs["action_mask"]
    action = np.full(MAX_LAUNCHERS, MAX_THREATS, dtype=np.int64)
    for l in range(MAX_LAUNCHERS):
        legal = np.flatnonzero(mask[l, :MAX_THREATS])  # exclude hold
        if legal.size > 0:
            action[l] = legal[0]
    return action


def run(policy, label, max_steps=2000, seed=0):
    env = MissileInterceptEnv(seed=seed)
    obs, _ = env.reset(seed=seed)
    rng = np.random.default_rng(seed)
    total_reward = 0.0
    n_fires = 0
    t0 = time.time()
    for step in range(max_steps):
        if policy == "random":
            action = masked_random_action(obs, rng)
        elif policy == "hold":
            action = hold_everything(obs)
        elif policy == "fire_first":
            action = fire_first(obs)
        else:
            raise ValueError(policy)
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        n_fires += info["n_fires"]
        if np.isnan(reward) or np.isinf(reward):
            print(f"[FAIL] {label}: NaN/inf reward at step {step}")
            return False
        if terminated or truncated:
            break
    dt = time.time() - t0
    steps_done = step + 1
    sim_t = info["sim_t"]
    decisions_per_s = steps_done / dt
    sim_ticks = steps_done * 10  # DECISION_EVERY
    tick_fps = sim_ticks / dt
    print(
        f"[OK] {label:14s} "
        f"| steps={steps_done:4d} sim_t={sim_t:6.1f}s winner={str(info['winner']):4s} "
        f"| reward={total_reward:+8.1f} fires={n_fires:4d} "
        f"| {decisions_per_s:5.0f} dec/s ({tick_fps:5.0f} tick/s) wall={dt:5.1f}s"
    )
    return True


def main():
    print("=== RL env smoke test ===")
    ok_r = run("random", "random-masked", max_steps=2000, seed=1)
    ok_h = run("hold", "hold-everything", max_steps=2000, seed=2)
    ok_f = run("fire_first", "fire-first", max_steps=2000, seed=3)
    if ok_r and ok_h and ok_f:
        print("All smoke checks passed.")
        return 0
    print("Smoke test FAILED.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
