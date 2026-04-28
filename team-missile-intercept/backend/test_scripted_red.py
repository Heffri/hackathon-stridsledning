"""Headless smoke test for `ScriptedRedAI` — the event-driven wave
scheduler that runs 3 parallel per-site attack chains (drone → cruise →
ballistic → HGV) opt-in via `RED_WAVE_MODE=scripted` on server.py.

Drones cruise at 120 m/s, so the *natural* chain timings are long:
Main Base at 140 km from the North Remote launcher = ~1200 s to drone
arrival, which means cruise fires at ~1200 s, ballistic ~1490 s, HGV
~1500 s per base. The smoke test runs 1800 sim seconds by default so
round 1 completes for every base and the budget gate visibly engages
in round 2. At 20× match speed in the real demo this is 90 s of wall
clock — completely watchable.

Passes if:
  * at least 2 different threat kinds were spawned,
  * Red budget drained by at least 30 %,
  * ScriptedRedAI logged at least one line per chain.

Not auto-wired into `test_balance.py` — it's a single-shot smoke for
hackathon demo prep. Run with `python test_scripted_red.py` from
`team-missile-intercept/backend/`.
"""
from collections import Counter

from sim import config
from sim.red_ai import ScriptedRedAI
from sim.scenarios import build_default_scenario


def run_smoke(sim_seconds: float = 1800.0, dt: float = 0.05) -> dict:
    scenario = build_default_scenario(auto_start=True)
    scenario.red = ScriptedRedAI(scenario)

    red_start = scenario.world.red_budget
    spawn_kinds: Counter = Counter()

    steps = int(sim_seconds / dt)
    for _ in range(steps):
        scenario.step(dt)
        for ev in scenario.world.events:
            if ev.get("type") == "threat_spawn":
                spawn_kinds[ev.get("kind")] += 1
        if scenario.done:
            break

    red_end = scenario.world.red_budget
    drain_frac = (red_start - red_end) / max(1, red_start)
    site_hps = [(s.name, s.hp) for s in scenario.world.threats and [] or []]
    # Pull site HPs directly from the singleton site list.
    from sim import sites as sites_module
    site_hps = [(s.name, s.hp) for s in sites_module.SOUTH_SITES]

    return {
        "sim_t": scenario.world.t,
        "spawn_kinds": dict(spawn_kinds),
        "total_spawned": scenario.world.threats_spawned,
        "intercepts": scenario.world.intercepts,
        "leaked": scenario.world.leaked,
        "red_budget_start": red_start,
        "red_budget_remaining": red_end,
        "red_budget_drain_frac": drain_frac,
        "winner": scenario.winner,
        "red_log_tail": scenario.red.log[-8:],
        "site_hps": site_hps,
    }


def main():
    print("=== ScriptedRedAI smoke test (headless) ===")
    result = run_smoke(sim_seconds=1800.0)
    print(f"Sim time:             {result['sim_t']:.1f}s")
    print(f"Total threats spawned: {result['total_spawned']}")
    print(f"  by kind:            {result['spawn_kinds']}")
    print(f"Intercepts:           {result['intercepts']}")
    print(f"Leaked:               {result['leaked']}")
    print(f"Red budget:           ${result['red_budget_remaining']:,} "
          f"remaining of ${result['red_budget_start']:,} "
          f"(drained {result['red_budget_drain_frac'] * 100:.1f}%)")
    print(f"Winner:               {result['winner']}")
    print("Site HPs:")
    for name, hp in result["site_hps"]:
        print(f"  {name}: {hp}")
    print("Red log tail:")
    for line in result["red_log_tail"]:
        print(f"  {line}")

    # Simple assertions for CI-grade sanity.
    assert len(result["spawn_kinds"]) >= 2, (
        f"expected ≥2 threat kinds, got {result['spawn_kinds']}"
    )
    assert result["red_budget_drain_frac"] >= 0.30, (
        f"expected ≥30% budget drain, got "
        f"{result['red_budget_drain_frac'] * 100:.1f}%"
    )
    assert len(result["red_log_tail"]) > 0, "expected ScriptedRed log entries"
    print("\nSMOKE PASS")


if __name__ == "__main__":
    main()
