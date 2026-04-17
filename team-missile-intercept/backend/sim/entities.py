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
    InterceptorType.IRIS_T_SLS,
    InterceptorType.MED_SAM,
    InterceptorType.LONG_SAM,
    InterceptorType.HIT_TO_KILL,
)
_VLS_BOOST_DURATION = 1.5  # seconds

# HGV scripted manoeuvre — two virtual waypoints laterally offset from the
# spawn→base line. PN homes on each in turn, producing a wide S with the
# HGV's full max_g (10 G) — the sharp mid-course weave that makes an HGV
# visually distinct from a ballistic re-entry. Final leg is PN onto the
# base for the terminal dive.
_HGV_S_OFFSET_M = 15_000.0     # ±15 km lateral deviation per leg
_HGV_WP_SWITCH_RADIUS = 8_000.0  # horizontal distance to advance to next wp

# Level-5 evasive manoeuvre — HGV jinks when an interceptor closes inside
# this radius. Gives a visible defensive reaction and couples with the
# energy-bleed model (sharper jinks cost more speed, tactical tension).
_HGV_DETECT_RADIUS = 12_000.0    # m
_HGV_JINK_G = 8.0                # g's of lateral evasion accel

# Hypersonic speed / energy model. A manoeuvring HGV bleeds kinetic
# energy at roughly bleed_rate × (current_G / max_G)² per second. Below
# _HGV_STALL_SPEED it can no longer generate lift and falls out of its
# glide (we just mark it dead; ground-collision finishes the visual).
_HGV_BLEED_RATE = 120.0         # m/s per second at max_g — higher than the
                                 # WEAPON_SPECS 50 m/s/s because at Mach 17
                                 # the quadratic drag + turn-induced drag
                                 # realistically pulls the HGV down much
                                 # faster during evasion, and the demo
                                 # needs visible speed loss so the turn
                                 # radius (R = v²/a) tightens as manoeuvres
                                 # accumulate. 120 gives 5 s of max-G
                                 # jinking = ~600 m/s loss (~10 % of peak).
