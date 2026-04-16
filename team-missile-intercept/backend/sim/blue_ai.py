"""Blue AI — threat assessment + cost-exchange interceptor selection.

Scan active threats each tick. For threats without an assigned interceptor
and within launch envelope, rank the legal interceptor types by expected
cost (shots_to_kill × cost_per_shot), fire the cheapest option whose
launcher is ready. Guidance itself lives on Interceptor.step() (True PN).
"""
import math
from typing import Dict, List

import numpy as np

from . import config
from .launcher import LauncherFleet
from .types import (
    INTERCEPTOR_SPECS,
    InterceptorType,
    THREAT_SPECS,
    ThreatType,
)


# Which interceptor types are allowed against which threat kinds.
# Ordering is not preference — we rank by cost-exchange at run time. Entries
# omit interceptors that cannot physically engage (e.g. CIWS vs ballistic).
RULES: Dict[ThreatType, List[InterceptorType]] = {
    ThreatType.DRONE: [
        InterceptorType.CIWS,
        InterceptorType.SHORT_SAM,
        InterceptorType.MED_SAM,
    ],
    ThreatType.CRUISE_SUB: [
        InterceptorType.SHORT_SAM,
        InterceptorType.MED_SAM,
        InterceptorType.LONG_SAM,
    ],
    ThreatType.BALLISTIC: [
        InterceptorType.HIT_TO_KILL,
        InterceptorType.LONG_SAM,
    ],
    ThreatType.HGV: [
        InterceptorType.HIT_TO_KILL,
        InterceptorType.LONG_SAM,
    ],
}


def _shots_to_kill(inter_kind: InterceptorType, threat_hp: int) -> int:
    """Expected shots to kill based on the damage_prox channel (since our
    PN rarely achieves the direct-hit radius). Deliberately conservative —
    if the AI over-estimates, it merely over-commits interceptors; if it
    under-estimates, it burns ammo on a target that keeps flying.
    """
    spec = INTERCEPTOR_SPECS[inter_kind]
    dmg = max(1, spec.damage_prox)
    return max(1, math.ceil(threat_hp / dmg))


def _rank_interceptors(
    threat_kind: ThreatType, threat_hp: int, dist: float
) -> List[InterceptorType]:
    """Return the legal interceptor types ordered from cheapest to most
    expensive expected total cost. Out-of-envelope options are filtered."""
    candidates = []
    for kind in RULES.get(threat_kind, []):
        spec = INTERCEPTOR_SPECS[kind]
        if dist > spec.max_range * config.LAUNCH_RANGE_MARGIN:
            continue
        n = _shots_to_kill(kind, threat_hp)
        total_cost = n * spec.usd_cost
        candidates.append((total_cost, kind))
    candidates.sort(key=lambda c: c[0])
    return [k for _, k in candidates]


class BlueAI:
    def __init__(self):
        self.assignments: Dict[int, int] = {}  # threat_id -> interceptor_id
        self.log: List[str] = []
        self.launchers = LauncherFleet()

    def step(self, t_now: float, world) -> None:
        self.launchers.tick(t_now)

        # Purge dead assignments so a damaged-but-alive threat whose
        # interceptor was just consumed can be re-engaged next tick.
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

            dist = float(np.linalg.norm(threat.state.pos - base))
            threat_kind = ThreatType(threat.state.kind)
            ranked = _rank_interceptors(
                threat_kind, threat.state.hp, dist
            )

            for int_kind in ranked:
                launcher = self.launchers.find_ready(int_kind, t_now)
                if launcher is None:
                    continue  # try next-most-expensive option

                initial_dir = threat.state.pos - base
                initial_dir[2] = max(initial_dir[2], 1000.0)
                iid = world.spawn_interceptor(
                    int_kind, tuple(base), tuple(initial_dir), tid
                )
                launcher.fire(t_now)
                self.assignments[tid] = iid

                threat_spec = THREAT_SPECS[threat_kind]
                n_shots = _shots_to_kill(int_kind, threat.state.hp)
                self.log.append(
                    f"[{t_now:6.1f}s] {int_kind.value} → {threat.state.kind} "
                    f"(hp {threat.state.hp}/{threat_spec.hp}, "
                    f"~{n_shots} shot{'s' if n_shots > 1 else ''}, "
                    f"rng {dist/1000:.1f} km)"
                )
                break
