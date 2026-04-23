"""Red AI — scripted wave spawner with randomised border-line spawning.

Every wave spawns its threats from a single fixed "border" line ~60 km north
of the defended base. Per-spawn X is randomised across the full border
width and Z is randomised within an envelope tuned to each threat type.
Cruise missiles additionally receive 1-2 intermediate waypoints to fly an
S-shape instead of a straight line. Random samples are drawn at spawn time
inside RedAI.step (not at module import) so every demo run looks different.

`ScriptedRedAI` (opt-in via env var `RED_WAVE_MODE=scripted` on server.py)
is an alternative driver that runs 3 parallel attack chains — one per
military site — instead of a fixed wave schedule. Each chain layers drone
→ cruise → ballistic → HGV subwaves whose triggers fire off estimated
time-to-arrival of the previous layer, producing overlapping saturation
attacks. Budget exhaustion naturally terminates the chain when Red's
$100M pool runs out (typically somewhere in round 2).
"""
from dataclasses import dataclass, field
import random
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from . import config, sites
from .launcher import RedLauncherFleet
from .types import THREAT_SPECS, ThreatType, WaveSpec


# --- Target selection weights (Milestone G) ---
# Red AI picks a target site per threat via weighted random choice.
# Capital > base > air_base > major_city, modelling Red's preference
# for maximum strategic damage. A future "Smart Red AI" could pattern
# weights per wave (wave 5 saturates the capital, wave 1 goes for an
# airbase, etc.) — currently every threat rolls independently.
_TARGET_WEIGHTS = {
    "capital":    4.0,
    "base":       3.0,
    "air_base":   2.0,
    "major_city": 1.0,
}


def _pick_target_site(rng: np.random.Generator):
    """M-TIER3-THREAT-CONTRACT (Issue #10, 2026-04-20): richer variant
    of `_pick_target` that returns the chosen `Site` object so callers
    can record `target_site_id` on the spawned Threat. Falls back to
    None if the site list is somehow empty (caller picks the legacy
    base coords directly)."""
    site_list = sites.SOUTH_SITES
    if not site_list:
        return None
    w = np.array(
        [_TARGET_WEIGHTS.get(s.subtype, 1.0) for s in site_list],
        dtype=np.float64,
    )
    w /= w.sum()
    idx = int(rng.choice(len(site_list), p=w))
    return site_list[idx]


def _pick_target(rng: np.random.Generator) -> tuple:
    """Return (x, y) in world metres for a weighted-random site. Falls
    back to the legacy base if the site list is somehow empty. Kept
    as-is for `test_balance_baseline.py`, `test_hgv_impact.py`,
    `test_ballistic_cep.py`, `test_cruise_impact.py` (stable API).
    `RedAI.step` uses `_pick_target_site` so it can populate the
    new `target_site_id` field on each spawned Threat."""
    chosen = _pick_target_site(rng)
    if chosen is None:
        return (config.BLUE_BASE_POS[0], config.BLUE_BASE_POS[1])
    return chosen.pos


# --- Border-line geometry (Milestone G: relative to STRAIT_CENTER_Y) ---
# Pre-G these were offsets from the base (5 km south), which put drones
# at y = 35_000 — visibly INSIDE Blue's own southern mainland — and
# made every spawn look narratively absurd. Milestone G anchors spawn
# Y to the strait centerline instead, so every threat starts physically
# north of the water. Offsets below are "distance NORTH of strait
# centre" (positive = deeper into Red territory). Drone / cruise still
# use them as a fallback when the Red launcher fleet is empty; ballistic
# / HGV moved to the Milestone I far-north strip sampler below.
STRAIT_OFFSET_DRONE     = 10_000   # just over the strait, close-in attack
STRAIT_OFFSET_CRUISE    = 25_000   # further back — cruise is faster
BORDER_HALF_WIDTH = 30_000.0    # X spans ±30 km around base axis

# --- Milestone I: ballistic / HGV far-north strip ---
# Strategic-range re-entry weapons now originate at the far-north edge
# of the arena instead of the old STRAIT_CENTER_Y + offset anchor.
# Mirrors doctrine: ICBM / IRBM launchers sit deep in Red territory, the
# operator wants them visibly "off the map to the north" rather than
# 10-20 km north of the strait.
#
# Y-strip sits at the top of the arena with a 5 km buffer from the edge
# and 10 km band width. X uniform across the full arena width. With
# ARENA_Y = 250 km this lands in [235 km, 245 km].
STRATEGIC_Y_BAND = (config.ARENA_Y - 15_000.0, config.ARENA_Y - 5_000.0)

