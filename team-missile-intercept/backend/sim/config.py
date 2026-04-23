"""Central tunable parameters for the Milestone B demo.

All physics, arena, guidance, and rendering parameters live here.

Arcade-AOE note (blue_aoe_long Phase 2): every detonation applies a flat
`fragment_damage` to threats within `fragment_radius`. Final calibrated
values live on each InterceptorSpec in `sim/types.py` (§3.6 of the worker
prompt). AOE_ENABLED below is a circuit-breaker for regression testing
the legacy CPA-falloff damage path — production runs leave it True.
"""

# --- Arcade fragmentation AOE ---
AOE_ENABLED = True


# --- Arena ---
ARENA_X = 150_000.0  # east-west extent (m)
ARENA_Y = 250_000.0  # north-south extent (m) — deep enough for HGV's
                      # 180 km spawn border and ballistic's 120 km, so
                      # Blue can see the interceptors run out of fuel
                      # during the long head-on engagement.
ARENA_Z = 40_000.0   # ceiling (m)
GROUND_Z = 0.0

# --- Time ---
DT = 0.05            # physics step (s)
PHYSICS_HZ = 1.0 / DT
STREAM_HZ = 15.0     # WebSocket state broadcast
# Milestone I replaced the 600 s hard cap with real win conditions
# (site HP depletion, Blue budget exhaustion, Red-out-of-threats). The
# 3600 s value is a safety net only — a typical match ends in 150-400 s.
MAX_SIM_TIME = 3600.0

# --- Environment ---
GRAVITY = 9.81       # m/s^2, applied -Z
# Air density (constant for this demo — atmosphere model deferred)
AIR_DENSITY = 1.225  # kg/m^3 at sea level

# --- Guidance ---
PN_GAIN = 4.0        # True Proportional Navigation N
LAUNCH_RANGE_MARGIN = 1.1  # fire when threat within 1.1x interceptor max range
INTERCEPT_TIMEOUT = 80.0   # self-destruct stale interceptors (s)

# --- Kill check ---
# Binary intercept: closest-approach distance during tick < kill_radius.
# Generous radii for demo visibility. Tune down for final game.
DEFAULT_KILL_RADIUS = 40.0   # m

# --- Defended position (Blue base, south-center) ---
BLUE_BASE_POS = (ARENA_X * 0.5, 5_000.0, 0.0)  # x, y, z
# Base "footprint" used for leak detection. A threat that crosses this
# horizontal radius around the base centre (at any altitude, in-air or on
# ground impact) counts as a leak. Tuned to match the visual base marker
# scale (~2.5 km cylinder) and a realistic "defended area" rather than a
# pinpoint site — 250 m was too tight (HGV diving at 1700 m/s skipped the
# 3D sphere cleanly and ground-impacts 300-800 m from centre were
# silently classified as "ground_crash"). 1500 m models an airfield-
# class defended area and matches user intuition of "hit the base".
#
# 2026-04-23: bumped 1500 → 3500 as an Issue #14 workaround. Ballistic
# CEP in the current sim averages ~3300 m, so a 1500 m disc was putting
# most ballistic impacts *outside* the site footprint — they scored as
# "ground_crash" and the site HP bar never dropped from ballistic.
# 3500 m captures the bulk of ballistic impacts while still being a
# plausible "defended area" per the original Milestone-D comment
# above. Side effect: cruise / HGV / drone also count as hits more
# often, but their CEP is much smaller (HGV ~100 m, cruise ~50 m, drone
# ~20 m) so the relative change is minor for those kinds.
#
# 2026-04-23 (W2): bumped 3500 → 5000. The 3500 m disc still cut off
# the long tail of ballistic CEP — occasional impacts at 3.8-5 km
# scored as "ground_crash" instead of damaging the site. 5000 m
# catches that tail. Issue #14's permanent fix is a Route-3 PN
# precision pass that's out of hackathon scope; this remains a
# workaround.
BASE_HIT_RADIUS = 5000.0  # metres (Issue #14 workaround, bumped W2)

