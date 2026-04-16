"""Offline physics check for Part A1/A2/A3 fixes (no Blue AI):
  * drones preserve their spawn Z (A1)
  * ballistic + cruise impact close to the base (A2)
  * drone Z stays stable during flight (A3)
"""
import numpy as np

from sim import config
from sim.red_ai import RedAI, build_demo_waves
from sim.world import World


def run(n_trials: int = 20):
    base = np.array(config.BLUE_BASE_POS, dtype=np.float64)
    impacts = {"drone": [], "cruise_sub": [], "ballistic": []}
    z_traces_all = []  # (spawn_z, [z_samples]) per drone across all trials

    for trial in range(n_trials):
        world = World()
        red = RedAI(build_demo_waves())
        spawn_z = {}
        z_trace = {}

        dt = 0.05
        total_ticks = int(600.0 / dt)
        for _ in range(total_ticks):
            red.step(world.t, world)
            # NOTE: no BlueAI.step — threats fly unopposed to impact.
            world.step(dt)
            for tid, thr in world.threats.items():
                if tid not in spawn_z:
                    spawn_z[tid] = float(thr.state.pos[2])
                if thr.state.kind == "drone" and thr.state.alive:
                    z_trace.setdefault(tid, []).append(float(thr.state.pos[2]))
            for tid, thr in list(world.threats.items()):
                if not thr.state.alive and tid in spawn_z:
                    final_pos = thr.state.pos
                    dist = float(np.linalg.norm(final_pos - base))
                    kind = thr.state.kind
                    if kind in impacts:
                        dy_signed = float(final_pos[1] - base[1])
                        impacts[kind].append((dist, dy_signed))
                        if kind == "drone" and tid in z_trace and z_trace[tid]:
                            z_traces_all.append(
                                (spawn_z[tid], z_trace[tid])
                            )
                    del spawn_z[tid]
                    z_trace.pop(tid, None)
            world.prune_dead()

        # Debug: still-alive threats at end of this trial
        alive = {"drone": 0, "cruise_sub": 0, "ballistic": 0}
        for tid, thr in world.threats.items():
            if thr.state.alive:
                alive[thr.state.kind] = alive.get(thr.state.kind, 0) + 1
        if any(alive.values()):
            print(f"  trial {trial}: still alive at T={world.t:.0f}: {alive}")

    print("--- Impact distance from base (m) ---")
    for kind, dists in impacts.items():
        if dists:
            d_arr = np.array([d[0] for d in dists])
            dy_arr = np.array([d[1] for d in dists])
            print(
                f"  {kind:10s}: n={len(dists):3d}  "
                f"mean_dist={d_arr.mean():7.0f}  "
                f"median={np.median(d_arr):7.0f}  "
                f"max={d_arr.max():7.0f}  "
                f"(dy: mean={dy_arr.mean():+7.0f})"
            )
        else:
            print(f"  {kind:10s}: no impacts recorded")

    if z_traces_all:
        # For each drone, compute |max_z - min_z| during cruise (excluding
        # final 2 km of approach when it dives onto base).
        spread = []
        for spawn_z, trace in z_traces_all:
            arr = np.array(trace)
            # First few samples may be transient, last few are impact. Use
            # the middle 60% for stability measurement.
            if len(arr) >= 20:
                mid = arr[int(len(arr) * 0.2): int(len(arr) * 0.8)]
            else:
                mid = arr
            spread.append(mid.max() - mid.min())
        print(
            f"\n--- Drone Z-stability (range during mid-flight, m) ---\n"
            f"  n={len(spread)}  mean={np.mean(spread):.0f}  "
            f"max={np.max(spread):.0f}"
        )
        # Also spawn_z vs final_z
        spawn_final = [
            (sz, trace[-1]) for sz, trace in z_traces_all if trace
        ]
        if spawn_final:
            diffs = np.array([abs(sz - fz) for sz, fz in spawn_final])
            print(
                f"  spawn_z vs last_z delta: mean={diffs.mean():.0f}  "
                f"max={diffs.max():.0f}"
            )


if __name__ == "__main__":
    run(5)
