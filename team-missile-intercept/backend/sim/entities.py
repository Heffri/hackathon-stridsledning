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


# Interceptor kinds that perform a vertical VLS boost before PN takes over.
_VLS_SAM_KINDS = (
    InterceptorType.SHORT_SAM,
    InterceptorType.MED_SAM,
    InterceptorType.LONG_SAM,
)
_VLS_BOOST_DURATION = 1.5  # seconds


class Threat:
    __slots__ = (
        "state",
        "spec",
        "waypoint",
        "_wp_queue",
        "_base_alt",
        "_alt_phase",
        "_elapsed",
        "_prev_pos",
        "_prev_vel",
        "_cruise_alt_override",
    )

    def __init__(
        self,
        eid: int,
        kind: ThreatType,
        start_xy,
        target_xy,
        t_now: float,
        intermediate_waypoints=None,
    ):
        self.spec: ThreatSpec = THREAT_SPECS[kind]
        # start_xy may be (x, y) or (x, y, z). When Z is supplied it is the
        # actual spawn altitude; otherwise we fall back to spec.cruise_alt.
        spawn_z = (
            float(start_xy[2])
            if len(start_xy) >= 3
            else float(self.spec.cruise_alt)
        )
        start = np.array(
            [float(start_xy[0]), float(start_xy[1]), spawn_z], dtype=np.float64
        )
        target = np.array(
            [float(target_xy[0]), float(target_xy[1]), 0.0], dtype=np.float64
        )

        # Build the waypoint sequence: [intermediate..., final_target].
        # For cruise/drone the queue's final element is the base (target).
        # For ballistic intermediate_waypoints is ignored.
        all_wps = []
        if kind != ThreatType.BALLISTIC and intermediate_waypoints:
            for wp in intermediate_waypoints:
                wz = float(wp[2]) if len(wp) >= 3 else spawn_z
                all_wps.append(
                    np.array([float(wp[0]), float(wp[1]), wz], dtype=np.float64)
                )
        all_wps.append(target.copy())

        if kind == ThreatType.BALLISTIC:
            # Terminal-phase ballistic trajectory: solve for the launch angle
            # below horizontal that lands on the base given spawn altitude h
            # and horizontal distance d at speed v, accounting for gravity.
            #
            # Projectile motion: x = v cos(θ) t;  z = h − v sin(θ) t − ½ g t²
            # Setting z = 0 and eliminating t gives a quadratic in tan(θ):
            #     (g d² / 2 v²) tan²θ + d tan θ + (g d² / 2 v² − h) = 0
            # The positive-root (shallow-angle) solution is the natural
            # re-entry trajectory. Direct "aim at target" launches fall short
            # because the aim is steeper than the actual ballistic arc.
            dx = float(target[0] - start[0])
            dy = float(target[1] - start[1])
            dh = float(np.sqrt(dx * dx + dy * dy))
            h_drop = float(start[2])
            v = self.spec.cruise_speed

            if dh > 1.0 and h_drop > 0.0:
                # Aim ~2% past the base to counter drag-induced speed loss
                # during descent. Empirically tuned so mean impact lands
                # within a few hundred metres of the base across the 30 km
                # wide random spawn band.
                dh_aim = dh * 1.02
                k = config.GRAVITY * dh_aim * dh_aim / (2.0 * v * v)
                disc = dh_aim * dh_aim - 4.0 * k * (k - h_drop)
                if disc > 0.0:
                    tan_theta = (-dh_aim + float(np.sqrt(disc))) / (2.0 * k)
                    theta = float(np.arctan(tan_theta))
                else:
                    theta = float(np.arctan2(h_drop, dh_aim))
                horiz_unit = np.array([dx / dh, dy / dh, 0.0])
                launch_dir = (
                    horiz_unit * float(np.cos(theta))
                    + np.array([0.0, 0.0, -float(np.sin(theta))])
                )
            else:
                launch_dir = np.array([0.0, 0.0, -1.0])
            vel = launch_dir * self.spec.cruise_speed
            self.waypoint = np.array([target[0], target[1], 0.0])
            self._wp_queue = []
        else:
            # Default: head toward the first waypoint (spawn altitude
            # preserved — the altitude-hold loop will keep it there).
            first_wp = all_wps[0]
            direction = first_wp - start
            norm = float(np.linalg.norm(direction))
            if norm < 1e-6:
                direction = np.array([0.0, -1.0, 0.0])
            else:
                direction = direction / norm
            vel = direction * self.spec.cruise_speed
            self.waypoint = first_wp
            self._wp_queue = all_wps[1:]

        self.state = EntityState(
            id=eid,
            team=Team.RED,
            kind=kind.value,
            pos=start,
            vel=vel,
            spawn_t=t_now,
            color=self.spec.color,
            hp=self.spec.hp,
            hp_max=self.spec.hp,
        )
        # Spawn altitude — the cruise / drone altitude-hold targets this
        # baseline when not in pop-up or drift modes.
        self._base_alt = spawn_z
        # Phase offset so concurrently spawned drones don't all drift in
        # lockstep; deterministically derived from the entity id.
        self._alt_phase = (eid * 0.7393) % (2.0 * float(np.pi))
        # Instantaneous target cruise altitude. For CRUISE_SUB this is
        # overridden during terminal pop-up; for drones it slowly oscillates
        # around _base_alt; otherwise it follows _base_alt.
        self._cruise_alt_override = spawn_z
        # Per-threat elapsed sim time (advanced inside step). Used by the
        # drone altitude-drift sine and any future time-of-flight effects.
        self._elapsed = 0.0

    def step(self, dt: float) -> None:
        if not self.state.alive:
            return
        self._elapsed += dt
        pos = self.state.pos
        vel = self.state.vel

        # --- Ballistic: gravity-driven re-entry with weak horizontal pull ---
        if self.spec.kind == ThreatType.BALLISTIC:
            to_base_h = np.array(
                [self.waypoint[0] - pos[0], self.waypoint[1] - pos[1], 0.0],
                dtype=np.float64,
            )
            dh = float(np.linalg.norm(to_base_h))
            if dh > 1.0:
                desired_h_dir = to_base_h / dh
                h_speed = float(np.sqrt(vel[0] * vel[0] + vel[1] * vel[1]))
                desired_vel = np.array(
                    [
                        desired_h_dir[0] * h_speed,
                        desired_h_dir[1] * h_speed,
                        0.0,
                    ]
                )
                cur_h_vel = np.array([vel[0], vel[1], 0.0])
                steer = (desired_vel - cur_h_vel) / max(dt, 1e-3)
                steer = physics.cap_accel(steer, self.spec.max_g)
            else:
                steer = np.zeros(3)

            accel = steer + physics.gravity_accel()
            accel = accel + physics.drag_accel(vel, self.spec.drag_k)

            new_pos, new_vel = physics.integrate(pos, vel, accel, dt)
            # No speed cap — terminal re-entry is allowed to fly fast.
            if new_pos[2] < config.GROUND_Z:
                new_pos[2] = config.GROUND_Z
                self.state.alive = False
            self.state.pos = new_pos
            self.state.vel = new_vel
            return

        # --- Waypoint advance (cruise + drone) ---
        # When close enough horizontally to the current waypoint, switch to
        # the next one in the queue. The 3 km threshold matches the
        # cruise-class turn radius and avoids overshoot-then-loop behaviour.
        horiz_to_wp = float(
            np.sqrt(
                (self.waypoint[0] - pos[0]) ** 2
                + (self.waypoint[1] - pos[1]) ** 2
            )
        )
        if horiz_to_wp < 3_000.0 and self._wp_queue:
            self.waypoint = self._wp_queue.pop(0)
            horiz_to_wp = float(
                np.sqrt(
                    (self.waypoint[0] - pos[0]) ** 2
                    + (self.waypoint[1] - pos[1]) ** 2
                )
            )

        # --- Cruise-sub terminal pop-up (only on the final approach) ---
        # Subsonic cruise missiles pop up at ~5 km from base then dive into
        # the target from ~600 m. Trigger only when no more waypoints follow
        # so intermediate S-pattern legs stay at base altitude.
        if self.spec.kind == ThreatType.CRUISE_SUB:
            if not self._wp_queue:
                if horiz_to_wp < 1_500.0:
                    self._cruise_alt_override = 150.0
                elif horiz_to_wp < 5_000.0:
                    self._cruise_alt_override = 600.0
                else:
                    self._cruise_alt_override = self._base_alt
            else:
                self._cruise_alt_override = self._base_alt

        # Drones: hold steady at their spawn altitude during cruise, then
        # dive onto the base during the final 2 km so the drone enters the
        # base hit sphere. The earlier sine drift caused visible nose
        # bobbing — removing it and keeping the altitude flat reads far
        # calmer on screen.
        elif self.spec.kind == ThreatType.DRONE:
            if horiz_to_wp < 500.0:
                self._cruise_alt_override = 0.0
            elif horiz_to_wp < 2_000.0:
                # Smooth ramp from base altitude (at 2 km out) to ground (at
                # 500 m out).
                frac = (horiz_to_wp - 500.0) / 1_500.0
                self._cruise_alt_override = self._base_alt * frac
            else:
                self._cruise_alt_override = self._base_alt

        target_alt = self._cruise_alt_override

        # Horizontal-plane steering toward waypoint.
        to_wp = self.waypoint - pos
        to_wp[2] = 0.0
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
            steer = (desired_v - vel) / max(dt, 1e-3)
            steer = physics.cap_accel(steer, self.spec.max_g)
        else:
            steer = np.zeros(3)

        # Altitude-hold to current target altitude (gentler spring/damper
        # than the original 0.5/0.8 gains — stops drones from bobbing).
        alt_err = target_alt - pos[2]
        alt_accel = np.array([0.0, 0.0, alt_err * 0.2 - vel[2] * 0.4])

        accel = steer + alt_accel
        accel = accel + physics.drag_accel(vel, self.spec.drag_k)

        new_pos, new_vel = physics.integrate(pos, vel, accel, dt)
        new_vel = physics.cap_speed(new_vel, self.spec.cruise_speed)
        if new_pos[2] < config.GROUND_Z:
            new_pos[2] = config.GROUND_Z
            self.state.alive = False
        self.state.pos = new_pos
        self.state.vel = new_vel


