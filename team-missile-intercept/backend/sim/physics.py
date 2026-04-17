"""3D physics: gravity, simplified drag, True Proportional Navigation.

Vectorized where convenient with numpy. Single-entity helpers used here —
aggregate batching happens in world.py if we need it.
"""
from typing import Tuple

import numpy as np

from . import config


def gravity_accel() -> np.ndarray:
    return np.array([0.0, 0.0, -config.GRAVITY], dtype=np.float64)


def drag_accel(vel: np.ndarray, drag_k: float) -> np.ndarray:
    """Quadratic drag: a = -k * |v| * v. Returns acceleration (m/s^2)."""
    speed = float(np.linalg.norm(vel))
    if speed < 1e-6:
        return np.zeros(3, dtype=np.float64)
    return -drag_k * speed * vel


# Scale height for exponential atmosphere model. ρ(h) = ρ_0 * exp(-h / H).
# H ≈ 8500 m matches the lower troposphere well enough for our ballistic
# /HGV altitudes (sea level → 40 km). Used for post-burnout interceptor
# glide drag so a PAC-3 coasting at 25 km decays slower than one coasting
# at 2 km. Existing threat drag_k values were hand-tuned at their flight
# altitudes so we don't retroactively apply this to them.
_ATMOSPHERE_SCALE_H = 8500.0


def air_density_ratio(altitude: float) -> float:
    """ρ(h) / ρ_0 from exponential atmosphere. Clamped to [1e-4, 1]."""
    if altitude <= 0.0:
        return 1.0
    ratio = float(np.exp(-altitude / _ATMOSPHERE_SCALE_H))
    # Floor keeps high-altitude coasting from numerically freezing drag.
    return max(1e-4, ratio)


def drag_accel_at(vel: np.ndarray, drag_k: float, altitude: float) -> np.ndarray:
    """Altitude-scaled quadratic drag. Same as drag_accel at sea level;
    falls off exponentially with altitude. Used for post-burnout
    interceptor glide so high-altitude coasts decelerate slowly."""
    speed = float(np.linalg.norm(vel))
    if speed < 1e-6:
        return np.zeros(3, dtype=np.float64)
    rho = air_density_ratio(altitude)
    return -drag_k * rho * speed * vel


def cap_accel(accel: np.ndarray, max_g: float) -> np.ndarray:
    """Clamp commanded acceleration to <= max_g * g."""
    max_a = max_g * config.GRAVITY
    mag = float(np.linalg.norm(accel))
    if mag > max_a and mag > 1e-9:
        accel = accel * (max_a / mag)
    return accel


def cap_speed(vel: np.ndarray, max_speed: float) -> np.ndarray:
    speed = float(np.linalg.norm(vel))
    if speed > max_speed and speed > 1e-9:
        vel = vel * (max_speed / speed)
    return vel


def pn_guidance_accel(
    shooter_pos: np.ndarray,
    shooter_vel: np.ndarray,
    target_pos: np.ndarray,
    target_vel: np.ndarray,
    gain: float = config.PN_GAIN,
) -> np.ndarray:
    """True Proportional Navigation command.

    a_cmd = N * |V_c| * (LOS_rate_vec x LOS_unit) cross structure
    Equivalent form used: a = N * (LOS_rate x V_rel) or more commonly
        a = N * lambda_dot * V_c  (perpendicular to LOS)

    We compute:
        r      = target - shooter
        v_rel  = target_vel - shooter_vel
        omega  = (r x v_rel) / (r . r)         (LOS angular velocity vec)
        V_c    = -(r . v_rel) / |r|            (closing speed; +ve closing)
        a_cmd  = N * V_c * (omega x r_hat)     (lateral accel perp to LOS)
    This is the standard True-PN form and stable for head-on geometries.
    """
    r = target_pos - shooter_pos
    r_mag = float(np.linalg.norm(r))
    if r_mag < 1e-3:
        return np.zeros(3, dtype=np.float64)

    v_rel = target_vel - shooter_vel
    r_hat = r / r_mag

    # LOS angular velocity
    omega = np.cross(r, v_rel) / (r_mag * r_mag)

    # Closing speed (positive when closing)
    v_c = -float(np.dot(r, v_rel)) / r_mag

    # Lateral accel perpendicular to LOS
    a_cmd = gain * v_c * np.cross(omega, r_hat)

    # Add a small boost along LOS when closing slowly (keeps mid-flight
    # interceptor from going idle on crossing geometries).
    if v_c < 100.0:
        a_cmd = a_cmd + r_hat * 80.0

    return a_cmd


def integrate(
    pos: np.ndarray,
    vel: np.ndarray,
    accel: np.ndarray,
    dt: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """Semi-implicit Euler. Keep it simple."""
    new_vel = vel + accel * dt
    new_pos = pos + new_vel * dt
    return new_pos, new_vel


def closest_approach(
    p1: np.ndarray,
    v1: np.ndarray,
    p2: np.ndarray,
    v2: np.ndarray,
    dt: float,
) -> float:
    """Minimum distance between two entities over [0, dt] given constant vel.

    Closed form: parametric distance squared minimized.
    """
    dp = p1 - p2
    dv = v1 - v2
    a = float(np.dot(dv, dv))
    if a < 1e-9:
        return float(np.linalg.norm(dp))
    b = float(np.dot(dp, dv))
    t_star = -b / a
    t_star = max(0.0, min(dt, t_star))
    closest_vec = dp + dv * t_star
    return float(np.linalg.norm(closest_vec))