_HGV_STALL_SPEED = 500.0        # m/s floor below which the HGV crashes


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

        if kind == ThreatType.HGV:
            # Hypersonic glide: PN-guide toward two virtual waypoints
            # offset ±15 km laterally from the spawn→base line at the
            # glide altitude, then PN onto the base. This produces a wide
            # S with the HGV's full max_g instead of a flat sinusoid.
            to_target_h = np.array([target[0] - start[0], target[1] - start[1], 0.0])
            norm_h = float(np.linalg.norm(to_target_h))
            if norm_h < 1e-6:
                to_target_h = np.array([0.0, -1.0, 0.0])
                norm_h = 1.0
            horiz_unit = to_target_h / norm_h
            # Left-hand perpendicular in the XY plane.
            perp = np.array([-horiz_unit[1], horiz_unit[0], 0.0])
            # Two waypoints at 1/3 and 2/3 along the path, on opposite
            # sides. Keep their altitude at the spawn altitude so PN pulls
            # the HGV along the horizontal S rather than down.
            wp1 = start + horiz_unit * (norm_h * (1.0 / 3.0)) + perp * _HGV_S_OFFSET_M
            wp1[2] = spawn_z
            wp2 = start + horiz_unit * (norm_h * (2.0 / 3.0)) - perp * _HGV_S_OFFSET_M
            wp2[2] = spawn_z
            vel = horiz_unit * self.spec.cruise_speed
            vel[2] = -80.0
            self.waypoint = wp1
            self._wp_queue = [wp2, target.copy()]
        elif kind == ThreatType.BALLISTIC:
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

    def step(self, dt: float, world=None) -> None:
        if not self.state.alive:
            return
        self._elapsed += dt
        pos = self.state.pos
        vel = self.state.vel

        # --- HGV: unpowered glide with Level-5 evasion + kinetic bleed ---
        # Real HGVs coast on re-entry kinetic energy; no main propulsion
        # remains in the glide phase. Pursuit-steered virtual waypoints
        # produce a wide S, terminal dive aims at the base in 3D. When
        # an interceptor closes inside _HGV_DETECT_RADIUS we add a
        # lateral jink — the defensive reaction costs energy via the
        # same (current_G / max_G)² bleed that drives all manoeuvre
        # losses, so sharp evasion trades future speed for momentary
        # safety.
        if self.spec.kind == ThreatType.HGV:
            wp = self.waypoint
            if self._wp_queue:
                next_wp = self._wp_queue[0]
                from_wp_to_next_h = np.array(
                    [next_wp[0] - wp[0], next_wp[1] - wp[1], 0.0]
                )
                nwp_n = float(np.linalg.norm(from_wp_to_next_h))
                if nwp_n > 1e-6:
                    axis = from_wp_to_next_h / nwp_n
                    pos_from_wp = np.array([pos[0] - wp[0], pos[1] - wp[1], 0.0])
                    if float(np.dot(pos_from_wp, axis)) > 0.0:
                        self.waypoint = self._wp_queue.pop(0)
                        wp = self.waypoint

            terminal = not self._wp_queue  # current wp is the base

            to_wp_h = np.array([wp[0] - pos[0], wp[1] - pos[1], 0.0])
            dh = float(np.linalg.norm(to_wp_h))
            if dh > 1.0:
                h_dir = to_wp_h / dh
            else:
                h_dir = np.array([0.0, -1.0, 0.0])
            desired_h_vel = h_dir * self.spec.cruise_speed
            cur_h_vel = np.array([vel[0], vel[1], 0.0])
            steer_h = (desired_h_vel - cur_h_vel) / max(dt, 1e-3)

            if terminal and dh < 30_000.0:
                to_base_3d = wp - pos
                n3 = float(np.linalg.norm(to_base_3d)) or 1.0
                desired_vel = (to_base_3d / n3) * self.spec.cruise_speed
                steer = (desired_vel - vel) / max(dt, 1e-3)
                steer = physics.cap_accel(steer, self.spec.max_g)
                accel = steer
                accel = accel + physics.gravity_accel()
                accel = accel + physics.drag_accel_at(vel, self.spec.drag_k, float(pos[2]))
            else:
                target_alt = self._base_alt
                alt_err = target_alt - pos[2]
                alt_accel = np.array([0.0, 0.0, alt_err * 0.3 - vel[2] * 0.5])
                horiz_accel = physics.cap_accel(steer_h, self.spec.max_g)
                # Lift cancels gravity during the glide (aerodynamic
                # lift, not propulsion).
                lift = np.array([0.0, 0.0, config.GRAVITY])
                accel = horiz_accel + alt_accel + lift
                accel = accel + physics.gravity_accel()
                accel = accel + physics.drag_accel_at(vel, self.spec.drag_k, float(pos[2]))

            # Level-5 evasion: if an interceptor is within detect radius,
            # add a lateral jink perpendicular to the threat line-of-sight.
            # Direction alternates every 2 s so the HGV snakes rather than
            # arcing steadily.
            jink_added = False
            if world is not None and getattr(world, "interceptors", None):
                nearest_d2 = float("inf")
                nearest = None
                for inter in world.interceptors.values():
                    if not inter.state.alive:
                        continue
                    dv = inter.state.pos - pos
                    d2 = float(np.dot(dv, dv))
                    if d2 < nearest_d2:
                        nearest_d2 = d2
                        nearest = inter
                if nearest is not None and nearest_d2 < _HGV_DETECT_RADIUS * _HGV_DETECT_RADIUS:
                    los = nearest.state.pos - pos
                    los_h = np.array([los[0], los[1], 0.0])
                    los_h_n = float(np.linalg.norm(los_h))
                    if los_h_n > 1e-6:
                        los_h_unit = los_h / los_h_n
                        perp = np.array([-los_h_unit[1], los_h_unit[0], 0.0])
                        side = 1.0 if (int(self._elapsed) % 4) < 2 else -1.0
                        jink = perp * side * (_HGV_JINK_G * config.GRAVITY)
                        accel = accel + jink
                        jink_added = True

            new_pos, new_vel = physics.integrate(pos, vel, accel, dt)
            new_vel = physics.cap_speed(new_vel, self.spec.cruise_speed)

            # Kinetic energy bleed from manoeuvring. Use the magnitude of
            # the commanded horizontal + jink accel (exclude gravity &
            # drag which aren't pilot inputs). Bleed rate is quadratic
            # in G ratio — cruising straight loses almost nothing, max-G
            # jinking bleeds the full _HGV_BLEED_RATE per second.
            max_accel = self.spec.max_g * config.GRAVITY
            # Approximate manoeuvre accel: horizontal steer + (jink if any).
            # cap already applied, so magnitude <= max_accel for steer
            # alone; jink can push it above. We measure actual command.
            manoeuvre_accel_mag = float(np.linalg.norm(steer if (terminal and dh < 30_000.0) else horiz_accel))
            if jink_added:
                manoeuvre_accel_mag = min(max_accel * 1.5, manoeuvre_accel_mag + _HGV_JINK_G * config.GRAVITY)
            g_ratio = manoeuvre_accel_mag / max(max_accel, 1e-6)
            speed_loss = _HGV_BLEED_RATE * g_ratio * g_ratio * dt
            nv_mag = float(np.linalg.norm(new_vel))
            if nv_mag > speed_loss:
                new_vel = new_vel * ((nv_mag - speed_loss) / nv_mag)

            self.state.pos = new_pos
            self.state.vel = new_vel

            # Stall: below _HGV_STALL_SPEED, aerodynamic lift collapses
            # and the HGV falls. Mark dead; ground-collision sweep
            # elsewhere emits the explosion visual.
            if float(np.linalg.norm(new_vel)) < _HGV_STALL_SPEED:
                self.state.alive = False
            return

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
            # Defensive Z-clamp; actual ground-impact handling is
            # centralised in World.step so every entity dies the same
            # way (explosion + leak bookkeeping).
            if new_pos[2] < config.GROUND_Z:
                new_pos[2] = config.GROUND_Z
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
                    self._cruise_alt_override = 300.0
                elif horiz_to_wp < 5_000.0:
                    self._cruise_alt_override = 800.0
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
        # Defensive Z-clamp; World.step handles ground-impact kills.
        if new_pos[2] < config.GROUND_Z:
            new_pos[2] = config.GROUND_Z
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
        "_burnout_flagged",
    )

    # Stall speed below which an unpowered interceptor loses aerodynamic
    # control and self-destructs. Real SAMs transition from skin-lift
    # aerodynamics to an uncontrolled tumble around 150-250 m/s; we use
    # 200 m/s as the cutoff.
    _STALL_SPEED = 200.0

    # Coast-phase manoeuvre cap as a fraction of the powered spec.max_g.
    # Real powered SAMs pull 20-60 G via thrust-vector control + fins;
    # after burnout the main motor is gone but the aerodynamic fins +
    # attitude control motors on PAC-3/ESSM class interceptors still
    # give roughly half the powered authority. 0.5 also keeps the demo
    # reachable — 1/3 tanked Blue win rate into the 20s.
    _COAST_G_FRACTION = 0.5

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
            thrust_active=True,  # motor is lit at launch
        )
        self.target_id = target_id
        self.launched_t = t_now
        self._burnout_flagged = False

    def step(self, dt: float, target_state: Optional[EntityState], t_now: float) -> None:
        if not self.state.alive:
            return

        pos = self.state.pos
        vel = self.state.vel

        fuel_elapsed = t_now - self.launched_t
        powered = fuel_elapsed < self.spec.fuel_s
        self.state.thrust_active = powered

        # --- VLS boost phase: fly nearly vertical, ignore PN ---
        # (Always powered — fuel_s is larger than _VLS_BOOST_DURATION for
        # every interceptor type, so we don't need to gate boost on fuel.)
        if t_now < self._boost_phase_end:
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
            self.state.pos = new_pos
            self.state.vel = new_vel
            return

        # --- Post-boost: PN guidance, possibly in coast (unpowered) mode ---
        if target_state is not None and target_state.alive:
            a_guide = physics.pn_guidance_accel(
                pos, vel, target_state.pos, target_state.vel
            )
            g_cap = self.spec.max_g if powered else self.spec.max_g * self._COAST_G_FRACTION
            a_guide = physics.cap_accel(a_guide, g_cap)
        else:
            a_guide = np.zeros(3)

        speed = float(np.linalg.norm(vel))
        a_boost = np.zeros(3)
        if powered and speed < self.spec.max_speed and speed > 1e-3:
            # Sustain thrust along line-of-sight to the target so the
            # missile actually converges on the engagement geometry
            # rather than fighting PN for many seconds.
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

        accel = a_guide + a_boost
        accel = accel + physics.gravity_accel()
        # Powered flight uses sea-level-tuned drag_k. Coast applies the
        # exponential atmosphere so a Patriot coasting at 25 km doesn't
        # decelerate like it would at 2 km.
        if powered:
            accel = accel + physics.drag_accel(vel, self.spec.drag_k)
        else:
            accel = accel + physics.drag_accel_at(vel, self.spec.drag_k, float(pos[2]))

        new_pos, new_vel = physics.integrate(pos, vel, accel, dt)
        # Cap speed: powered flight to max_speed; coast just can't gain.
        if powered:
            new_vel = physics.cap_speed(new_vel, self.spec.max_speed)

        if new_pos[2] < config.GROUND_Z:
            new_pos[2] = config.GROUND_Z
        self.state.pos = new_pos
        self.state.vel = new_vel

        # Stall: coast speed below _STALL_SPEED → no more controllable
        # aerodynamics. Kill the interceptor; World.step will emit the
        # ground-impact flash on the next tick if it falls through the
        # floor, otherwise it leaves an explosion marker via the kill
        # branch of the CPA check (not our concern here).
        if not powered and float(np.linalg.norm(new_vel)) < self._STALL_SPEED:
            self.state.alive = False
