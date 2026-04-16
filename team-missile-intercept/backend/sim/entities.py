"""Threat and Interceptor entity wrappers.

Both own an EntityState and a spec. Stepping logic lives here so world.py
just iterates.
"""
from typing import Optional

import numpy as np

from . import config, physics
from .types import (
    EntityState,
    InterceptorSpec,
    InterceptorType,
    Team,
    ThreatSpec,
    ThreatType,
    THREAT_SPECS,
    INTERCEPTOR_SPECS,
)


class Threat:
    __slots__ = ("state", "spec", "waypoint", "_prev_pos", "_prev_vel")

    def __init__(self, eid: int, kind: ThreatType, start_xy, target_xy, t_now: float):
        self.spec: ThreatSpec = THREAT_SPECS[kind]
        start = np.array(
            [start_xy[0], start_xy[1], self.spec.cruise_alt], dtype=np.float64
        )
        target = np.array(
            [target_xy[0], target_xy[1], self.spec.cruise_alt], dtype=np.float64
        )
        direction = target - start
        norm = float(np.linalg.norm(direction))
        if norm < 1e-6:
            direction = np.array([0.0, -1.0, 0.0])
        else:
            direction = direction / norm
        vel = direction * self.spec.cruise_speed

        self.state = EntityState(
            id=eid,
            team=Team.RED,
            kind=kind.value,
            pos=start,
            vel=vel,
            spawn_t=t_now,
            color=self.spec.color,
        )
        self.waypoint = target  # straight-line demo — aim for base

    def step(self, dt: float) -> None:
        if not self.state.alive:
            return
        # Demo-level threat: maintain cruise alt, keep heading toward waypoint.
        # Simple horizontal-plane steering that nudges toward waypoint.
        pos = self.state.pos
        vel = self.state.vel

        to_wp = self.waypoint - pos
        to_wp[2] = 0.0  # ignore altitude component
        horiz = float(np.linalg.norm(to_wp))
        if horiz > 1.0:
            desired_h = to_wp / horiz
            desired_v = np.array(
                [
                    desired_h[0] * self.spec.cruise_speed,
                    desired_h[1] * self.spec.cruise_speed,
                    0.0,
                ]
            )
            # Gently rotate vel toward desired (cap turn accel)
            steer = (desired_v - vel) / max(dt, 1e-3)
            steer = physics.cap_accel(steer, self.spec.max_g)
        else:
            steer = np.zeros(3)

        # Altitude-hold (light): push back toward cruise_alt
        alt_err = self.spec.cruise_alt - pos[2]
        alt_accel = np.array([0.0, 0.0, alt_err * 0.5 - vel[2] * 0.8])

        accel = steer + alt_accel
        # Light drag
        accel = accel + physics.drag_accel(vel, self.spec.drag_k)

        new_pos, new_vel = physics.integrate(pos, vel, accel, dt)
        # Re-enforce speed cap so drag doesn't runaway
        new_vel = physics.cap_speed(new_vel, self.spec.cruise_speed)
        # Ground collision
        if new_pos[2] < config.GROUND_Z:
            new_pos[2] = config.GROUND_Z
            self.state.alive = False
        self.state.pos = new_pos
        self.state.vel = new_vel


class Interceptor:
    __slots__ = ("state", "spec", "target_id", "launched_t", "_prev_pos", "_prev_vel")

    def __init__(
        self,
        eid: int,
        kind: InterceptorType,
        launch_pos,
        initial_dir,
        target_id: int,
        t_now: float,
    ):
        self.spec: InterceptorSpec = INTERCEPTOR_SPECS[kind]
        pos = np.array(launch_pos, dtype=np.float64).copy()
        d = np.array(initial_dir, dtype=np.float64)
        n = float(np.linalg.norm(d))
        if n < 1e-6:
            d = np.array([0.0, 1.0, 0.3])
            n = float(np.linalg.norm(d))
        d = d / n
        # Launch at 50% of max speed for visible boost curve
        vel = d * (self.spec.max_speed * 0.5)

        self.state = EntityState(
            id=eid,
            team=Team.BLUE,
            kind=kind.value,
            pos=pos,
            vel=vel,
            target_id=target_id,
            spawn_t=t_now,
            color=self.spec.color,
        )
        self.target_id = target_id
        self.launched_t = t_now

    def step(self, dt: float, target_state: Optional[EntityState]) -> None:
        if not self.state.alive:
            return

        pos = self.state.pos
        vel = self.state.vel

        # Guidance
        if target_state is not None and target_state.alive:
            a_guide = physics.pn_guidance_accel(
                pos, vel, target_state.pos, target_state.vel
            )
            a_guide = physics.cap_accel(a_guide, self.spec.max_g)
        else:
            # No target — coast + light drag, will self-destruct on timeout.
            a_guide = np.zeros(3)

        # Simple boost: accelerate along velocity direction while under max speed
        speed = float(np.linalg.norm(vel))
        if speed < self.spec.max_speed and speed > 1e-3:
            along = vel / speed
            boost_mag = min(150.0, (self.spec.max_speed - speed) / max(dt, 1e-3))
            a_boost = along * boost_mag
        else:
            a_boost = np.zeros(3)

        accel = a_guide + a_boost
        # Gravity and drag
        accel = accel + physics.gravity_accel()
        accel = accel + physics.drag_accel(vel, self.spec.drag_k)

        new_pos, new_vel = physics.integrate(pos, vel, accel, dt)
        new_vel = physics.cap_speed(new_vel, self.spec.max_speed)

        if new_pos[2] < config.GROUND_Z:
            new_pos[2] = config.GROUND_Z
            self.state.alive = False
        self.state.pos = new_pos
        self.state.vel = new_vel
