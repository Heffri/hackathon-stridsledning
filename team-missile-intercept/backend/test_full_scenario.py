"""Smoke-test: run the full demo scenario offline for 200 seconds and
print stats. Used to catch regressions before opening the browser.
"""
from sim.scenarios import build_default_scenario


def main() -> None:
    scn = build_default_scenario()
    dt = 0.05
    total_ticks = int(200.0 / dt)
    for _ in range(total_ticks):
        scn.step(dt)

    snap = scn.snapshot()
    print("--- Final snapshot stats ---")
    for k, v in snap["stats"].items():
        print(f"  {k}: {v}")
    print(f"  wave: {snap['wave']} / {snap['total_waves']}")
    print()
    print("--- Red log (last 6) ---")
    for line in snap["red_log"]:
        print(f"  {line}")
    print()
    print("--- Blue log (last 10) ---")
    for line in scn.blue.log[-10:]:
        print(f"  {line}")


if __name__ == "__main__":
    main()