# Altitude floors for re-entry realism — ballistic RVs and HGVs cannot
# enter the scene at low altitude; they're a kinetic-energy-plus-
# altitude trade. Spawn Z is clamped to at least these values even if
# the random sample from the per-kind range lands lower.
BALLISTIC_MIN_Z = 20_000.0   # m — re-entry entry altitude
HGV_MIN_Z       = 30_000.0   # m — glide ceiling

# --- Per-kind spawn altitude envelopes (m AGL) ---
# Three visual tiers on the 150 km × 150 km arena:
#   - high  (25–40 km): ballistic re-entry, HGV cruise
#   - mid   ( 1– 6 km): subsonic cruise with pop-up at terminal
#   - low   (0.5–4 km): drones
# Cruise is deliberately set above drones so operators can tell the "mid"
# band from the "low" band at a glance during the demo.
DRONE_ALT_RANGE = (500.0, 4_000.0)
CRUISE_ALT_RANGE = (1_000.0, 6_000.0)
BALLISTIC_ALT_RANGE = (30_000.0, 40_000.0)
HGV_ALT_RANGE = (30_000.0, 40_000.0)


def build_demo_waves() -> List[WaveSpec]:
    """5 escalating waves tuned so Blue is not guaranteed to hold —
    wave 5's saturation attack regularly gets at least 1 threat through.
    """
    # Cruise count doubled (4 → 8) and ballistic count doubled (2 → 4)
    # per the "more volume" brief. Drones still spawn from 30 km so
    # SHORT_SAM / CIWS actually engage them.
    waves = [
        WaveSpec(
            time=2.0,
            threats=[ThreatType.DRONE] * 3,
            label="Wave 1: Drones",
        ),
        WaveSpec(
            time=25.0,
            threats=[ThreatType.DRONE] * 3 + [ThreatType.CRUISE_SUB] * 2,
            label="Wave 2: Drones + cruise",
        ),
        WaveSpec(
            time=55.0,
            threats=[ThreatType.CRUISE_SUB] * 4 + [ThreatType.BALLISTIC] * 2,
            label="Wave 3: Cruise + ballistic",
        ),
        WaveSpec(
            time=95.0,
            threats=[ThreatType.HGV] + [ThreatType.DRONE] * 2,
            label="Wave 4: HGV + drones",
        ),
        WaveSpec(
            time=145.0,
            threats=(
                [ThreatType.BALLISTIC] * 2
                + [ThreatType.HGV] * 2
                + [ThreatType.DRONE] * 3
                + [ThreatType.CRUISE_SUB] * 2
            ),
            label="Wave 5: Saturation attack",
        ),
    ]
    return waves


def _sample_spawn(kind: ThreatType, rng: np.random.Generator, base_x: float, base_y: float):
    """Pick (x, y, z) for one threat.

    * Ballistic / HGV (Milestone I): X uniform across the arena width,
      Y uniform in the far-north strip `STRATEGIC_Y_BAND`, Z clamped to
      the reentry / glide floor (20 km / 30 km). Strategic-range
      weapons originate at the far edge, not 10-20 km north of the
      strait.
    * Drone / cruise: fallback path only. Normally routed through
      `RedLauncherFleet.next_pos` in `_spawn_point`; this branch fires
      only when the launcher fleet is empty for that kind (e.g. in
      tests that bypass `config.RED_LAUNCHER_POSITIONS`). Keeps the
      strait-offset sampler so existing behaviour is unchanged.

    `base_y` is retained in the signature for API compatibility.
    """
    if kind == ThreatType.BALLISTIC:
        x = float(rng.uniform(0.0, config.ARENA_X))
        y = float(rng.uniform(*STRATEGIC_Y_BAND))
        z = max(BALLISTIC_MIN_Z, float(rng.uniform(*BALLISTIC_ALT_RANGE)))
        return (x, y, z)
    if kind == ThreatType.HGV:
        x = float(rng.uniform(0.0, config.ARENA_X))
        y = float(rng.uniform(*STRATEGIC_Y_BAND))
        z = max(HGV_MIN_Z, float(rng.uniform(*HGV_ALT_RANGE)))
        return (x, y, z)
    # Drone / cruise fallback (rare — primary path is RedLauncherFleet).
    x = base_x + float(rng.uniform(-BORDER_HALF_WIDTH, BORDER_HALF_WIDTH))
    if kind == ThreatType.DRONE:
        y = config.STRAIT_CENTER_Y + STRAIT_OFFSET_DRONE
        z = float(rng.uniform(*DRONE_ALT_RANGE))
    else:  # CRUISE_SUB
        y = config.STRAIT_CENTER_Y + STRAIT_OFFSET_CRUISE
        z = float(rng.uniform(*CRUISE_ALT_RANGE))
    return (x, y, z)


