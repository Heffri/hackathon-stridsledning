"""Standalone PN guidance sanity check.

Usage: python test_pn.py
Runs a 10-second chase: medium-SAM from south chasing a subsonic cruise
threat inbound from north. Prints miss distance and trajectory stats.
"""
import numpy as np

from sim import config
from sim.entities import Interceptor, Threat
from sim.types import InterceptorType, ThreatType


def run():
    # Threat: subsonic cruise flying south toward base
    threat_start = (config.BLUE_BASE_POS[0] + 5000.0, 35_000.0)
    threat_target = (config.BLUE_BASE_POS[0], 0.0)
    threat = Threat(
        eid=1,
        kind=ThreatType.CRUISE_SUB,
        start_xy=threat_start,
        target_xy=threat_target,
        t_now=0.0,
    )

    # Interceptor: med-SAM launched from base, aimed up-north
    launch_pos = config.BLUE_BASE_POS
    initial_dir = (0.0, 1.0, 0.3)
    inter = Interceptor(
        eid=2,
        kind=InterceptorType.MED_SAM,
        launch_pos=launch_pos,
        initial_dir=initial_dir,
        target_id=1,
        t_now=0.0,
    )

    dt = config.DT
    min_dist = float("inf")
    hit = False
    for step in range(int(60 / dt)):
        threat.step(dt)
        inter.step(dt, threat.state)
        d = float(np.linalg.norm(threat.state.pos - inter.state.pos))
        min_dist = min(min_dist, d)
        if step % 40 == 0:
            t = step * dt
            print(
                f"t={t:5.2f}s | inter=({inter.state.pos[0]:7.0f},{inter.state.pos[1]:7.0f},{inter.state.pos[2]:6.0f}) "
                f"v={np.linalg.norm(inter.state.vel):5.0f}  | "
                f"threat=({threat.state.pos[0]:7.0f},{threat.state.pos[1]:7.0f},{threat.state.pos[2]:6.0f}) "
                f"v={np.linalg.norm(threat.state.vel):5.0f}  | dist={d:8.1f}"
            )
        if d < max(inter.spec.kill_radius, threat.spec.kill_radius):
            hit = True
            print(f"  >>> intercept at t={step * dt:.2f}s, dist={d:.1f}m")
            break

    print(f"\nMin distance reached: {min_dist:.1f} m | hit={hit}")


if __name__ == "__main__":
    run()
