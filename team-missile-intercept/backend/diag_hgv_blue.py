"""Diagnostic — single-HGV blue_ai decision log.

Purpose: answer Chen's observation that PAC-3/PAC-2 fails to intercept
HGVs accurately, especially after they're moved during the SETUP
deployment UI. We need to know whether the miss is a firing-gate
problem (blue_ai waits too long to fire) or a PN precision problem
(interceptor fires but CPA > radius_direct).

No blue_ai behavior change — purely external observation via world +
interceptor state per tick.

Three trials:
  A. Default Blue launcher positions (baseline)
  B. PAC-3/PAC-2 launchers moved 30 km further south (simulating
     what a SETUP-phase drag-drop might do in the worst case)
  C. PAC-3/PAC-2 launchers moved 30 km further NORTH (aggressive
     forward deployment)

Each trial: spawn one HGV from the far-north strip aimed at a southern
site, step the sim, log per-launcher in-gate/can_fire/distance state
every second, diff world.interceptors to detect fires, track CPA
(closest relative distance) for every interceptor vs the HGV.

Run: python diag_hgv_blue.py
"""
from __future__ import annotations

import sys
from math import hypot

import numpy as np

from sim import config, sites
from sim.config import BLUE_LAUNCHER_POSITIONS, LAUNCH_RANGE_MARGIN
from sim.red_ai import RedAI
from sim.scenarios import Scenario
from sim.types import (
    INTERCEPTOR_SPECS,
    InterceptorType,
    MatchPhase,
    ThreatType,
)


_DT = 0.05
_SIM_CAP_S = 120.0
_KINDS_OF_INTEREST = (InterceptorType.LONG_SAM, InterceptorType.HIT_TO_KILL)  # PAC-2, PAC-3


def _shift_launchers(scn: Scenario, kinds: tuple, dy_m: float) -> None:
    """Move every launcher of matching kind by `dy_m` metres along Y."""
    for lch in scn.blue.launchers.launchers:
        if lch.kind in kinds:
            x, y = lch.pos
            lch.pos = (x, y + dy_m)


def _run_trial(label: str, launcher_dy_m: float, verbose: bool = False) -> dict:
    scn = Scenario()
    scn.red = RedAI([])  # suppress wave spawner
    if launcher_dy_m != 0.0:
        _shift_launchers(scn, _KINDS_OF_INTEREST, launcher_dy_m)

    scn.world.transition(MatchPhase.RUNNING)

    # Pick the southernmost military site as the HGV target to give
    # PAC-3 the longest engagement runway possible.
    military = [s for s in sites.SOUTH_SITES if s.subtype in ("air_base", "base")]
    target = min(military, key=lambda s: s.pos[1])  # smallest Y = most south
    tx, ty = target.pos[0], target.pos[1]

    # Deterministic HGV spawn: 10 km west of target, Y=240 km (far north),
    # altitude 35 km. Horizontal flight distance ~180 km.
    spawn_xyz = (tx + 10_000.0, 240_000.0, 35_000.0)
    tid = scn.world.spawn_threat(ThreatType.HGV, spawn_xyz, (tx, ty))
    thr = scn.world.threats[tid]

    prev_icep = set(scn.world.interceptors.keys())
    cpa: dict[int, dict] = {}  # iid -> {kind, min_d, t_fired, t_min_d, final_d}
    first_fire = {"pac_2": None, "pac_3": None}
    first_in_gate = {"pac_2": None, "pac_3": None}
    tick_log: list[str] = []

    max_ticks = int(_SIM_CAP_S / _DT)
    for tick_idx in range(max_ticks):
        t_now = scn.world.t

        # Pre-step state (for in-gate / can_fire logging)
        hgv_alive = thr.state.alive
        hgv_pos = thr.state.pos.copy() if hgv_alive else None

        # Advance sim
        scn.step(_DT)

        # Detect new interceptor births
        new_icep = set(scn.world.interceptors.keys()) - prev_icep
        for iid in new_icep:
            itc = scn.world.interceptors[iid]
            kname = itc.spec.kind.value
            cpa[iid] = {
                "kind": kname,
                "min_d": float("inf"),
                "t_fired": t_now,
                "t_min_d": None,
                "died_at": None,
            }
            if kname in first_fire and first_fire[kname] is None:
                first_fire[kname] = t_now
        prev_icep = set(scn.world.interceptors.keys())

        # Update CPA for every tracked interceptor
        if hgv_alive:
            for iid, info in cpa.items():
                if iid not in scn.world.interceptors:
                    continue
                itc = scn.world.interceptors[iid]
                if not itc.state.alive:
                    if info["died_at"] is None:
                        info["died_at"] = t_now
                    continue
                d3 = float(np.linalg.norm(itc.state.pos - thr.state.pos))
                if d3 < info["min_d"]:
                    info["min_d"] = d3
                    info["t_min_d"] = t_now

        # Log per-launcher state every 1 s (every 20 ticks)
        if hgv_alive and (tick_idx % 20 == 0):
            line_header = (
                f"t={t_now:5.2f}s  HGV=("
                f"{hgv_pos[0] / 1000:6.1f},{hgv_pos[1] / 1000:6.1f},"
                f"{hgv_pos[2] / 1000:5.1f})km  "
                f"|v|={float(np.linalg.norm(thr.state.vel)):5.0f}m/s"
            )
            tick_log.append(line_header)
            for lch in scn.blue.launchers.launchers:
                if lch.kind not in _KINDS_OF_INTEREST:
                    continue
                dx = hgv_pos[0] - lch.pos[0]
                dy = hgv_pos[1] - lch.pos[1]
                dxy = hypot(dx, dy)
                spec = INTERCEPTOR_SPECS[lch.kind]
                gate_m = spec.max_range * LAUNCH_RANGE_MARGIN
                in_gate = dxy <= gate_m
                can_fire = lch.can_fire(t_now)
                kname = lch.kind.value
                if in_gate and can_fire and first_in_gate.get(kname) is None:
                    first_in_gate[kname] = t_now
                tag = ""
                if in_gate and can_fire:
                    tag = "  <-- FIREABLE"
                elif in_gate and not can_fire:
                    tag = "  (gate ok, not ready)"
                tick_log.append(
                    f"   {kname:6s} {lch.id:18s} "
                    f"pos=({lch.pos[0] / 1000:6.1f},{lch.pos[1] / 1000:6.1f}) "
                    f"d={dxy / 1000:5.1f}/{gate_m / 1000:4.1f}km  "
                    f"can_fire={str(can_fire):5s}{tag}"
                )

        # Termination
        if not thr.state.alive:
            break
        if scn.winner is not None:
            break

    # Final outcome
    hgv_final_z = float(thr.state.pos[2])
    hgv_final_xy = (float(thr.state.pos[0]), float(thr.state.pos[1]))
    target_miss = hypot(hgv_final_xy[0] - tx, hgv_final_xy[1] - ty)

    fires_by_kind: dict[str, list[float]] = {}
    for info in cpa.values():
        fires_by_kind.setdefault(info["kind"], []).append(info["min_d"])

    return {
        "label": label,
        "dy_m": launcher_dy_m,
        "target_site": target.name,
        "target_xy": (tx, ty),
        "hgv_alive": thr.state.alive,
        "hgv_final_z": hgv_final_z,
        "target_miss": target_miss,
        "t_end": float(scn.world.t),
        "first_in_gate": first_in_gate,
        "first_fire": first_fire,
        "fires_by_kind": fires_by_kind,
        "tick_log": tick_log,
    }


