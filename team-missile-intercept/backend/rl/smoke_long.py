"""Longer smoke — run full matches (no truncation) to verify reward
signal differentiates policies and terminal win/loss fires."""
import numpy as np
import time

from rl.env import MAX_LAUNCHERS, MAX_THREATS, MissileInterceptEnv


def policy_random(obs, rng):
    mask = obs["action_mask"]
    a = np.zeros(MAX_LAUNCHERS, dtype=np.int64)
    for l in range(MAX_LAUNCHERS):
        legal = np.flatnonzero(mask[l])
        a[l] = rng.choice(legal) if legal.size else MAX_THREATS
    return a


def policy_hold(obs):
    return np.full(MAX_LAUNCHERS, MAX_THREATS, dtype=np.int64)


def policy_fire_closest(obs):
    """Fire each launcher at its closest legal threat."""
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


def run(policy_name, seed, time_limit=2500.0):
    env = MissileInterceptEnv(seed=seed, episode_time_limit=time_limit)
    obs, _ = env.reset(seed=seed)
    rng = np.random.default_rng(seed)
    total = 0.0
    fires = 0
    steps = 0
    t0 = time.time()
    while True:
        if policy_name == "random":
            a = policy_random(obs, rng)
        elif policy_name == "hold":
            a = policy_hold(obs)
        elif policy_name == "closest":
            a = policy_fire_closest(obs)
        else:
            raise ValueError(policy_name)
        obs, r, term, trunc, info = env.step(a)
        total += r
        fires += info["n_fires"]
        steps += 1
        if term or trunc:
            break
    dt = time.time() - t0
    print(
        f"{policy_name:10s} seed={seed} winner={str(info['winner']):5s} "
        f"reward={total:+8.1f} fires={fires:4d} sim_t={info['sim_t']:6.1f}s "
        f"site_hp={info['site_hp_total']:4d} budget=${info['blue_budget']/1e6:5.1f}M "
        f"wall={dt:5.1f}s"
    )
    return info


def main():
    print("=== Full-match smoke (truncate at 2500s) ===")
    for policy in ["hold", "random", "closest"]:
        for seed in [1, 2, 3]:
            run(policy, seed)


if __name__ == "__main__":
    main()