# --- Red spawn band (north edge) ---
RED_SPAWN_Y = ARENA_Y - 5_000.0

# --- Integration / numeric stability ---
MIN_SPEED_SQ = 1.0       # below this, a projectile is considered stalled (m^2/s^2)
MAX_ACCEL = 600.0        # hard cap on commanded acceleration (~60G) for stability

# --- Visual/stream ---
TRAIL_LENGTH = 60        # samples client may keep; server does not cap

# --- Blue launcher layout ---
# Distributed launcher positions on the southern mainland. (x, y) in m,
# world coords. Hard-coded for now — future work hooks a placement AI
# here, but the rendering + fire path already treats this list as the
# source of truth. Keys are the wire-format InterceptorType values
# (see types.py).
#
# Positions are validated below via `terrain.point_on_south_land` against
# the Saab CSV polygons, so every launcher sits on visible land. The
# Milestone F layout had several launchers (RBS 70, SLS east, SLM west)
# landing in coastal-pocket sea because the old `y < 105_000` gate was
# far wider than the southern mainland's actual band (thin 0..~18 km
# thick strip before the strait). Milestone G re-places them on land.
#
# Milestone H Part 5 rebalance: after the out-of-arena site filter (H2)
# left 3 live targets (Main Base, Spear Point Base, Firewatch Station),
# forward launchers were moved onto the south_central_peninsula
# (Spear Point area) and south_small_island / south_forward_island to
# give area coverage against cruise + drone paths that previously flew
# past all forward envelopes. Resulting 20-match balance:
# Blue 6/20, draw 9/20, Red 5/20 (see REPORT Milestone H section).
#
# 2026-04-23 (W2): swapped to the "Slot E" demo layout — 12 launchers
# spread across the southern mainland + forward islands, with PAC-2 /
# PAC-3 / SLM pushed forward onto the south_central_peninsula so they
# can engage ballistic / cruise on the way in rather than waiting at
# the base for terminal handoff. W2 then adds 2 forward drone-lane
# layers (1 CIWS + 1 RBS-70) on top of Slot E, bringing the roster to
# 14 launchers — the Red drone swarm was reaching Spear Point /
# Firewatch before any forward CIWS or RBS-70 could engage in Slot E.
# Both new positions validated as south-side land below.
BLUE_LAUNCHER_POSITIONS = {
    # kind: [ (x, y), ... ]  — one tuple per launcher instance
    # CIWS: Slot E base trio + 1 forward-center drone catcher (W2).
    "ciws":       [(76_000,   7_000), ( 88_000, 14_000), (117_000,   7_000), ( 82_500, 95_000)],
    # RBS-70: Slot E west_small_island + east-base + 1 forward-east on
    # south_forward_island (W2). 8 km reach, point-defense for drone
    # / cruise on the east approach lane.
    "rbs_70":     [(40_000,  55_000), (132_000,  9_000), (122_500, 92_500)],
    # IRIS-T SLS: Slot E south_central_peninsula + south_forward_island.
    "iris_t_sls": [(83_000,  79_000), (125_000, 102_000)],
    # IRIS-T SLM: Slot E forward-center (peninsula north tip) + east.
    "iris_t_slm": [(79_000,  93_000), (125_000,  92_000)],
    # PAC-2: Slot E forward at (79, 90); 70 km reach covers all 3 sites
    # from forward, so ballistic / cruise enter range earlier than the
    # near-base placement of Milestone H.
    "pac_2":      [(79_000,  90_000)],
    # PAC-3: Slot E forward + back-up at east-base; primary HGV /
    # ballistic hit-to-kill platform.
    "pac_3":      [(83_000,  85_000), (100_000, 10_000)],
}

