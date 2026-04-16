"""Blue AI — threat assessment, rule-based interceptor selection, PN guidance.

Scan active threats each tick. For threats without an assigned interceptor
and within launch envelope, pick the best-matching interceptor type and
launch. Guidance itself lives on Interceptor.step() (True PN).
"""
from typing import Dict, List

import numpy as np

from . import config
from .types import (
    INTERCEPTOR_SPECS,
    InterceptorType,
    ThreatType,
)


# Priority rules: for each threat kind, ordered preference of interceptors.
# Earlier = preferred. Blue AI walks this list, uses the first one whose
# range envelope contains the threat.
RULES: Dict[ThreatType, List[InterceptorType]] = {
    ThreatType.DRONE: [
        InterceptorType.SHORT_SAM,
        InterceptorType.CIWS,
        InterceptorType.MED_SAM,
    ],
    ThreatType.CRUISE_SUB: [
        InterceptorType.MED_SAM,
        InterceptorType.SHORT_SAM,
    ],
    # Ballistic terminal phase: only LONG_SAM is fast enough to catch it.
    # If somehow not in envelope, Blue AI passes — better than wasting a
    # cheaper interceptor that cannot reach Mach 5+ closing geometry.
    ThreatType.BALLISTIC: [
        InterceptorType.LONG_SAM,
    ],
}


class BlueAI:
    def __init__(self):
        self.assignments: Dict[int, int] = {}  # threat_id -> interceptor_id
        self.log: List[str] = []

    def step(self, t_now: float, world) -> None:
        # Purge dead assignments so a threat that loses its interceptor
        # can be re-engaged.
        dead = []
        for tid, iid in self.assignments.items():
            t = world.threats.get(tid)
            i = world.interceptors.get(iid)
            if t is None or not t.state.alive:
                dead.append(tid)
            elif i is None or not i.state.alive:
                dead.append(tid)
        for tid in dead:
            self.assignments.pop(tid, None)

        base = np.array(config.BLUE_BASE_POS, dtype=np.float64)

        for tid, threat in world.threats.items():
            if not threat.state.alive:
                continue
            if tid in self.assignments:
                continue

            # Range check (3D distance from defended base)
            dist = float(np.linalg.norm(threat.state.pos - base))

            kind_rules = RULES.get(ThreatType(threat.state.kind), [])
            for int_kind in kind_rules:
                spec = INTERCEPTOR_SPECS[int_kind]
                if dist > spec.max_range * config.LAUNCH_RANGE_MARGIN:
                    continue

                # Fire! Launch direction = lead-less initial guess toward threat
                initial_dir = threat.state.pos - base
                # tilt up a bit so it doesn't plow into the ground on boost
                initial_dir[2] = max(initial_dir[2], 1000.0)
                iid = world.spawn_interceptor(
                    int_kind, tuple(base), tuple(initial_dir), tid
                )
                self.assignments[tid] = iid
                self.log.append(
                    f"[{t_now:6.1f}s] Blue launched {int_kind.value} "
                    f"(id {iid}) at {threat.state.kind} (id {tid}), "
                    f"range {dist/1000:.1f} km"
                )
                break
