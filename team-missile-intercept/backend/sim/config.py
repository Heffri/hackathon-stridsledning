"""Central tunable parameters for the Milestone B demo.

All physics, arena, guidance, and rendering parameters live here.
"""

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
BASE_HIT_RADIUS = 1500.0  # metres

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
BLUE_LAUNCHER_POSITIONS = {
    # kind: [ (x, y), ... ]  — one tuple per launcher instance
    "ciws":       [(75_000,  5_000)],                          # point defence at base
    "rbs_70":     [(80_000, 73_000), ( 38_100, 50_000)],       # forward-center (Spear Point drones) + south_small_island forward-west
    "iris_t_sls": [(80_000, 70_000), (126_750, 102_093)],      # south_central_peninsula + south_forward_island
    "iris_t_slm": [(82_000, 72_000), ( 85_000,  6_000)],       # forward-center (Spear Point area) + eastern base-side
    "pac_2":      [(74_700,  8_000)],                          # near base (300 m west of centre); 70 km reach covers all 3 sites
    "pac_3":      [(75_300,  8_000)],                          # near base (300 m east of centre); primary HGV / ballistic HIT-TO-KILL
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
# Tuned so a typical match sees 3-8 leaks with an average ~20 dmg per
# leak (cruise / ballistic dominant in the current balance) — one fully
# concentrated site can die in ~3 heavy leaks, which keeps Red's wave 5
# saturation interesting without being one-shot territory.
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

# --- Strait / threat-origin geometry (Milestone G) ---
# Threats spawn *north of the strait centerline*, not relative to the
# base. Derivation: the southern mainland's north coast sits around
# Saab Y ≈ 1020, the northern mainland's south coast around Saab Y ≈
# 370. Centerline ≈ (1020 + 370) / 2 = 695 in Saab coords. Mapping
# through saabToScene (y_norm = (695 - 280) / 800 = 0.519; scene_z =
# -245 + 0.519 * 250 = -115) and then world Y = 5000 - scene_z * 1000:
# world_y ≈ 120_000 m.
STRAIT_CENTER_Y = 120_000.0  # metres, world coord. Threat spawn Y anchor.