class Interceptor:
    __slots__ = (
        "state",
        "spec",
        "target_id",
        "launched_t",
        "_prev_pos",
        "_prev_vel",
        "_boost_phase_end",
        "_horiz_launch_dir",
    )

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

        # Horizontal component of initial_dir (used as the boost-phase lean
        # for SAMs, and for CIWS as the actual launch direction).
        d = np.array(initial_dir, dtype=np.float64)
        d_horiz = np.array([d[0], d[1], 0.0], dtype=np.float64)
        dh_norm = float(np.linalg.norm(d_horiz))
        if dh_norm > 1e-6:
            d_horiz = d_horiz / dh_norm
        else:
            d_horiz = np.array([0.0, 1.0, 0.0])
        self._horiz_launch_dir = d_horiz

        if kind in _VLS_SAM_KINDS:
            # VLS: launch nearly straight up with a small lean toward the
            # target. PN guidance kicks in after _VLS_BOOST_DURATION.
            launch_vec = np.array(
                [0.2 * d_horiz[0], 0.2 * d_horiz[1], 1.0],
                dtype=np.float64,
            )
            launch_vec = launch_vec / float(np.linalg.norm(launch_vec))
            vel = launch_vec * (self.spec.max_speed * 0.4)
            self._boost_phase_end = t_now + _VLS_BOOST_DURATION
        else:
            # CIWS: ballistic lofted burst along initial_dir, 50% max_speed.
            n = float(np.linalg.norm(d))
            if n < 1e-6:
                d_unit = np.array([0.0, 1.0, 0.3])
                d_unit = d_unit / float(np.linalg.norm(d_unit))
            else:
                d_unit = d / n
            vel = d_unit * (self.spec.max_speed * 0.5)
            self._boost_phase_end = t_now  # already past (no boost phase)

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

    def step(self, dt: float, target_state: Optional[EntityState], t_now: float) -> None:
        if not self.state.alive:
            return

        pos = self.state.pos
        vel = self.state.vel

        # --- VLS boost phase: fly nearly vertical, ignore PN ---
        if t_now < self._boost_phase_end:
            # Target velocity: same lean-up unit vector scaled to 0.4*max.
            # Push current velocity toward it with very strong thrust so the
            # missile actually climbs before guidance engages.
            target_vec = np.array(
                [
                    0.2 * self._horiz_launch_dir[0],
                    0.2 * self._horiz_launch_dir[1],
                    1.0,
                ],
                dtype=np.float64,
            )
            target_vec = target_vec / float(np.linalg.norm(target_vec))
            target_vel = target_vec * (self.spec.max_speed * 0.7)
            a_boost = (target_vel - vel) / max(dt, 1e-3)
            # Allow much higher accel during boost to make climb snappy.
            a_boost = physics.cap_accel(a_boost, self.spec.max_g * 1.5)

            accel = a_boost + physics.gravity_accel()
            accel = accel + physics.drag_accel(vel, self.spec.drag_k)

            new_pos, new_vel = physics.integrate(pos, vel, accel, dt)
            new_vel = physics.cap_speed(new_vel, self.spec.max_speed)
            if new_pos[2] < config.GROUND_Z:
                new_pos[2] = config.GROUND_Z
                self.state.alive = False
            self.state.pos = new_pos
            self.state.vel = new_vel
            return

        # --- Post-boost: PN guidance + thrust ---
        if target_state is not None and target_state.alive:
            a_guide = physics.pn_guidance_accel(
                pos, vel, target_state.pos, target_state.vel
            )
            a_guide = physics.cap_accel(a_guide, self.spec.max_g)
        else:
            # No target — coast + light drag, will self-destruct on timeout.
            a_guide = np.zeros(3)

        speed = float(np.linalg.norm(vel))
        if speed < self.spec.max_speed and speed > 1e-3:
            # After the VLS boost the velocity points nearly vertical; a
            # pure "thrust along velocity" would fight PN for many seconds.
            # Point the sustain thrust along line-of-sight to the target so
            # the missile actually converges on the engagement geometry.
            if target_state is not None and target_state.alive:
                to_target = target_state.pos - pos
                tt_norm = float(np.linalg.norm(to_target))
                if tt_norm > 1e-6:
                    along = to_target / tt_norm
                else:
                    along = vel / speed
            else:
                along = vel / speed
            boost_mag = min(150.0, (self.spec.max_speed - speed) / max(dt, 1e-3))
            a_boost = along * boost_mag
        else:
            a_boost = np.zeros(3)

        accel = a_guide + a_boost
        accel = accel + physics.gravity_accel()
        accel = accel + physics.drag_accel(vel, self.spec.drag_k)

        new_pos, new_vel = physics.integrate(pos, vel, accel, dt)
        new_vel = physics.cap_speed(new_vel, self.spec.max_speed)

        if new_pos[2] < config.GROUND_Z:
            new_pos[2] = config.GROUND_Z
            self.state.alive = False
        self.state.pos = new_pos
        self.state.vel = new_vel
