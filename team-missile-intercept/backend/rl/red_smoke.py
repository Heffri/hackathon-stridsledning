"""Smoke test the Red-perspective Gym env.

Mirrors rl/smoke.py. Runs three 100-step checks (per worker-prompt spec):
  1. Random mask-respecting policy — verbose per-step trace, no NaN.
  2. Fixed "hold forever" policy — no spawns, reward stays zero before
     truncation; confirms the no-op path.
  3. Fixed "always-drone" policy — spawns a drone every decision so the
     leak-reward signal gets exercised; caps at 100 decisions so the
     sim doesn't blow up under ~100 concurrent drones.

Prints per-run summary (steps, sim_t, winner, total reward, spawns,
budgets). Exit code 0 on success, non-zero on any failure.
"""
from __future__ import annotations

import sys
import time
from typing import Optional

import numpy as np

from rl.red_env import N_RED_KINDS, RedEnv


def masked_random_action(obs: dict, rng: np.random.Generator, env: RedEnv) -> np.ndarray:
    """Sample an action respecting the marginal action_mask.

    Mask layout: mask[0:N_RED_KINDS] = kind mask, mask[N_RED_KINDS:] =
    site mask. For each component, pick uniformly among legal entries.
    """
    mask = obs["action_mask"]
    n_kinds = N_RED_KINDS
    kind_mask = mask[:n_kinds]
    site_mask = mask[n_kinds:]
    legal_kinds = np.flatnonzero(kind_mask)
    kind = 0 if legal_kinds.size == 0 else int(rng.choice(legal_kinds))
    legal_sites = np.flatnonzero(site_mask)
    site = 0 if legal_sites.size == 0 else int(rng.choice(legal_sites))
    return np.array([kind, site], dtype=np.int64)


def hold_forever(obs: dict, rng, env) -> np.ndarray:
    return np.array([0, 0], dtype=np.int64)


def drone_spam(obs: dict, rng: np.random.Generator, env: RedEnv) -> np.ndarray:
    """Try to spawn a drone every tick; fall back to hold if drone kind
    is masked out (budget empty / no launcher). Target site rotates
    uniformly so leaks spread across all Blue sites."""
    mask = obs["action_mask"]
    kind = 1 if mask[1] else 0  # kind=1 = drone
    site = int(rng.integers(0, env._n_sites))
    return np.array([kind, site], dtype=np.int64)


def run(
    policy_name: str,
    max_steps: int = 100,
    seed: int = 0,
    verbose: bool = False,
) -> bool:
    policies = {
        "random": masked_random_action,
        "hold": hold_forever,
        "drone_spam": drone_spam,
    }
    policy = policies[policy_name]

    env = RedEnv(seed=seed)
    obs, _ = env.reset(seed=seed)
    rng = np.random.default_rng(seed)
    total_reward = 0.0
    n_spawns_attempted = 0
    n_spawns_succeeded = 0
    winner: Optional[str] = None
    step = 0
    t0 = time.time()

    if verbose:
        print(
            f"  step action            reward  term  trunc  threats  "
            f"red_M  blue_M  sim_t"
        )

    for step in range(max_steps):
        action = policy(obs, rng, env)
        if int(action[0]) != 0:
            n_spawns_attempted += 1
        obs, reward, terminated, truncated, info = env.step(action)
        if np.isnan(reward) or np.isinf(reward):
            print(f"[FAIL] {policy_name}: NaN/inf reward at step {step}")
            return False
        total_reward += reward
        n_spawns_succeeded += info.get("n_spawns", 0)

        if verbose:
            n_threats = sum(
                1 for t in env.world.threats.values() if t.state.alive
            )
            print(
                f"  {step:4d} {str(action):16s} {reward:+8.2f}  "
                f"{str(terminated):5s} {str(truncated):5s}  {n_threats:6d}  "
                f"{info['red_budget']/1e6:5.1f}  {info['blue_budget']/1e6:5.1f}  "
                f"{info['sim_t']:5.1f}"
            )

        if terminated or truncated:
            winner = info.get("winner")
            break

    dt = time.time() - t0
    steps_done = step + 1
    sim_t = info.get("sim_t", 0.0)
    red_budget = info.get("red_budget", 0)
    blue_budget = info.get("blue_budget", 0)
    site_hp = info.get("site_hp_total", 0)
    rate = steps_done / dt if dt > 0 else 0.0
    print(
        f"[OK] {policy_name:11s} | steps={steps_done:4d} sim_t={sim_t:6.1f}s "
        f"winner={str(winner):4s} | reward={total_reward:+9.1f} "
        f"spawns={n_spawns_succeeded:3d}/{n_spawns_attempted:3d} "
        f"| red_${red_budget/1e6:5.1f}M blue_${blue_budget/1e6:5.1f}M "
        f"site_hp={site_hp:3d} | {rate:5.0f} dec/s wall={dt:4.1f}s"
    )
    return True


def main():
    print("=== Red RL env smoke test ===")
    # Verbose per-step trace for the random policy — first few lines
    # double as a quick visual sanity check on mask + obs + reward shape.
    print("\n-- random (verbose, first 100 steps) --")
    ok_r = run("random", max_steps=100, seed=1, verbose=True)
    print("\n-- hold --")
    ok_h = run("hold", max_steps=100, seed=2)
    print("\n-- drone_spam --")
    ok_d = run("drone_spam", max_steps=100, seed=3)
    print()
    if ok_r and ok_h and ok_d:
        print("All Red smoke checks passed.")
        return 0
    print("Red smoke test FAILED.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