def _build_cruise_waypoints(
    spawn_xyz, target_xy, rng: np.random.Generator
) -> List[tuple]:
    """Generate 1-2 intermediate waypoints for an S-shaped cruise route.

    Each intermediate point sits along the spawn→target line at a randomly
    chosen progress fraction with a lateral offset of 5-20 km. With two
    waypoints the offsets alternate sign so the path actually weaves.
    """
    sx, sy, sz = spawn_xyz
    tx, ty = target_xy
    # 1 or 2 intermediate waypoints (50/50)
    n = int(rng.integers(1, 3))
    progress = sorted(float(rng.uniform(0.30, 0.70)) for _ in range(n))
    # Random side first, alternating after to weave.
    side = 1.0 if rng.random() < 0.5 else -1.0
    wps: List[tuple] = []
    for i, p in enumerate(progress):
        # base point on the straight line to target
        bx = sx + (tx - sx) * p
        by = sy + (ty - sy) * p
        offset_mag = float(rng.uniform(5_000.0, 20_000.0))
        # Lateral offset direction = perpendicular to the straight line
        # (in XY plane). For a near-southward route this is mostly along X.
        dx = tx - sx
        dy = ty - sy
        norm = float(np.sqrt(dx * dx + dy * dy)) or 1.0
        # Perp(dx,dy) = (-dy, dx)
        px = -dy / norm
        py = dx / norm
        s = side * (1.0 if i % 2 == 0 else -1.0)
        wx = bx + px * offset_mag * s
        wy = by + py * offset_mag * s
        wps.append((wx, wy, sz))
    return wps


