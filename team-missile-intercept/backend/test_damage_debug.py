"""Debug: show all hit events (damage / intercept / timeout) over a run."""
from collections import defaultdict

from sim.scenarios import build_default_scenario


def main() -> None:
    scn = build_default_scenario()
    dt = 0.05
    total_ticks = int(500.0 / dt)
    cpa_hist = defaultdict(list)  # (threat_kind, interceptor_kind) -> [d_min]
    damage_count = 0
    intercept_count = 0
    miss_count = 0
    for _ in range(total_ticks):
        scn.step(dt)
        for ev in scn.world.events:
            if ev["type"] == "damage":
                damage_count += 1
                cpa_hist[("damage", ev.get("hit_kind"))].append(ev["miss_distance"])
            elif ev["type"] == "intercept":
                intercept_count += 1
                cpa_hist[("intercept", ev.get("hit_kind"))].append(ev["miss_distance"])
            elif ev["type"] == "timeout":
                miss_count += 1

    snap = scn.snapshot()
    print(f"spawned={snap['stats']['spawned']}  intercepts={snap['stats']['intercepts']}  leaked={snap['stats']['leaked']}")
    print(f"damage events: {damage_count}  intercept events: {intercept_count}  timeouts: {miss_count}")
    print()
    print("CPA by outcome:")
    for key, ds in sorted(cpa_hist.items()):
        if not ds:
            continue
        ds_sorted = sorted(ds)
        print(
            f"  {key}: n={len(ds)} min={ds_sorted[0]:.1f}m "
            f"median={ds_sorted[len(ds)//2]:.1f}m max={ds_sorted[-1]:.1f}m"
        )


if __name__ == "__main__":
    main()
