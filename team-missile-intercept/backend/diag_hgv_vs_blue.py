"""Diagnostic: single HGV vs full Blue AI.

Runs one HGV against the default Blue deployment (no Red waves) and
prints tick-by-tick gate / fire / CPA data for PAC-3, PAC-2, IRIS-T SLM
launchers. Goal: decide whether HGV leak rate (Issue #15) is a
FIRING-GATE problem (Blue never fires) or a PN PRECISION problem
(Blue fires but CPA > radius_direct).

This is a one-shot diagnostic, not a test. It does NOT modify any
runtime behavior. It snapshots launcher ammo pre/post step to detect
fires, and tracks interceptor-to-HGV geometry to compute CPA.

Run: python diag_hgv_vs_blue.py
"""
from __future__ import annotations

from math import hypot

import numpy as np

from sim import config, sites
from sim.blue_ai import BlueAI
from sim.red_ai import RedAI
from sim.types import (
    INTERCEPTOR_SPECS,
    InterceptorType,
    MatchPhase,
    ThreatType,
)
from sim.world import World


DT = 0.05
TIMEOUT_S = 90.0


def run_trial(label: str, launcher_overrides=None, hgv_spawn_xyz=None, hgv_target_xy=None):
    sites.reset_leaks()
    world = World()
    red = RedAI([])  # empty waves
    blue = BlueAI()

    if launcher_overrides:
        for lch_id, new_xy in launcher_overrides.items():
            for lch in blue.launchers.launchers:
                if lch.id == lch_id:
                    lch.pos = tuple(new_xy)

    world.transition(MatchPhase.RUNNING)

    if hgv_spawn_xyz is None:
        hgv_spawn_xyz = (75000.0, 240000.0, 35000.0)
    if hgv_target_xy is None:
        hgv_target_xy = (75300.0, 8000.0)  # PAC-3's default position

    spawn = np.array(hgv_spawn_xyz, dtype=float)
    tid = world.spawn_threat(ThreatType.HGV, spawn, hgv_target_xy)
    thr = world.threats[tid]

    watch_kinds = (InterceptorType.HIT_TO_KILL, InterceptorType.LONG_SAM, InterceptorType.MED_SAM)
    watch = [l for l in blue.launchers.launchers if l.kind in watch_kinds]

    print(f"\n========== TRIAL: {label} ==========")
    print(f"HGV spawn=({hgv_spawn_xyz[0]/1000:.1f}, {hgv_spawn_xyz[1]/1000:.1f}, {hgv_spawn_xyz[2]/1000:.1f}km)  target=({hgv_target_xy[0]/1000:.1f}, {hgv_target_xy[1]/1000:.1f})")
    print("Watch launchers:")
    for l in watch:
        s = INTERCEPTOR_SPECS[l.kind]
        gate_km = s.max_range * config.LAUNCH_RANGE_MARGIN / 1000
        print(f"  {l.id:18s} kind={l.kind.name:12s} pos=({l.pos[0]/1000:.1f},{l.pos[1]/1000:.1f})  max_range={s.max_range/1000:.0f}km  gate={gate_km:.0f}km  fuel={s.fuel_s:.0f}s  radius_direct={s.radius_direct:.0f}m  radius_prox={s.radius_prox:.0f}m")

    first_gate = {l.id: None for l in watch}
    first_fire = {l.id: None for l in watch}
    fire_events = []  # (t, launcher_id, launcher_ammo_before, hgv_pos)
    # interceptor track: iid -> list of (t, dist_xy, dz, dist_3d)
    ic_tracks = {}
    # attribute each iid to a launcher by snapshotting ammo before each step
    iid_to_launcher = {}

    max_ticks = int(TIMEOUT_S / DT)
    progress_every = int(2.0 / DT)

    for step_i in range(max_ticks):
        t_now = world.t

        # pre-step: ammo snapshot + live interceptor id set
        pre_ammo = {l.id: l.current_ammo for l in watch}
        pre_iids = set(world.interceptors.keys())

        blue.step(t_now, world)
        world.step(DT)
        world.prune_dead()

        post_ammo = {l.id: l.current_ammo for l in watch}
        post_iids = set(world.interceptors.keys())
        new_iids = post_iids - pre_iids

        # attribute new interceptors to launchers via ammo drop
        # (one per launcher per tick — blue only fires one shot per _try_fire return)
        for l in watch:
            if post_ammo[l.id] < pre_ammo[l.id]:
                # find a new iid whose kind matches
                matching = [iid for iid in new_iids if world.interceptors[iid].spec.kind == l.kind]
                if matching:
                    iid = matching[0]
                    new_iids.discard(iid)
                    iid_to_launcher[iid] = l.id
                    ic_tracks[iid] = []
                    fire_events.append((t_now, l.id, pre_ammo[l.id], tuple(thr.state.pos)))
                    if first_fire[l.id] is None:
                        first_fire[l.id] = t_now

        # update interceptor tracks
        if thr.state.alive:
            hx, hy, hz = float(thr.state.pos[0]), float(thr.state.pos[1]), float(thr.state.pos[2])
            for iid in list(ic_tracks.keys()):
                if iid in world.interceptors and world.interceptors[iid].state.alive:
                    ic = world.interceptors[iid]
                    ix, iy, iz = float(ic.state.pos[0]), float(ic.state.pos[1]), float(ic.state.pos[2])
                    d_xy = hypot(hx - ix, hy - iy)
                    dz = hz - iz
                    d_3d = hypot(d_xy, dz)
                    ic_tracks[iid].append((t_now, d_xy, dz, d_3d))

            # first-gate-enter detection
            for l in watch:
                if first_gate[l.id] is None:
                    d = hypot(hx - l.pos[0], hy - l.pos[1])
                    gate = INTERCEPTOR_SPECS[l.kind].max_range * config.LAUNCH_RANGE_MARGIN
                    if d <= gate:
                        first_gate[l.id] = t_now

            if step_i % progress_every == 0:
                line = f"  t={t_now:5.1f}s HGV=({hx/1000:5.1f},{hy/1000:5.1f},{hz/1000:5.1f}km) v={np.linalg.norm(thr.state.vel):5.0f}m/s | dist_km:"
                for l in watch:
                    d_km = hypot(hx - l.pos[0], hy - l.pos[1]) / 1000
                    line += f" {l.id}={d_km:5.1f}"
                print(line)
        else:
            print(f"  t={t_now:5.1f}s HGV DEAD at ({thr.state.pos[0]/1000:.1f},{thr.state.pos[1]/1000:.1f},{thr.state.pos[2]/1000:.2f}km)")
            break

    # summary
    print()
    print(f"Final: alive={thr.state.alive}  t_end={world.t:.1f}s  HGV=({thr.state.pos[0]/1000:.1f},{thr.state.pos[1]/1000:.1f},{thr.state.pos[2]/1000:.2f}km)")
    print()
    print(f"{'launcher':18s}  {'first_gate':>10s}  {'first_fire':>10s}  fires_total")
    for l in watch:
        gate_s = f"{first_gate[l.id]:.1f}s" if first_gate[l.id] is not None else "never"
        fire_s = f"{first_fire[l.id]:.1f}s" if first_fire[l.id] is not None else "never"
        n_fires = sum(1 for f in fire_events if f[1] == l.id)
        print(f"{l.id:18s}  {gate_s:>10s}  {fire_s:>10s}  {n_fires}")

    if fire_events:
        print()
        print("Fire events:")
        for t, lid, ammo_b, hgv_pos in fire_events:
            print(f"  t={t:5.1f}s {lid:18s}  ammo {ammo_b}->{ammo_b-1}  HGV=({hgv_pos[0]/1000:.1f},{hgv_pos[1]/1000:.1f},{hgv_pos[2]/1000:.2f}km)")

    if ic_tracks:
        print()
        print("Per-interceptor CPA (3D min distance to HGV over flight):")
        for iid, track in ic_tracks.items():
            if not track:
                continue
            lid = iid_to_launcher.get(iid, '?')
            kind = world.interceptors[iid].spec.kind.name if iid in world.interceptors else '(dead)'
            # find min d_3d
            cpa_row = min(track, key=lambda r: r[3])
            t_cpa, dxy_cpa, dz_cpa, d3d_cpa = cpa_row
            spec = INTERCEPTOR_SPECS[world.interceptors[iid].spec.kind] if iid in world.interceptors else None
            rd = spec.radius_direct if spec else None
            rp = spec.radius_prox if spec else None
            verdict = ""
            if rd is not None:
                if d3d_cpa <= rd:
                    verdict = " *** DIRECT HIT range ***"
                elif d3d_cpa <= rp:
                    verdict = " *** PROX range ***"
                else:
                    verdict = f" miss by {d3d_cpa - rp:.0f}m beyond prox"
            print(f"  iid={iid:3d} launcher={lid:18s} CPA_3d={d3d_cpa:6.0f}m (xy={dxy_cpa:6.0f}m, dz={dz_cpa:+7.0f}m) at t={t_cpa:5.1f}s{verdict}")

    return {
        "alive": thr.state.alive,
        "t_end": world.t,
        "first_gate": first_gate,
        "first_fire": first_fire,
        "fire_events": fire_events,
        "ic_tracks": ic_tracks,
    }