# Validate every launcher sits on visible south-side land per the Saab
# CSV. Import is lazy/deferred to the bottom of the module to avoid
# import-time circular-import concerns (terrain has no sim deps, but
# keep the config import surface clean). A future placement AI must
# re-run this check before publishing any layout.
from . import terrain  # noqa: E402
for _kind, _positions in BLUE_LAUNCHER_POSITIONS.items():
    for _x, _y in _positions:
        assert terrain.point_on_south_land(_x, _y), (
            f"BLUE_LAUNCHER_POSITIONS[{_kind!r}]: ({_x}, {_y}) is not on "
            f"south-side land in the Saab Boreal Passage map. Move it "
            f"north-west or south-east by a few km until it lands on "
            f"visible terrain."
        )
del _kind, _positions, _x, _y

# --- Red launcher layout (Milestone H Part 3) ---
# Visible Red offensive launcher positions on the north side of the
# strait. Same dict schema as `BLUE_LAUNCHER_POSITIONS`: key is a
# ThreatType value string ('drone' / 'cruise_sub'), value is a list of
# (world_x, world_y) tuples in metres. Ballistic + HGV keep their
# abstract strait-origin spawns (strategic-range assets, no visible
# launcher for the demo).
#
# Drone launchers sit on 3 north-side islands (North Strait Island
# West, North Strait Island East, North Remote Island). Cruise
# launchers sit on the north mainland and North Strait Island East
# (shared with a drone launcher; a single island can host both).
#
# All positions must pass `terrain.point_on_north_land()` — validated
# at module load below. A future placement UI can re-run this check.
RED_LAUNCHER_POSITIONS = {
    # kind (ThreatType value string): [ (x, y), ... ]
    "drone": [
        ( 59_091, 183_344),   # North Strait Island West
        (104_082, 216_156),   # North Strait Island East
        ( 27_291, 141_656),   # North Remote Island
    ],
    "cruise_sub": [
        ( 53_989, 243_750),   # North mainland (saab ~600, 300)
        (105_279, 212_500),   # North Strait Island East (2nd position)
    ],
}

# Validate every red launcher sits on north-side land. Same safety net
# as the BLUE validation above; uses the shared `terrain` module.
for _kind, _positions in RED_LAUNCHER_POSITIONS.items():
    for _x, _y in _positions:
        assert terrain.point_on_north_land(_x, _y), (
            f"RED_LAUNCHER_POSITIONS[{_kind!r}]: ({_x}, {_y}) is not on "
            f"north-side land in the Saab Boreal Passage map. Move it "
            f"inland until it lands on a visible mainland or island."
        )
del _kind, _positions, _x, _y

# --- Milestone I: win conditions + economy ---
# Each Blue-side site starts at SITE_HP_START and takes kind-tagged damage
# on every leak event. When any site's hp falls to 0, Red wins.
# Spec default. Affects `scenario.winner` only — `test_balance.py`
# classifies by leak count, not HP, so HP tuning does not move the
# balance sweep buckets. For the game-loop end condition, HP 100 means
# a single site absorbs ~2 concentrated HGV leaks (80 dmg) before
# dying; 3+ leaks on the same site (or a mix with cruise / ballistic)
# is what the match-end-on-Red logic watches for.
SITE_HP_START = 100
SITE_LEAK_DAMAGE = {
    "drone":       5,
    "cruise_sub": 15,
    "ballistic":  30,
    "hgv":        40,
}
# Starting Blue budget in USD. Sized so a typical match (25-40 interceptor
# launches, weighted toward mid-tier SLM / SLS / RBS-70 with some PAC-3 /
# PAC-2) burns roughly 30-60 % of the budget. See WEAPON_SPECS.md for
# per-interceptor `usd_cost` values; maximum full-magazine value across
# the current 9-launcher loadout is ≈ $49 M so $120 M gives real
# headroom but a wave-5 saturation can visibly tighten the bar.
BLUE_BUDGET_START = 120_000_000