class RedAI:
    def __init__(self, waves: List[WaveSpec]):
        self.waves = sorted(waves, key=lambda w: w.time)
        self._next_wave = 0
        self.log: List[str] = []
        # Fresh entropy per RedAI instance — every Reset / restart reshuffles.
        self.rng = np.random.default_rng()
        # Visible Red launcher boxes (Milestone H Part 3). Drones and
        # cruise missiles spawn FROM a launcher position instead of a
        # randomised strait-offset point. Ballistic + HGV keep the
        # abstract border-line spawn (strategic assets, no visible
        # launcher for the demo).
        self.launchers = RedLauncherFleet()

    def step(self, t_now: float, world) -> None:
        """Spawn any waves whose time has come.

        Each WaveSpec.threats is a list of ThreatType (no coords). For
        drone / cruise we pick a Red launcher position (round-robin
        across the configured islands / mainland). For ballistic / HGV
        we keep the abstract strait-origin sample since those are
        strategic-range assets with no visible launcher. Cruise_sub
        additionally generates intermediate waypoints toward its chosen
        target site.
        """
        base_x = config.BLUE_BASE_POS[0]
        base_y = config.BLUE_BASE_POS[1]

        while (
            self._next_wave < len(self.waves)
            and self.waves[self._next_wave].time <= t_now
        ):
            w = self.waves[self._next_wave]
            spawned = 0
            skipped_budget = 0
            for kind in w.threats:
                # M-TIER3-RED-BUDGET (Issue #8): gate individual
                # spawns on world.red_budget. Skip if the threat's
                # cost would take the budget negative. Current demo
                # starts with $100M vs ~$54M default-wave cost so
                # this gate is inactive under default waves; the
                # check exists for the future Boyu Red AI regime
                # where budget becomes a real tactical constraint.
                cost = THREAT_SPECS[kind].usd_cost
                if world.red_budget < cost:
                    skipped_budget += 1
                    continue
                spawn = self._spawn_point(kind, base_x, base_y)
                # M-TIER3-THREAT-CONTRACT (Issue #10): resolve the picked
                # Site (not just its position) so we can stamp
                # `target_site_id` on the spawned Threat. Backward-compat
                # fallback to legacy base coords if SOUTH_SITES is empty.
                chosen_site = _pick_target_site(self.rng)
                if chosen_site is not None:
                    target_xy = chosen_site.pos
                    target_site_id = chosen_site.id
                else:
                    target_xy = (config.BLUE_BASE_POS[0], config.BLUE_BASE_POS[1])
                    target_site_id = None
                if kind == ThreatType.CRUISE_SUB:
                    wps = _build_cruise_waypoints(spawn, target_xy, self.rng)
                    world.spawn_threat(
                        kind, spawn, target_xy,
                        intermediate_waypoints=wps,
                        target_site_id=target_site_id,
                    )
                else:
                    world.spawn_threat(
                        kind, spawn, target_xy,
                        target_site_id=target_site_id,
                    )
                world.red_budget = max(0, world.red_budget - cost)
                spawned += 1
            note = (
                f" (skipped {skipped_budget} — insufficient Red budget)"
                if skipped_budget else ""
            )
            self.log.append(
                f"[{t_now:6.1f}s] {w.label} launched ({spawned} threats){note}"
            )
            self._next_wave += 1

    def _spawn_point(
        self, kind: ThreatType, base_x: float, base_y: float
    ) -> tuple:
        """Pick the (x, y, z) spawn point for a new threat. Drones /
        cruise use the next Red launcher position for their kind (so
        the user sees threats emerge from visible red boxes). Ballistic
        / HGV fall back to the strait-offset random sample.
        """
        if kind in (ThreatType.DRONE, ThreatType.CRUISE_SUB):
            pos = self.launchers.next_pos(kind)
            if pos is not None:
                x, y = pos
                if kind == ThreatType.DRONE:
                    z = float(self.rng.uniform(*DRONE_ALT_RANGE))
                else:
                    z = float(self.rng.uniform(*CRUISE_ALT_RANGE))
                return (x, y, z)
        return _sample_spawn(kind, self.rng, base_x, base_y)

    @property
    def done(self) -> bool:
        return self._next_wave >= len(self.waves)


# =============================================================================
# ScriptedRedAI — event-driven wave scheduler (opt-in via RED_WAVE_MODE=scripted)
# =============================================================================

# Progress fractions for each sub-chain trigger. Pulled out of the code
# as named constants so the attack doctrine is editable in one place.
_DRONE_NEXT_BATCH_PROGRESS = 0.50   # d2 spawns when d1 reaches 50% of its flight
_DRONE_TO_CRUISE_PROGRESS  = 1.00   # cruise spawns when drone "arrives"
_CRUISE_TO_BALLISTIC_PROGRESS = 0.90
_BALLISTIC_PAIR_PROGRESS      = 0.55
_BALLISTIC_TO_HGV_PROGRESS    = 0.50

# Per-base batch sizes (public encyclopedia-level arcade balance numbers).
_DRONE_BATCH_SIZE = 10
_CRUISE_BATCH_SIZE = 5
_BALLISTIC_PAIR_BALLISTICS = 1    # one ballistic fires per "b-slot" in the pair
_HGV_BATCH_SIZE = 1


@dataclass
class _Trigger:
    """Deferred spawn trigger — fires when world.t >= fire_t."""
    fire_t: float
    action: Callable[[], None]
    desc: str = ""


@dataclass
class _AttackChain:
    """All state for a single base's multi-round attack chain."""
    target_site_id: int
    target_name: str
    target_xy: Tuple[float, float]
    # Per-batch metadata: {batch_name: {"spawn_t", "ids", "spawn_pos", "dist"}}
    batches: Dict[str, dict] = field(default_factory=dict)
    rounds_scheduled: int = 0  # 0..3 — how many c/b/h chains have been fired


def _straight_line_dist(spawn_xy: Tuple[float, float], target_xy: Tuple[float, float]) -> float:
    dx = spawn_xy[0] - target_xy[0]
    dy = spawn_xy[1] - target_xy[1]
    return float(np.sqrt(dx * dx + dy * dy))


