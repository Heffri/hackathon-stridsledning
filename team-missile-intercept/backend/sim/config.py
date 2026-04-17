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
MAX_SIM_TIME = 600.0 # safety cap (s)

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
# source of truth. y values are north-of-base distance (base_y=5000),
# keeping all launchers in the southern-half territory (y < ~105 km).
# Keys are the wire-format InterceptorType values (see types.py).
BLUE_LAUNCHER_POSITIONS = {
    # kind: [ (x, y), ... ]  — one tuple per launcher instance
    "ciws":       [(75_000,  5_000)],                         # point defence at base
    "rbs_70":     [(60_000, 25_000), (90_000, 25_000)],       # forward, spread wide
    "iris_t_sls": [(55_000, 20_000), (95_000, 20_000)],       # flanking SHORT_SAM
    "iris_t_slm": [(65_000, 15_000), (85_000, 15_000)],       # mid-field coverage
    "pac_2":      [(74_700,  8_000)],                         # near base (nudged 300 m west of centre)
    "pac_3":      [(75_300,  8_000)],                         # near base (nudged 300 m east of centre to split from PAC-2)
}

# Validate every launcher sits on our side of the strait. Base is at
# y=5000; southern-mainland band ends around y=105_000 in world coords
# (maps to the Boreal Passage southern mainland + peninsula on the
# rendered terrain). A future placement AI must respect these bounds.
_BASE_Y = BLUE_BASE_POS[1]
for _kind, _positions in BLUE_LAUNCHER_POSITIONS.items():
    for _x, _y in _positions:
        assert _BASE_Y <= _y < 105_000, (
            f"BLUE_LAUNCHER_POSITIONS[{_kind!r}]: y={_y} outside "
            f"southern-mainland band [{_BASE_Y}, 105000)"
        )
del _BASE_Y, _kind, _positions, _x, _y
