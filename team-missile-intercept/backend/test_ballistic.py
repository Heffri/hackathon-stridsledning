"""Smoke-test: spawn a ballistic threat and a LONG_SAM interceptor, step a
full intercept, and print the trajectory so we can eyeball Z behavior.

Runs offline (no server). 30 sim-seconds at dt=0.05 = 600 steps.
"""
import numpy as np

from sim import config
from sim.entities import Interceptor, Threat
from sim.types import InterceptorType, ThreatType


def main() -> None:
    base = np.array(config.BLUE_BASE_POS, dtype=np.float64)
    base_xy = (float(base[0]), float(base[1]))

    # Ballistic: 40 km north of base, 35 km altitude.
    b_start = (base_xy[0], base_xy[1] + 40_000.0, 35_000.0)
    threat = Threat(1, ThreatType.BALLISTIC, b_start, base_xy, t_now=0.0)

    # LONG_SAM fired immediately, launch_dir = raw (threat - base) with z>=1000
    initial_dir = threat.state.pos - base
    initial_dir[2] = max(initial_dir[2], 1000.0)
    inter = Interceptor(
        2, InterceptorType.LONG_SAM, tuple(base), tuple(initial_dir), 1, t_now=0.0
    )

    dt = 0.05
    t = 0.0
    print(f"{'t':>6} {'bZ(km)':>8} {'bSp(m/s)':>9} {'iZ(km)':>8} {'iSp(m/s)':>9} {'range(km)':>10}")
    hit = False
    miss_reported = None
    for step in range(600):
        threat.step(dt)
        inter.step(dt, threat.state, t_now=t)

        # CPA check using prev-vel not stored here; use instantaneous range.
        rng = float(np.linalg.norm(inter.state.pos - threat.state.pos))
        if not hit and rng < max(inter.spec.kill_radius, threat.spec.kill_radius):
            hit = True
            miss_reported = rng
            print(f"*** INTERCEPT at t={t + dt:.2f}s, range={rng:.1f} m ***")

        if step % 20 == 0:
            print(
                f"{t:6.2f} "
                f"{threat.state.pos[2] / 1000:8.2f} "
                f"{float(np.linalg.norm(threat.state.vel)):9.1f} "
                f"{inter.state.pos[2] / 1000:8.2f} "
                f"{float(np.linalg.norm(inter.state.vel)):9.1f} "
                f"{rng / 1000:10.2f}"
            )

        t += dt
        if not threat.state.alive or not inter.state.alive:
            break

    print()
    print(f"Final: threat_alive={threat.state.alive} inter_alive={inter.state.alive}")
    print(f"hit={hit} miss_dist={miss_reported}")
    print(f"threat_final_pos={threat.state.pos}, speed={float(np.linalg.norm(threat.state.vel)):.1f} m/s")
    print(f"inter_final_pos={inter.state.pos}, speed={float(np.linalg.norm(inter.state.vel)):.1f} m/s")


if __name__ == "__main__":
    main()
