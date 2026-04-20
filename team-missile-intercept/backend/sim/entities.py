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

# Milestone I: HGV runs straight toward its pre-selected target by
# default — no scripted S-weave, no range-gated jink, no sine pattern.
# External control comes in via `Threat.override_maneuver(turn_dir,
# g_load)` which stores a commanded lateral acceleration consumed on
# the NEXT physics step; call it every tick to maintain a sustained
# manoeuvre. This replaces Milestone D's pre-scripted evasion so the
# Red AI layer (coming after this milestone) can drive HGV trajectories
# directly without the integrator fighting a scripted waypoint queue.
#
# Physics limits are enforced regardless of the command source:
#   * commanded G clamped to `spec.max_g` (8 for HGV)
#   * quadratic KE bleed on (current_G / max_G)² — sharper turn, more
#     speed loss
#   * below `_HGV_STALL_SPEED` the glide collapses and the HGV is marked
#     dead
#
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

# M-TIER2.7 (Issue #13 option a): cruise_sub terminal-dive gate. Below
# this horizontal distance to the final waypoint, cruise switches from
# sea-skim altitude-hold to a 3D aim at the target so it actually
# reaches z=0. 5 km leaves room for max_g=2 to rotate the velocity
# downward from a 1-6 km spawn altitude without a jerky pop-down.
_CRUISE_TERMINAL_DH = 5_000.0


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
        # Milestone I: one-tick HGV manoeuvre command, np.ndarray(3) of
        # commanded lateral acceleration in m/s². Consumed + cleared in
        # Threat.step. None = no external override this tick.
        "_override_accel",
        # M-TIER1.5 (Issue #10 subtask): horizontal distance from spawn
        # to target, used to compute the constant glide-path pitch
        # (tan = _base_alt / _glide_initial_dh). HGV-only; other kinds
        # keep it at 1.0. Stored once at spawn.
        "_glide_initial_dh",
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
        """Construct a Threat at `start_xy`, aimed at `target_xy`.

        Per-kind initial velocity resolution:
          * HGV: glide-path pitch chosen so a straight glide from
            (start, spawn_z) reaches z=0 at target (x, y). Red AI
            can override per-tick via `override_maneuver`.
          * Ballistic: trajectory-solver picks a launch angle below
            horizontal that puts the gravity + drag re-entry arc
            on the target (projectile-motion quadratic in tan θ).
          * Cruise / drone: head toward first waypoint, altitude
            held by `_cruise_alt_override`; cruise_sub pops up +
            down near target, drone dives in the final 2 km.

        `start_xy` may be length-2 (z defaults to `spec.cruise_alt`)
        or length-3 (actual spawn altitude). `target_xy` is always
        length-2 (z=0 forced for ground target).

        `intermediate_waypoints` is a list of (x, y[, z]) tuples
        prepended to the target. Cruise / drone walk it; ballistic
        ignores it.

        Post-construction mutation is not supported — the waypoint
        queue, spawn position, and initial velocity are part of the
        trajectory solver's initial conditions.
        """
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

        # HGV glide-path horizontal distance, overridden below for HGV
        # spawn. Left at 1.0 for non-HGV kinds (unused by their paths).
        self._glide_initial_dh = 1.0

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
            # Milestone I + M-TIER1.5 (Issue #10 subtask):
            # constant glide-path dive toward the pre-selected target.
            # Flight-path angle chosen at spawn so a straight glide from
            # `spawn_z` lands at z = 0 at the target's (x, y). Red AI's
            # per-tick `override_maneuver(dir, g)` still wins over the
            # default when set.
            to_target_h = np.array([target[0] - start[0], target[1] - start[1], 0.0])
            norm_h = float(np.linalg.norm(to_target_h))
            if norm_h < 1e-6:
                to_target_h = np.array([0.0, -1.0, 0.0])
                norm_h = 1.0
            horiz_unit = to_target_h / norm_h
            # tan_pitch = spawn_z / initial_dh. For the Milestone I
            # spawn strip (z=30-40 km, dh=150-240 km) this is ~0.12-0.27
            # i.e. 7-15° shallow dive. Spawn with velocity already on
            # the glide line so the PD controller only has to correct
            # small integration drift during flight.
            self._glide_initial_dh = max(1.0, norm_h)
            tan_pitch = spawn_z / self._glide_initial_dh
            denom = float(np.sqrt(1.0 + tan_pitch * tan_pitch))
            vel = horiz_unit * (self.spec.cruise_speed / denom)
            vel[2] = -self.spec.cruise_speed * tan_pitch / denom
            self.waypoint = target.copy()
            self._wp_queue = []
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
        # Milestone I: no override pending by default.
        self._override_accel = None

    def override_maneuver(self, turn_direction, g_load: float) -> None:
        """Milestone I external-control hook. Stores a commanded lateral
        acceleration consumed on the NEXT `step` call; persists for
        exactly one tick so callers maintain a sustained manoeuvre by
        calling every tick.

        Args:
          turn_direction: 3-vector (list / tuple / np.ndarray) naming
            the commanded acceleration direction. Any magnitude — the
            method normalises internally. Zero-vector clears the
            override.
          g_load: desired manoeuvre load in G's. Clamped to
            `[0, self.spec.max_g]`; negative values are clamped to 0.

        Physics limits still apply after the integrator (max_g cap on
        the total commanded accel, quadratic KE bleed, 500 m/s stall).
        Intended for the Red AI layer to drive HGV trajectories; a
        no-op on non-HGV threats is fine — the field exists on every
        Threat but only the HGV step path consumes it.
        """
        dir_arr = np.array(turn_direction, dtype=np.float64).reshape(3)
        n = float(np.linalg.norm(dir_arr))
        if n < 1e-6:
            self._override_accel = None
            return
        dir_unit = dir_arr / n
        g_clamped = max(0.0, min(float(g_load), float(self.spec.max_g)))
        self._override_accel = dir_unit * (g_clamped * config.GRAVITY)

    def step(self, dt: float, world=None) -> None:
        if not self.state.alive:
            return
        self._elapsed += dt
        pos = self.state.pos
        vel = self.state.vel

        # --- HGV: unpowered glide straight to target (Milestone I) ---
        # No scripted S, no range-gated jink. External callers drive
        # lateral manoeuvre via `override_maneuver(dir, g)`, clamped to
        # spec.max_g. KE bleed + stall physics still apply.
        if self.spec.kind == ThreatType.HGV:
            wp = self.waypoint  # always the pre-selected target

            to_wp_h = np.array([wp[0] - pos[0], wp[1] - pos[1], 0.0])
            dh = float(np.linalg.norm(to_wp_h))
            if dh > 1.0:
                h_dir = to_wp_h / dh
            else:
                h_dir = np.array([0.0, -1.0, 0.0])

            # M-TIER1.5 (Issue #10): default is a constant glide-path
            # dive from spawn — target_alt descends linearly with
            # horizontal travel so a straight glide reaches z=0 exactly
            # at (x_target, y_target). Sharp 3D aim kicks in only for
            # the final 3 km or below 2 km altitude to clean up the
            # terminal impact.
            terminal_dive = dh < 3_000.0 or pos[2] < 2_000.0
            if terminal_dive:
                to_base_3d = wp - pos
                n3 = float(np.linalg.norm(to_base_3d)) or 1.0
                desired_vel = (to_base_3d / n3) * self.spec.cruise_speed
                steer = (desired_vel - vel) / max(dt, 1e-3)
                steer = physics.cap_accel(steer, self.spec.max_g)
                base_cmd = steer
                manoeuvre_cmd_mag = float(np.linalg.norm(steer))
                accel = (
                    base_cmd
                    + physics.gravity_accel()
                    + physics.drag_accel_at(vel, self.spec.drag_k, float(pos[2]))
                )
            else:
                # Horizontal steering: same cruise-speed target as before.
                desired_h_vel = h_dir * self.spec.cruise_speed
                cur_h_vel = np.array([vel[0], vel[1], 0.0])
                steer_h = (desired_h_vel - cur_h_vel) / max(dt, 1e-3)
                horiz_accel = physics.cap_accel(steer_h, self.spec.max_g)

                # Glide-path reference: target_alt = _base_alt * dh /
                # initial_dh, clamped to [0, _base_alt]. Reaches 0 at
                # target (x, y). target_vz feeds forward the descent
                # rate needed to stay on the line (−tan_pitch ×
                # horizontal_speed). PD on (alt_err, vz_err) handles
                # small drift; spawn `vel` is already on the glide
                # line so steady-state is reached immediately.
                tan_pitch = self._base_alt / self._glide_initial_dh
                glide_ratio = max(0.0, min(1.0, dh / self._glide_initial_dh))
                target_alt = self._base_alt * glide_ratio
                cur_h_speed = float(np.linalg.norm(cur_h_vel))
                target_vz = -tan_pitch * cur_h_speed
                alt_err = target_alt - pos[2]
                vz_err = target_vz - vel[2]
                alt_accel = np.array([0.0, 0.0, alt_err * 0.3 + vz_err * 0.5])

                # Aerodynamic lift cancels gravity during the glide.
                lift = np.array([0.0, 0.0, config.GRAVITY])
                base_cmd = horiz_accel + alt_accel + lift
                manoeuvre_cmd_mag = float(np.linalg.norm(horiz_accel))
                accel = (
                    base_cmd
                    + physics.gravity_accel()
                    + physics.drag_accel_at(vel, self.spec.drag_k, float(pos[2]))
                )

            # Milestone I: external `override_maneuver` command, if any.
            # Consumed + cleared so each call is good for exactly one
            # tick (Red AI must keep calling to maintain a turn).
            override_mag = 0.0
            if self._override_accel is not None:
                override = self._override_accel
                override_mag = float(np.linalg.norm(override))
                accel = accel + override
                self._override_accel = None

            new_pos, new_vel = physics.integrate(pos, vel, accel, dt)
            new_vel = physics.cap_speed(new_vel, self.spec.cruise_speed)

            # Kinetic energy bleed. Total pilot-commanded lateral load =
            # base steering + override; KE loss quadratic in the
            # combined G ratio. Cap at 1.5× max_g_accel for the ratio
            # term so a runaway override still bleeds proportionally
            # instead of saturating.
            max_accel = self.spec.max_g * config.GRAVITY
            total_cmd = manoeuvre_cmd_mag + override_mag
            total_cmd = min(total_cmd, max_accel * 1.5)
            g_ratio = total_cmd / max(max_accel, 1e-6)
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
            # Altitude-scaled drag: at 35 km spawn altitude rho ≈ 0.016,
            # so cruise drag is near zero. Dense-air drag only kicks in
            # during terminal re-entry. Matches the HGV drag model and
            # lets the projectile-motion trajectory solver at spawn land
            # close to the pre-selected target across the full 150-240 km
            # distance range. Sea-level drag here caused a consistent
            # ~17 km shortfall for the far-north Milestone I spawn strip.
            accel = accel + physics.drag_accel_at(
                vel, self.spec.drag_k, float(pos[2])
            )

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

        # --- Cruise-sub terminal dive (M-TIER2.7, Issue #13 option a) ---
        # Final-approach behaviour: cruise abandons sea-skim altitude-hold
        # and points desired_vel straight at the target's (x, y, 0)
        # position so it actually reaches ground impact. Pattern mirrors
        # HGV's terminal_dive but simpler — no glide-path angle, cruise
        # just aims directly at the 3D target. Only fires on the final
        # waypoint; intermediate S-pattern legs stay sea-skimming.
        if self.spec.kind == ThreatType.CRUISE_SUB:
            if not self._wp_queue and horiz_to_wp < _CRUISE_TERMINAL_DH:
                to_target_3d = self.waypoint - pos
                n3 = float(np.linalg.norm(to_target_3d)) or 1.0
                desired_vel = (to_target_3d / n3) * self.spec.cruise_speed
                steer = (desired_vel - vel) / max(dt, 1e-3)
                steer = physics.cap_accel(steer, self.spec.max_g)
                accel = steer + physics.drag_accel(vel, self.spec.drag_k)
                new_pos, new_vel = physics.integrate(pos, vel, accel, dt)
                new_vel = physics.cap_speed(new_vel, self.spec.cruise_speed)
                if new_pos[2] < config.GROUND_Z:
                    new_pos[2] = config.GROUND_Z
                self.state.pos = new_pos
                self.state.vel = new_vel
                return
            # Pre-terminal / intermediate legs: sea-skim at spawn altitude.
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
        # M-TIER2.5 engagement-mode infrastructure. 'prox' or 'htk'
        # string; set at construction via `spec.default_engagement_mode`
        # when the caller doesn't override. See `ENGAGEMENT_MODE_DESIGN.md`.
        "engagement_mode",
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
        engagement_mode: Optional[str] = None,
    ):
        """Construct an Interceptor.

        Launch profile per kind:
          * VLS SAMs (every kind except CIWS): near-vertical boost
            with a small horizontal lean derived from the XY
            component of `initial_dir`. PN guidance takes over at
            `t_now + _VLS_BOOST_DURATION` (1.5 s).
          * CIWS: ballistic lofted burst along the full 3-vector
            `initial_dir` at 50 % max_speed. No boost phase.

        `engagement_mode` resolution (M-TIER2.5):
          * `None` → uses `spec.default_engagement_mode` (prox for
            every SAM, htk for pac_3).
          * Explicit string → must be in `spec.engagement_mode_choices`
            or `ValueError` is raised immediately. Legal callers
            (BlueAI._fire → Launcher.fire → spawn_interceptor) all
            pre-validate via `Launcher.fire`, so a well-formed
            caller never hits this raise.

        See `ENGAGEMENT_MODE_DESIGN.md` for the full mode contract.
        """
        self.spec: InterceptorSpec = INTERCEPTOR_SPECS[kind]
        # M-TIER2.5: validate + resolve engagement_mode. `None` → spec
        # default; explicit values must be in the spec's choices or the
        # caller bug raises. Launcher.fire pre-validates the same way,
        # so a well-formed caller never hits the ValueError here.
        if engagement_mode is None:
            self.engagement_mode = self.spec.default_engagement_mode
        elif engagement_mode in self.spec.engagement_mode_choices:
            self.engagement_mode = engagement_mode
        else:
            raise ValueError(
                f"Interceptor({kind.value}): engagement_mode="
                f"{engagement_mode!r} not in choices "
                f"{self.spec.engagement_mode_choices}"
            )
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