class ScriptedRedAI:
    """Event-driven wave scheduler.

    Three parallel attack chains — one per military site — each running
    up to 3 rounds of (drones → cruise → ballistic pair → HGV). Round
    triggers fire off estimated arrival time of the previous layer so
    overlap is baked into the doctrine rather than being an artefact of
    tick scheduling. Red's $100M budget typically runs out during round
    2 or early round 3; `world.spawn_threat` is gated on budget here
    (not inside the World), so depletion just stops new spawns — chain
    triggers continue to resolve but the spawn calls skip silently.

    Exposes `log`, `done`, `_next_wave`, `waves`, `launchers` for
    scenarios.snapshot() compatibility so swapping in this class doesn't
    break the WebSocket contract.
    """

    def __init__(self, scenario):
        self.scenario = scenario
        self._chains: List[_AttackChain] = []
        self._triggers: List[_Trigger] = []
        self.log: List[str] = []
        self._initialized = False
        self._finished = False
        self.rng = np.random.default_rng()
        # --- Snapshot-compat shims ---
        # The existing scenario.snapshot() reads `.waves`, `._next_wave`,
        # `.log`, `.launchers`. We expose no-op waves + a real
        # RedLauncherFleet so the HUD's "Wave N/M" indicator and visible
        # red launcher boxes keep rendering (chain progress is logged via
        # `.log`; the wave counter stays 0/0 — the scripted mode isn't
        # wave-indexed, and the HUD treats 0 as "no waves yet" gracefully).
        self.waves: List[WaveSpec] = []
        self._next_wave: int = 0
        self.launchers = RedLauncherFleet()

    # ------------------------------------------------------------------
    # Public interface: matches RedAI so scenario.red can be either class.
    # ------------------------------------------------------------------
    def step(self, t_now: float, world) -> None:
        if not self._initialized:
            self._init_chains(world)
            self._initialized = True

        # Fire all matured triggers in deterministic order (earliest first).
        # A trigger's action may append new triggers; those evaluate next
        # tick, which is fine — the chain is still acyclic per round.
        due = [trig for trig in self._triggers if world.t >= trig.fire_t]
        self._triggers = [trig for trig in self._triggers if world.t < trig.fire_t]
        due.sort(key=lambda tr: tr.fire_t)
        for trig in due:
            try:
                trig.action()
            except Exception as exc:   # pragma: no cover — defensive
                self.log.append(f"[{world.t:6.1f}s] trigger {trig.desc!r} raised {exc!r}")

        # `.done` semantics: mirror RedAI — True once no more spawns will
        # happen AND no live threats remain. Scenario.winner consumes this
        # to decide Blue victory on "out of threats" side.
        no_pending = not self._triggers
        no_live = all(not th.state.alive for th in world.threats.values())
        budget_dry = world.red_budget <= 0
        if no_pending and no_live:
            self._finished = True
        # Edge: if budget dried and every pending trigger would spawn
        # something unaffordable, we still flush pending triggers (they
        # become no-ops) until the queue drains.

    @property
    def done(self) -> bool:
        return self._finished

    # ------------------------------------------------------------------
    # Chain construction
    # ------------------------------------------------------------------
    def _init_chains(self, world) -> None:
        """Build one AttackChain per military site, fire the initial
        drone batch (d1) immediately, and register downstream triggers.

        "Military" = subtype in {'base', 'air_base'} — same filter the
        winner resolver uses. At the current arena crop that's Main Base,
        Spear Point Base, Firewatch Station (3 sites). Targeting cities
        / the capital is out of scope for this mode; those sites survive
        the match untouched.
        """
        military_sites = [s for s in sites.SOUTH_SITES if s.subtype in ("base", "air_base")]
        if not military_sites:
            self.log.append("[ScriptedRed] no military sites found — nothing to attack")
            self._finished = True
            return

        for site in military_sites:
            chain = _AttackChain(
                target_site_id=site.id,
                target_name=site.name,
                target_xy=(float(site.pos[0]), float(site.pos[1])),
            )
            self._chains.append(chain)
            # Round 1: spawn d1 now, schedule d2/d3 + c1 triggers.
            self._spawn_drone_batch(world, chain, batch_name="d1")
            self._schedule_drone_and_cruise_triggers(world, chain, round_idx=1)

        self.log.append(
            f"[{world.t:6.1f}s] ScriptedRed init — {len(self._chains)} chain(s): "
            + ", ".join(c.target_name for c in self._chains)
        )

    def _schedule_drone_and_cruise_triggers(
        self, world, chain: _AttackChain, round_idx: int,
    ) -> None:
        """After d{round_idx} spawns, schedule its follow-ups.

        Round 1: d2 at 50%-of-d1, c1 at 100%-of-d1.
        Round 2: d3 at 50%-of-d2, c2 at 100%-of-d2.
        Round 3: c3 at 100%-of-d3 (no d4).
        """
        drone_name = f"d{round_idx}"
        batch = chain.batches.get(drone_name)
        if batch is None:
            # Drone batch failed to register (budget / no sites / ...).
            return
        drone_speed = THREAT_SPECS[ThreatType.DRONE].cruise_speed
        flight_s = batch["dist"] / max(1.0, drone_speed)
        # Sub-chain A: next drone batch (only for rounds 1 and 2).
        if round_idx < 3:
            next_drone_name = f"d{round_idx + 1}"
            fire_t = batch["spawn_t"] + _DRONE_NEXT_BATCH_PROGRESS * flight_s
            chain_ref = chain
            def _spawn_next_drone(world=world, chain=chain_ref, name=next_drone_name, rd=round_idx + 1):
                self._spawn_drone_batch(world, chain, batch_name=name)
                self._schedule_drone_and_cruise_triggers(world, chain, round_idx=rd)
            self._triggers.append(_Trigger(
                fire_t=fire_t,
                action=_spawn_next_drone,
                desc=f"{chain.target_name}:{next_drone_name}_spawn",
            ))
        # Sub-chain B: cruise batch triggered by this drone batch.
        cruise_name = f"c{round_idx}"
        cruise_fire_t = batch["spawn_t"] + _DRONE_TO_CRUISE_PROGRESS * flight_s
        chain_ref = chain
        rd = round_idx
        def _spawn_cruise(world=world, chain=chain_ref, name=cruise_name, rd=rd):
            self._spawn_cruise_batch(world, chain, batch_name=name)
            self._schedule_ballistic_pair_trigger(world, chain, round_idx=rd)
        self._triggers.append(_Trigger(
            fire_t=cruise_fire_t,
            action=_spawn_cruise,
            desc=f"{chain.target_name}:{cruise_name}_spawn",
        ))

    def _schedule_ballistic_pair_trigger(
        self, world, chain: _AttackChain, round_idx: int,
    ) -> None:
        """After c{round_idx} spawns, register b1 (first of the pair)."""
        cruise_name = f"c{round_idx}"
        batch = chain.batches.get(cruise_name)
        if batch is None:
            return
        cruise_speed = THREAT_SPECS[ThreatType.CRUISE_SUB].cruise_speed
        flight_s = batch["dist"] / max(1.0, cruise_speed)
        fire_t = batch["spawn_t"] + _CRUISE_TO_BALLISTIC_PROGRESS * flight_s
        b1_name = f"b1_r{round_idx}"
        chain_ref = chain
        rd = round_idx
        def _spawn_b1(world=world, chain=chain_ref, name=b1_name, rd=rd):
            self._spawn_ballistic(world, chain, batch_name=name)
            self._schedule_ballistic_to_ballistic_trigger(world, chain, round_idx=rd)
        self._triggers.append(_Trigger(
            fire_t=fire_t,
            action=_spawn_b1,
            desc=f"{chain.target_name}:{b1_name}_spawn",
        ))

    def _schedule_ballistic_to_ballistic_trigger(
        self, world, chain: _AttackChain, round_idx: int,
    ) -> None:
        """After b1_r{round_idx} spawns, register b2 (55% along b1)."""
        b1_name = f"b1_r{round_idx}"
        batch = chain.batches.get(b1_name)
        if batch is None:
            return
        ballistic_speed = THREAT_SPECS[ThreatType.BALLISTIC].cruise_speed
        flight_s = batch["dist"] / max(1.0, ballistic_speed)
        fire_t = batch["spawn_t"] + _BALLISTIC_PAIR_PROGRESS * flight_s
        b2_name = f"b2_r{round_idx}"
        chain_ref = chain
        rd = round_idx
        def _spawn_b2(world=world, chain=chain_ref, name=b2_name, rd=rd):
            self._spawn_ballistic(world, chain, batch_name=name)
            self._schedule_hgv_trigger(world, chain, round_idx=rd)
        self._triggers.append(_Trigger(
            fire_t=fire_t,
            action=_spawn_b2,
            desc=f"{chain.target_name}:{b2_name}_spawn",
        ))

    def _schedule_hgv_trigger(
        self, world, chain: _AttackChain, round_idx: int,
    ) -> None:
        """After b2_r{round_idx} spawns, register HGV (50% along b2)."""
        b2_name = f"b2_r{round_idx}"
        batch = chain.batches.get(b2_name)
        if batch is None:
            return
        ballistic_speed = THREAT_SPECS[ThreatType.BALLISTIC].cruise_speed
        flight_s = batch["dist"] / max(1.0, ballistic_speed)
        fire_t = batch["spawn_t"] + _BALLISTIC_TO_HGV_PROGRESS * flight_s
        hgv_name = f"h_r{round_idx}"
        chain_ref = chain
        def _spawn_hgv(world=world, chain=chain_ref, name=hgv_name):
            self._spawn_hgv(world, chain, batch_name=name)
        self._triggers.append(_Trigger(
            fire_t=fire_t,
            action=_spawn_hgv,
            desc=f"{chain.target_name}:{hgv_name}_spawn",
        ))

    # ------------------------------------------------------------------
    # Spawn helpers — each enforces the budget gate + validate_location,
    # records the batch metadata, and returns early if budget exhausted.
    # ------------------------------------------------------------------
    def _try_spawn(
        self, world, kind: ThreatType, spawn_xyz, chain: _AttackChain,
    ) -> Optional[int]:
        """Budget-gated wrapper around world.spawn_threat. Returns the
        new threat id or None if the spawn was skipped (insufficient
        budget, or spawn_threat validation raised)."""
        cost = THREAT_SPECS[kind].usd_cost
        if world.red_budget < cost:
            return None
        try:
            tid = world.spawn_threat(
                kind, spawn_xyz, chain.target_xy,
                target_site_id=chain.target_site_id,
            )
        except ValueError as exc:
            self.log.append(
                f"[{world.t:6.1f}s] spawn {kind.value} → {chain.target_name} "
                f"rejected: {exc}"
            )
            return None
        world.red_budget = max(0, world.red_budget - cost)
        return tid

    def _spawn_drone_batch(
        self, world, chain: _AttackChain, batch_name: str,
    ) -> None:
        """Spawn up to `_DRONE_BATCH_SIZE` drones toward `chain.target_xy`.

        Spawn position: one uniformly-random drone launcher per spec.
        Per-drone xy jitter (±1500m) and altitude jitter (DRONE_ALT_RANGE)
        so drones don't visually stack. If a jittered position falls on
        water (fails north-land validation), retry at the exact launcher
        position.
        """
        positions = config.RED_LAUNCHER_POSITIONS.get("drone", [])
        if not positions:
            return
        pos_xy = random.choice(positions)
        base_x, base_y = float(pos_xy[0]), float(pos_xy[1])
        ids: List[int] = []
        for _ in range(_DRONE_BATCH_SIZE):
            z = float(self.rng.uniform(*DRONE_ALT_RANGE))
            # Per-drone xy jitter to avoid visual stack
            jx = self.rng.uniform(-1500.0, 1500.0)
            jy = self.rng.uniform(-1500.0, 1500.0)
            spawn_xyz = (base_x + jx, base_y + jy, z)
            tid = self._try_spawn(world, ThreatType.DRONE, spawn_xyz, chain)
            if tid is None:
                # Jitter pushed to sea — retry at exact launcher pos
                spawn_xyz = (base_x, base_y, z)
                tid = self._try_spawn(world, ThreatType.DRONE, spawn_xyz, chain)
                if tid is None:
                    break  # budget-exhausted or hard failure
            ids.append(tid)
        dist = _straight_line_dist(pos_xy, chain.target_xy)
        chain.batches[batch_name] = {
            "spawn_t": world.t,
            "ids": ids,
            "spawn_pos": tuple(pos_xy),
            "dist": dist,
        }
        self.log.append(
            f"[{world.t:6.1f}s] {chain.target_name} {batch_name}: "
            f"{len(ids)}/{_DRONE_BATCH_SIZE} drone(s) from ({pos_xy[0]:.0f},{pos_xy[1]:.0f})"
        )

    def _spawn_cruise_batch(
        self, world, chain: _AttackChain, batch_name: str,
    ) -> None:
        """Spawn up to `_CRUISE_BATCH_SIZE` cruise missiles with S-shape
        intermediate waypoints so each takes a slightly different route.
        """
        positions = config.RED_LAUNCHER_POSITIONS.get("cruise_sub", [])
        if not positions:
            return
        pos_xy = random.choice(positions)
        base_x, base_y = float(pos_xy[0]), float(pos_xy[1])
        ids: List[int] = []
        for _ in range(_CRUISE_BATCH_SIZE):
            z = float(self.rng.uniform(*CRUISE_ALT_RANGE))
            # Per-cruise xy jitter (±800m, smaller than drone because cruise
            # launchers are tighter mainland positions). Retry at launcher
            # pos if jitter pushed to sea.
            jx = self.rng.uniform(-800.0, 800.0)
            jy = self.rng.uniform(-800.0, 800.0)
            spawn_xyz = (base_x + jx, base_y + jy, z)
            # Budget-check before building waypoints (cheap short-circuit).
            cost = THREAT_SPECS[ThreatType.CRUISE_SUB].usd_cost
            if world.red_budget < cost:
                break
            wps = _build_cruise_waypoints(spawn_xyz, chain.target_xy, self.rng)
            try:
                tid = world.spawn_threat(
                    ThreatType.CRUISE_SUB, spawn_xyz, chain.target_xy,
                    intermediate_waypoints=wps,
                    target_site_id=chain.target_site_id,
                )
            except ValueError:
                # Jitter pushed to sea — retry at exact launcher pos
                spawn_xyz = (base_x, base_y, z)
                wps = _build_cruise_waypoints(spawn_xyz, chain.target_xy, self.rng)
                try:
                    tid = world.spawn_threat(
                        ThreatType.CRUISE_SUB, spawn_xyz, chain.target_xy,
                        intermediate_waypoints=wps,
                        target_site_id=chain.target_site_id,
                    )
                except ValueError as exc:
                    self.log.append(
                        f"[{world.t:6.1f}s] spawn cruise → {chain.target_name} "
                        f"rejected: {exc}"
                    )
                    break
            world.red_budget = max(0, world.red_budget - cost)
            ids.append(tid)
        dist = _straight_line_dist(pos_xy, chain.target_xy)
        chain.batches[batch_name] = {
            "spawn_t": world.t,
            "ids": ids,
            "spawn_pos": tuple(pos_xy),
            "dist": dist,
        }
        self.log.append(
            f"[{world.t:6.1f}s] {chain.target_name} {batch_name}: "
            f"{len(ids)}/{_CRUISE_BATCH_SIZE} cruise from ({pos_xy[0]:.0f},{pos_xy[1]:.0f})"
        )

    def _spawn_strategic(
        self,
        world,
        kind: ThreatType,
        chain: _AttackChain,
        batch_name: str,
        alt_range: Tuple[float, float],
        min_z: float,
    ) -> None:
        """Shared helper for ballistic / HGV spawns from the far-north
        STRATEGIC_Y_BAND. One missile per call (spec says 1 per b-slot,
        1 per HGV slot)."""
        x = float(self.rng.uniform(5_000.0, 145_000.0))
        y = float(self.rng.uniform(*STRATEGIC_Y_BAND))
        z = max(min_z, float(self.rng.uniform(*alt_range)))
        spawn_xyz = (x, y, z)
        ids: List[int] = []
        tid = self._try_spawn(world, kind, spawn_xyz, chain)
        if tid is not None:
            ids.append(tid)
        dist = _straight_line_dist((x, y), chain.target_xy)
        chain.batches[batch_name] = {
            "spawn_t": world.t,
            "ids": ids,
            "spawn_pos": (x, y),
            "dist": dist,
        }
        self.log.append(
            f"[{world.t:6.1f}s] {chain.target_name} {batch_name}: "
            f"{len(ids)} {kind.value} from ({x:.0f},{y:.0f})"
        )

    def _spawn_ballistic(
        self, world, chain: _AttackChain, batch_name: str,
    ) -> None:
        self._spawn_strategic(
            world, ThreatType.BALLISTIC, chain, batch_name,
            alt_range=BALLISTIC_ALT_RANGE, min_z=BALLISTIC_MIN_Z,
        )

    def _spawn_hgv(
        self, world, chain: _AttackChain, batch_name: str,
    ) -> None:
        self._spawn_strategic(
            world, ThreatType.HGV, chain, batch_name,
            alt_range=HGV_ALT_RANGE, min_z=HGV_MIN_Z,
        )