# M-TIER3-RED-BUDGET (Issue #8, 2026-04-20): Red now has a finite
# spending pool, symmetric with Blue. Deducted from `world.red_budget`
# per-threat at spawn time in `red_ai.step`. Default waves
# (`build_demo_waves`) total spawn cost is ≈ $54.3 M (11 drones +
# 8 cruise + 4 ballistic + 3 hgv, see THREAT_SPECS.usd_cost), so
# $100 M gives the current wave spawner real headroom — default demo
# never hits the budget ceiling and spawn behavior is bit-for-bit
# identical to pre-Tier-3 runs. Sized loose deliberately: the future
# Red AI (Boyu) will make tactical spawn decisions against this pool,
# so the runtime just needs to expose + deduct + gate. Future-ready
# Blue-win path fires when `red_budget <= 0 AND no threats alive` — a
# no-op under the current wave spawner (red.done already fires first),
# but live for the AI-driven regime.
# TODO: tune once Boyu's Red AI lands. Balance target is "Red must
# play an efficient budget game to win".
RED_BUDGET_START = 100_000_000

# Per-launcher base cost (M-TIER2-J Part 2, Issue #6). Deducted from
# `world.blue_budget` when `add_launcher` places a new launcher during
# SETUP, refunded (clamped at BLUE_BUDGET_START) when `remove_launcher`
# takes one off the map. The default roster built from
# `BLUE_LAUNCHER_POSITIONS` is pre-paid: scenario construction does NOT
# charge base_cost, so the operator starts with the full $120 M for
# interceptors + optional roster tweaks. Default roster total base cost
# = $41.5 M (1 ciws + 2 rbs_70 + 2 iris_t_sls + 2 iris_t_slm + 1 pac_2 +
# 1 pac_3 — 9 launchers total) — net refund equals cost on removing-then-
# re-adding, so a "sell the default pac_3, buy two slm" roster edit stays
# inside budget. These are arcade game-balance numbers ("unit stats") —
# see CLAUDE.md framing note. Keys are the wire-format InterceptorType
# values. Invariant locked by `test_launcher_base_cost.py`.
# TODO: tune against balance sweep post-Hack-Day
LAUNCHER_BASE_COSTS: dict = {
    "ciws":         500_000,
    "rbs_70":     1_000_000,
    "iris_t_sls": 2_000_000,
    "iris_t_slm": 5_000_000,
    "pac_2":     10_000_000,
    "pac_3":     15_000_000,
}

# --- Strait / threat-origin geometry (Milestone G) ---
# Threats spawn *north of the strait centerline*, not relative to the
# base. Derivation: the southern mainland's north coast sits around
# Saab Y ≈ 1020, the northern mainland's south coast around Saab Y ≈
# 370. Centerline ≈ (1020 + 370) / 2 = 695 in Saab coords. Mapping
# through saabToScene (y_norm = (695 - 280) / 800 = 0.519; scene_z =
# -245 + 0.519 * 250 = -115) and then world Y = 5000 - scene_z * 1000:
# world_y ≈ 120_000 m.
STRAIT_CENTER_Y = 120_000.0  # metres, world coord. Threat spawn Y anchor.

# W14 (Issue #30, 2026-04-20): minimum Y (metres north of origin) at
# which future Red AI is allowed to spawn a ballistic or HGV threat.
# Sized so even a Mach-17 HGV has ~31 s of flight time before reaching
# a typical southern site, giving Blue AI a realistic engagement
# window. The existing `STRATEGIC_Y_BAND = [235_000, 245_000]` used
# by today's random wave spawner (in `red_ai.py`) is a narrower
# sampling range (very far back). The FLOOR is the future-AI rule;
# the BAND is the current spawner's habit — the wave spawner's sample
# always satisfies the floor by construction.
# Inclusive: y == STRATEGIC_Y_FLOOR is valid.
STRATEGIC_Y_FLOOR = 180_000.0
