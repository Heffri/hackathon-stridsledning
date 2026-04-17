"""Blue force launchers — per-launcher magazine + inter-shot CD + reload.

Each launcher tracks its own ammunition counter and reload state. When its
magazine hits zero it goes into "reload" for `reload_time` seconds, after
which it refills to full capacity. Between shots there's also a shorter
`inter_shot_cd` gate (rate-of-fire limit).

Reload times are the /10-scaled values from WEAPON_SPECS.md so a Blue run
doesn't stall waiting several real minutes for a PAC-2 refill.
"""
from dataclasses import dataclass, field
from typing import Dict, List

from .types import InterceptorType


@dataclass
class Launcher:
    kind: InterceptorType
    magazine_capacity: int
    inter_shot_cd: float       # seconds between consecutive shots
    reload_time: float         # seconds from empty → full
    current_ammo: int = 0
    last_shot_t: float = -999.0
    reload_start_t: float = -999.0

    def __post_init__(self):
        if self.current_ammo == 0:
            self.current_ammo = self.magazine_capacity

    @property
    def reloading(self) -> bool:
        return self.current_ammo == 0

    def reload_remaining(self, t_now: float) -> float:
        if not self.reloading:
            return 0.0
        return max(0.0, self.reload_time - (t_now - self.reload_start_t))

    def tick(self, t_now: float) -> None:
        # Refill when reload window elapses. Called every tick by the
        # owning fleet before firing attempts.
        if self.reloading and (t_now - self.reload_start_t) >= self.reload_time:
            self.current_ammo = self.magazine_capacity

    def can_fire(self, t_now: float) -> bool:
        if self.reloading:
            return False
        return (t_now - self.last_shot_t) >= self.inter_shot_cd

    def fire(self, t_now: float) -> None:
        self.current_ammo -= 1
        self.last_shot_t = t_now
        if self.current_ammo <= 0:
            self.reload_start_t = t_now


# Per-type launcher template (magazine + cooldowns). Reload values are
# already /10-scaled for demo pacing; see WEAPON_SPECS.md.
LAUNCHER_TEMPLATES: Dict[InterceptorType, Dict] = {
    InterceptorType.CIWS: dict(
        magazine_capacity=144, inter_shot_cd=0.2, reload_time=30.0,
    ),
    InterceptorType.SHORT_SAM: dict(
        magazine_capacity=1, inter_shot_cd=5.0, reload_time=5.0,
    ),
    InterceptorType.IRIS_T_SLS: dict(
        magazine_capacity=4, inter_shot_cd=3.0, reload_time=60.0,
    ),
    InterceptorType.MED_SAM: dict(
        magazine_capacity=8, inter_shot_cd=5.0, reload_time=120.0,
    ),
    InterceptorType.LONG_SAM: dict(
        magazine_capacity=4, inter_shot_cd=10.0, reload_time=180.0,
    ),
    InterceptorType.HIT_TO_KILL: dict(
        magazine_capacity=4, inter_shot_cd=10.0, reload_time=180.0,
    ),
}


# Starting loadout: how many of each launcher type the Blue base fields.
DEFAULT_LOADOUT: Dict[InterceptorType, int] = {
    InterceptorType.CIWS: 1,
    InterceptorType.SHORT_SAM: 2,
    InterceptorType.IRIS_T_SLS: 2,
    InterceptorType.MED_SAM: 2,
    InterceptorType.LONG_SAM: 1,
    InterceptorType.HIT_TO_KILL: 1,
}


class LauncherFleet:
    """Owns every launcher on the Blue side. Offers a "find a ready
    launcher of kind K" API for Blue AI to call when it decides to fire.
    """

    def __init__(self, loadout: Dict[InterceptorType, int] = None):
        if loadout is None:
            loadout = DEFAULT_LOADOUT
        self.launchers: List[Launcher] = []
        for kind, n in loadout.items():
            tmpl = LAUNCHER_TEMPLATES.get(kind)
            if tmpl is None:
                continue
            for _ in range(n):
                self.launchers.append(Launcher(kind=kind, **tmpl))

    def tick(self, t_now: float) -> None:
        for lch in self.launchers:
            lch.tick(t_now)

    def find_ready(self, kind: InterceptorType, t_now: float):
        for lch in self.launchers:
            if lch.kind == kind and lch.can_fire(t_now):
                return lch
        return None

    def fleet_status(self, t_now: float) -> Dict[str, dict]:
        """Snapshot-friendly per-kind aggregate: total current ammo,
        total capacity, whether ALL launchers of that kind are reloading,
        and the max remaining reload time across them."""
        agg: Dict[str, dict] = {}
        for lch in self.launchers:
            key = lch.kind.value
            slot = agg.setdefault(
                key,
                {
                    "current": 0,
                    "capacity": 0,
                    "reloading_count": 0,
                    "count": 0,
                    "reload_remaining": 0.0,
                },
            )
            slot["current"] += lch.current_ammo
            slot["capacity"] += lch.magazine_capacity
            slot["count"] += 1
            if lch.reloading:
                slot["reloading_count"] += 1
                slot["reload_remaining"] = max(
                    slot["reload_remaining"], lch.reload_remaining(t_now)
                )

        out: Dict[str, dict] = {}
        for k, slot in agg.items():
            out[k] = {
                "current": slot["current"],
                "capacity": slot["capacity"],
                "reloading": slot["reloading_count"] == slot["count"],
                "reload_remaining": slot["reload_remaining"],
            }
        return out