def _summarize(r: dict) -> None:
    print(f"\n=== Trial {r['label']}  (launcher dy={r['dy_m'] / 1000:+.0f}km) ===")
    print(f"Target: {r['target_site']} @ ({r['target_xy'][0] / 1000:.1f}, {r['target_xy'][1] / 1000:.1f})km")
    print(f"HGV outcome: alive={r['hgv_alive']}  final_z={r['hgv_final_z']:.0f}m  "
          f"target_miss={r['target_miss']:.0f}m  t_end={r['t_end']:.1f}s")
    print(
        "First in-gate: "
        f"pac_2={r['first_in_gate']['pac_2']}  "
        f"pac_3={r['first_in_gate']['pac_3']}"
    )
    print(
        "First fire:    "
        f"pac_2={r['first_fire']['pac_2']}  "
        f"pac_3={r['first_fire']['pac_3']}"
    )
    if not r["fires_by_kind"]:
        print("Fires: NONE — Blue AI never pulled the trigger")
    else:
        print("Fires (CPA per interceptor, m):")
        for kname, cpas in r["fires_by_kind"].items():
            spec_kind = (
                InterceptorType.LONG_SAM if kname == "pac_2"
                else InterceptorType.HIT_TO_KILL if kname == "pac_3"
                else None
            )
            radius_direct = (
                INTERCEPTOR_SPECS[spec_kind].radius_direct if spec_kind else None
            )
            arr = np.array(cpas)
            print(
                f"  {kname:6s}  n={len(cpas):2d}  "
                f"min={arr.min():7.1f}  median={np.median(arr):7.1f}  "
                f"max={arr.max():7.1f}  "
                f"radius_direct={radius_direct}"
            )


def main() -> None:
    trials = [
        _run_trial("A_default", 0.0),
        _run_trial("B_south30km", +30_000.0),  # launchers pushed AWAY from spawn (south)
        _run_trial("C_north30km", -30_000.0),  # launchers pushed TOWARD spawn (north)
    ]

    for r in trials:
        _summarize(r)

    # Write full tick logs to a file for forensic review
    out_path = "hgv_diag_2026-04-20.log"
    with open(out_path, "w", encoding="utf-8") as fh:
        for r in trials:
            fh.write(f"\n{'=' * 60}\n")
            fh.write(f"Trial {r['label']}  (launcher dy={r['dy_m'] / 1000:+.0f}km)\n")
            fh.write(f"{'=' * 60}\n\n")
            for line in r["tick_log"]:
                fh.write(line + "\n")
            fh.write(f"\nOutcome: alive={r['hgv_alive']}  "
                     f"final_z={r['hgv_final_z']:.0f}m  "
                     f"miss={r['target_miss']:.0f}m  "
                     f"t_end={r['t_end']:.1f}s\n")
    print(f"\nFull tick logs → {out_path}")


if __name__ == "__main__":
    main()