def main():
    # Trial 1: HGV straight at PAC-3 base
    run_trial(
        label="A: default positions, HGV dead-center at PAC-3",
        hgv_spawn_xyz=(75000.0, 240000.0, 35000.0),
        hgv_target_xy=(75300.0, 8000.0),
    )

    # Trial 2: HGV flanking — aimed at SLM forward launcher
    run_trial(
        label="B: default positions, HGV aimed at iris_t_slm_0 forward (82km, 72km)",
        hgv_spawn_xyz=(82000.0, 240000.0, 35000.0),
        hgv_target_xy=(82000.0, 72000.0),
    )

    # Trial 3: PAC-3 moved SOUTH (simulating bad SETUP placement)
    run_trial(
        label="C: PAC-3 moved south to y=-15km, HGV dead-center",
        launcher_overrides={"pac_3_0": (75300.0, -15000.0)},
        hgv_spawn_xyz=(75000.0, 240000.0, 35000.0),
        hgv_target_xy=(75300.0, 8000.0),
    )

    # Trial 4: PAC-3 moved FORWARD (potential best case)
    run_trial(
        label="D: PAC-3 moved forward to y=40km, HGV dead-center",
        launcher_overrides={"pac_3_0": (75300.0, 40000.0)},
        hgv_spawn_xyz=(75000.0, 240000.0, 35000.0),
        hgv_target_xy=(75300.0, 8000.0),
    )


if __name__ == "__main__":
    main()
