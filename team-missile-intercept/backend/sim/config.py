"""Central tunable parameters for the Milestone B demo.

All physics, arena, guidance, and rendering parameters live here.
"""

# --- Arena ---
ARENA_X = 150_000.0  # east-west extent (m)
ARENA_Y = 150_000.0  # north-south extent (m)
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

# --- Red spawn band (north edge) ---
RED_SPAWN_Y = ARENA_Y - 5_000.0

# --- Integration / numeric stability ---
MIN_SPEED_SQ = 1.0       # below this, a projectile is considered stalled (m^2/s^2)
MAX_ACCEL = 600.0        # hard cap on commanded acceleration (~60G) for stability

# --- Visual/stream ---
TRAIL_LENGTH = 60        # samples client may keep; server does not cap
