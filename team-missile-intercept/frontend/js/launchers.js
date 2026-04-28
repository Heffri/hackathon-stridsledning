// Per-launcher visual layer: per-kind 3D vehicle model + full-circle range ring.
//
// Each launcher kind gets a dedicated vehicle silhouette:
//   ciws       — Lvkv 90 tracked chassis, dual autocannon turret, rear radar disc
//   rbs_70     — RBS-70 NG tripod platform, launch tube, seeker optic
//   iris_t_sls — Truck with vertical launch container (2×3 tubes)
//   iris_t_slm — Larger truck, 2×2 VLS tubes + side radar mast
//   pac_2      — Long truck, tall radar dish on mast, angled missile rails
//   pac_3      — Long truck, 2×2 canister cluster, short radar mast
//
// this.box = hull mesh — raycasting + drag-drop target (drag_launchers.js).
// this.material = shared MeshStandardMaterial across all sub-meshes of the
//   vehicle so opacity (reload) and emissiveIntensity (selection) changes
//   apply to the whole vehicle at once.
//
// Range ring, setReloading, setSelected, dispose — all unchanged from
// Milestone H Part 4 contract.
import * as THREE from 'three';
import { worldToSceneXY } from './scene.js';
import { getSelectedLauncherId } from './launcher_selection.js';

// Mesh colours — matches entities.js body colours + scene.js range arc colours.
const LAUNCHER_COLORS = {
  ciws:       0xd9b36a,
  rbs_70:     0x4a8a3a,
  iris_t_sls: 0xff9944,
  iris_t_slm: 0xff8c1a,
  pac_2:      0xff69b4,
  pac_3:      0xa855f7,
};

// Per-kind max_range (km). Mirrors backend INTERCEPTOR_SPECS.max_range / 1000.
const RANGE_KM = {
  ciws:       4,
  rbs_70:     9,
  iris_t_sls: 12,
  iris_t_slm: 40,
  pac_2:      70,
  pac_3:      60,
};

const BOX_OPACITY_READY  = 1.0;
const BOX_OPACITY_RELOAD = 0.5;
const ARC_OPACITY_READY  = 0.4;
const ARC_OPACITY_RELOAD = 0.15;

class LauncherMesh {
  constructor(scene, kind, sx, sz, launcherId) {
    this.kind = kind;
    this.launcherId = launcherId;
    const color = LAUNCHER_COLORS[kind] ?? 0xffffff;

    // Group positioned at the launcher's world position.
    // userData.launcherId and userData.dragging are consumed by drag_launchers.js.
    this.group = new THREE.Group();
    this.group.position.set(sx, 0, sz);
    // Scale vehicles up so they're readable from the pulled-back camera.
    this.group.scale.setScalar(1.5);
    this.group.userData.launcherId = launcherId;
    this.group.userData.dragging = false;

    // Shared material across all vehicle sub-meshes. transparent:true so
    // setReloading() can dim the whole vehicle via opacity. emissiveIntensity
    // bumped by setSelected() to highlight the clicked launcher.
    this.material = new THREE.MeshStandardMaterial({
      color,
      emissive: color,
      emissiveIntensity: 0.35,
      roughness: 0.5,
      metalness: 0.2,
      transparent: true,
      opacity: BOX_OPACITY_READY,
    });

    // Build per-kind vehicle. Sets this.box (hull mesh = raycast target).
    this._buildVehicle(kind);

    // Invisible hit volume for drag_launchers.js (makes small weapons like RBS-70 easy to grab).
    // r=3.0 × group scale 1.5 = 4.5 km effective radius, h=5.0×1.5 = 7.5 km tall.
    const hitGeo = new THREE.CylinderGeometry(3.0, 3.0, 5.0, 12);
    const hitMat = new THREE.MeshBasicMaterial({ visible: false });
    this.hitMesh = new THREE.Mesh(hitGeo, hitMat);
    this.hitMesh.position.set(0, 2.5, 0);
    this.group.add(this.hitMesh);

    // Full-circle range ring in local coords centred on group origin.
    const rKm = RANGE_KM[kind] ?? 4;
    const segments = 192;
    const pts = [];
    for (let i = 0; i <= segments; i++) {
      const theta = (i / segments) * Math.PI * 2;
      pts.push(new THREE.Vector3(
        Math.cos(theta) * rKm,
        0.35,
        -Math.sin(theta) * rKm,
      ));
    }
    const arcGeom = new THREE.BufferGeometry().setFromPoints(pts);
    this.arcMaterial = new THREE.LineBasicMaterial({
      color,
      transparent: true,
      opacity: ARC_OPACITY_READY,
    });
    this.arc = new THREE.Line(arcGeom, this.arcMaterial);
    this.group.add(this.arc);

    scene.add(this.group);
  }

  // Convenience: create mesh with shared material, position+rotate it,
  // add to group. Returns the mesh so caller can assign to this.box if needed.
  _mk(geom, x = 0, y = 0, z = 0, rx = 0, ry = 0, rz = 0) {
    const m = new THREE.Mesh(geom, this.material);
    m.position.set(x, y, z);
    if (rx || ry || rz) m.rotation.set(rx, ry, rz);
    this.group.add(m);
    return m;
  }

  _buildVehicle(kind) {
    // ── Shared material helpers ───────────────────────────────────────────
    // darkMat: chassis undercarriage, grilles, exhausts, dark trim
    const darkMat = new THREE.MeshStandardMaterial({
      color: 0x181e24, roughness: 0.85, metalness: 0.15,
    });
    // glassMat: windscreens, side windows
    const glassMat = new THREE.MeshStandardMaterial({
      color: 0x3a6080, roughness: 0.1, metalness: 0.7,
      transparent: true, opacity: 0.65,
    });
    // tyreMat: black rubber wheels/tracks
    const tyreMat = new THREE.MeshStandardMaterial({
      color: 0x151515, roughness: 0.98, metalness: 0.0,
    });
    // hubMat: bright metal wheel hubs
    const hubMat = new THREE.MeshStandardMaterial({
      color: 0x888890, roughness: 0.4, metalness: 0.7,
    });

    // mkM: add mesh with explicit material
    const mkM = (geom, mat, x=0, y=0, z=0, rx=0, ry=0, rz=0) => {
      const m = new THREE.Mesh(geom, mat);
      m.position.set(x, y, z);
      if (rx||ry||rz) m.rotation.set(rx, ry, rz);
      this.group.add(m); return m;
    };

    // addAxle: pair of tyres + hubs on left & right at given position.
    // Wheel axle runs along Z (perpendicular to vehicle forward = X), so the
    // Three.js CylinderGeometry (default axis = Y) gets `rx = π/2` — a prior
    // version used `rz = π/2` which spun the axle along X, giving upright
    // tyre discs that read as drums on end from the side view.
    const addAxle = (x, y, z, tyreR=0.22, tyreW=0.14, spread=0.52) => {
      for (const side of [-1, 1]) {
        const sz = z + side * spread;
        mkM(new THREE.CylinderGeometry(tyreR, tyreR, tyreW, 16), tyreMat, x, y, sz, Math.PI/2, 0, 0);
        mkM(new THREE.CylinderGeometry(tyreR*0.5, tyreR*0.5, tyreW*1.1, 8), hubMat, x, y, sz, Math.PI/2, 0, 0);
      }
    };

    // buildCab: standard military truck cab at given X centre, Y base, Z width
    const buildCab = (cx, cabW, cabH, cabD) => {
      // Main cab box
      this._mk(new THREE.BoxGeometry(cabW, cabH, cabD), cx, cabH/2 + 0.48, 0);
      // Angled windscreen
      mkM(new THREE.BoxGeometry(cabW*0.9, cabH*0.38, 0.04), glassMat,
          cx - cabW*0.04, cabH*0.72 + 0.48, 0, 0, 0, -0.25);
      // Side windows
      mkM(new THREE.BoxGeometry(cabW*0.45, cabH*0.32, 0.04), glassMat,
          cx + cabW*0.08, cabH*0.68 + 0.48, -cabD/2 - 0.01);
      mkM(new THREE.BoxGeometry(cabW*0.45, cabH*0.32, 0.04), glassMat,
          cx + cabW*0.08, cabH*0.68 + 0.48,  cabD/2 + 0.01);
      // Grille face
      mkM(new THREE.BoxGeometry(0.05, cabH*0.55, cabD*0.94), darkMat,
          cx - cabW/2 - 0.02, cabH*0.3 + 0.48, 0);
      // Bumper bar
      this._mk(new THREE.BoxGeometry(0.06, 0.08, cabD*1.05), cx - cabW/2 - 0.02, 0.52, 0);
      // Headlights
      mkM(new THREE.CylinderGeometry(0.07, 0.07, 0.05, 10), glassMat,
          cx - cabW/2 - 0.02, 0.60, -cabD*0.35, Math.PI/2, 0, 0);
      mkM(new THREE.CylinderGeometry(0.07, 0.07, 0.05, 10), glassMat,
          cx - cabW/2 - 0.02, 0.60,  cabD*0.35, Math.PI/2, 0, 0);
      // Exhaust stack (right side)
      this._mk(new THREE.CylinderGeometry(0.032, 0.032, cabH*0.8, 6),
          cx + cabW*0.1, cabH*0.9 + 0.48, cabD/2 + 0.04);
      // Wing mirror arms
      this._mk(new THREE.BoxGeometry(0.16, 0.02, 0.02),
          cx - cabW*0.28, cabH*0.7 + 0.48, -cabD/2 - 0.09);
      this._mk(new THREE.BoxGeometry(0.16, 0.02, 0.02),
          cx - cabW*0.28, cabH*0.7 + 0.48,  cabD/2 + 0.09);
      mkM(new THREE.BoxGeometry(0.04, 0.16, 0.10), glassMat,
          cx - cabW*0.28 - 0.10, cabH*0.7 + 0.48, -cabD/2 - 0.12);
      mkM(new THREE.BoxGeometry(0.04, 0.16, 0.10), glassMat,
          cx - cabW*0.28 - 0.10, cabH*0.7 + 0.48,  cabD/2 + 0.12);
    };

    if (kind === 'ciws') {
      // ── Lvkv 90 / SPAAG — low tracked hull, prominent twin cannons ──
      // Main hull: low and wide
      const hullH = 0.46, hullL = 1.60, hullW = 1.05;
      this.box = this._mk(new THREE.BoxGeometry(hullL, hullH, hullW), 0, hullH/2, 0);
      // Sloped glacis (front armour plate, angled ~35°)
      this._mk(new THREE.BoxGeometry(0.30, 0.42, hullW), -hullL/2 + 0.05, 0.34, 0, -0.60, 0, 0);
      // Engine deck hump (raised rear third)
      this._mk(new THREE.BoxGeometry(0.42, 0.12, hullW*0.88), hullL/2 - 0.25, hullH + 0.06, 0);
      // Track assemblies — wide flat plates either side, lower than hull
      for (const s of [-1, 1]) {
        // Track outer plate
        mkM(new THREE.BoxGeometry(hullL, 0.42, 0.12), tyreMat, 0, 0.21, s * (hullW/2 + 0.06));
        // Track top cover (sloped fender)
        this._mk(new THREE.BoxGeometry(hullL, 0.06, 0.14), 0, hullH, s * (hullW/2 + 0.07));
        // Road wheels (5 per side, visible below hull). Axle along Z matches
        // addAxle() — see its comment for why rx is used instead of rz.
        for (let i = 0; i < 5; i++) {
          const wx = -hullL/2 + 0.18 + i * 0.30;
          mkM(new THREE.CylinderGeometry(0.155, 0.155, 0.10, 12), tyreMat,
              wx, 0.12, s*(hullW/2+0.06), Math.PI/2, 0, 0);
          mkM(new THREE.CylinderGeometry(0.07, 0.07, 0.11, 8), hubMat,
              wx, 0.12, s*(hullW/2+0.06), Math.PI/2, 0, 0);
        }
        // Drive sprocket front, idler rear
        mkM(new THREE.CylinderGeometry(0.18, 0.18, 0.10, 10), this.material,
            -hullL/2 + 0.04, 0.18, s*(hullW/2+0.06), Math.PI/2, 0, 0);
        mkM(new THREE.CylinderGeometry(0.16, 0.16, 0.10, 10), this.material,
             hullL/2 - 0.04, 0.14, s*(hullW/2+0.06), Math.PI/2, 0, 0);
      }
      // Turret base ring
      this._mk(new THREE.CylinderGeometry(0.32, 0.34, 0.10, 12), 0, hullH + 0.05, 0);
      // Turret body (hexagonal profile)
      this._mk(new THREE.CylinderGeometry(0.30, 0.31, 0.22, 6), 0, hullH + 0.21, 0);
      // Turret front mantlet
      this._mk(new THREE.BoxGeometry(0.18, 0.24, 0.34), -0.22, hullH + 0.20, 0);
      // ── Twin 40mm autocannon barrels (most distinctive feature) ──
      for (const s of [-0.11, 0.11]) {
        // Barrel tube
        this._mk(new THREE.CylinderGeometry(0.042, 0.034, 1.05, 8),
            s, hullH + 0.50, -0.35, Math.PI/2, 0, 0);
        // Muzzle brake
        this._mk(new THREE.CylinderGeometry(0.058, 0.042, 0.07, 8),
            s, hullH + 0.50, -0.87, Math.PI/2, 0, 0);
      }
      // Commander cupola (small dome top-left of turret)
      this._mk(new THREE.CylinderGeometry(0.09, 0.10, 0.10, 8), -0.14, hullH + 0.42, 0.16);
      this._mk(new THREE.SphereGeometry(0.09, 8, 5, 0, Math.PI*2, 0, Math.PI/2),
          -0.14, hullH + 0.52, 0.16);
      // Rear tracking radar mast + array
      this._mk(new THREE.CylinderGeometry(0.024, 0.024, 0.44, 5),  0.60, hullH + 0.22, 0);
      this._mk(new THREE.BoxGeometry(0.38, 0.28, 0.05), 0.60, hullH + 0.52, 0, 0.32, 0, 0);
      // Antenna rod
      this._mk(new THREE.CylinderGeometry(0.008, 0.008, 0.55, 4), -0.56, hullH + 0.50, 0.42);

    } else if (kind === 'rbs_70') {
      // ── RBS-70 NG — ground tripod + prominent angled launch tube ──
      // Wide flat base to stabilise the tripod visually
      this.box = this._mk(new THREE.CylinderGeometry(0.08, 0.10, 0.05, 8), 0, 0.025, 0);
      // Three legs radiating at 120°, flat on ground, foot pads visible
      for (let i = 0; i < 3; i++) {
        const a = (i / 3) * Math.PI * 2 + Math.PI / 2;
        const lx = Math.cos(a) * 0.48; const lz = Math.sin(a) * 0.48;
        // Leg tube
        this._mk(new THREE.CylinderGeometry(0.038, 0.038, 0.68, 6),
            lx * 0.5, 0.06, lz * 0.5, 0, -a + Math.PI/2, Math.PI/9);
        // Foot pad (flat disc)
        this._mk(new THREE.CylinderGeometry(0.10, 0.12, 0.03, 8), lx, 0.015, lz);
        // Lower brace bar connecting leg to centre
        this._mk(new THREE.BoxGeometry(0.05, 0.03, 0.24), lx*0.7, 0.03, lz*0.7, 0, -a + Math.PI/2, 0);
      }
      // Central pivot column
      this._mk(new THREE.CylinderGeometry(0.08, 0.10, 0.32, 8), 0, 0.22, 0);
      // Traversing ring
      this._mk(new THREE.CylinderGeometry(0.16, 0.17, 0.06, 12), 0, 0.41, 0);
      // Elevation yoke (two side arms)
      for (const s of [-0.12, 0.12]) {
        this._mk(new THREE.BoxGeometry(0.06, 0.34, 0.06), s, 0.60, 0);
      }
      // ── Launch tube — most distinctive feature, angled ~45° forward-up ──
      this._mk(new THREE.CylinderGeometry(0.10, 0.096, 1.10, 10),
          0, 0.74, -0.32, -Math.PI * 0.26, 0, 0);
      // Tube front cap (seeker window)
      this._mk(new THREE.SphereGeometry(0.10, 10, 8), 0, 1.10, -0.70);
      // Tube rear cap (motor exhaust bell)
      this._mk(new THREE.CylinderGeometry(0.10, 0.14, 0.08, 10),
          0, 0.38, 0.08, -Math.PI * 0.26 + Math.PI, 0, 0);
      // Electronics/battery box
      this._mk(new THREE.BoxGeometry(0.24, 0.18, 0.22), 0.18, 0.05, 0.28);
      // Gunner seat (foldout)
      mkM(new THREE.BoxGeometry(0.28, 0.05, 0.30), darkMat, 0, 0.40, 0.36);
      mkM(new THREE.BoxGeometry(0.28, 0.26, 0.04), darkMat, 0, 0.55, 0.50);
      // IFF interrogator antenna (thin rod, side)
      this._mk(new THREE.CylinderGeometry(0.008, 0.008, 0.40, 4), 0.22, 0.68, 0.12);

    } else if (kind === 'iris_t_sls') {
      // ── IRIS-T SLS — 4×4 military truck with vertical launch pod ──
      // Silhouette: compact cab + tall VLS tube cluster behind it
      const chL = 1.75, chH = 0.44, chW = 0.88;
      // Chassis rail
      this.box = this._mk(new THREE.BoxGeometry(chL, chH, chW), 0, chH/2, 0);
      // Cab (front 35% of vehicle)
      buildCab(-0.55, 0.56, 0.55, chW);
      // Axles: front steer + rear drive
      addAxle(-0.68, 0.22, 0, 0.20, 0.12, 0.50);
      addAxle( 0.38, 0.22, 0, 0.20, 0.12, 0.50);
      // ── VLS launch container — KEY recognition feature ──
      // Base container (armoured steel box)
      this._mk(new THREE.BoxGeometry(0.80, 0.55, chW*0.95), 0.36, chH + 0.275, 0);
      // 8 vertical launch tubes in 2×4 grid, clearly protruding above container
      for (let col = 0; col < 2; col++) {
        for (let row = 0; row < 4; row++) {
          const tx = 0.05 + (col - 0.5) * 0.28;
          const tz = (row - 1.5) * 0.18;
          // Tube body
          this._mk(new THREE.CylinderGeometry(0.062, 0.062, 0.78, 8),
              tx, chH + 0.55 + 0.39, tz);
          // Tube mouth flange
          this._mk(new THREE.CylinderGeometry(0.075, 0.062, 0.032, 8),
              tx, chH + 0.55 + 0.80, tz);
        }
      }
      // Rear stabiliser legs (deployed)
      for (const s of [-1, 1]) {
        mkM(new THREE.BoxGeometry(0.06, 0.40, 0.06), darkMat, 0.82, 0.20, s * 0.30, Math.PI*0.08, 0, 0);
        mkM(new THREE.CylinderGeometry(0.06, 0.08, 0.03, 8), darkMat, 0.82, 0.005, s * 0.36);
      }
      // Cab-roof sensor dome
      this._mk(new THREE.SphereGeometry(0.10, 8, 6, 0, Math.PI*2, 0, Math.PI/2),
          -0.62, 1.06, 0);

    } else if (kind === 'iris_t_slm') {
      // ── IRIS-T SLM — 8×8 heavy truck with tall VLS pod + radar ──
      const chL = 2.05, chH = 0.48, chW = 0.96;
      this.box = this._mk(new THREE.BoxGeometry(chL, chH, chW), 0, chH/2, 0);
      buildCab(-0.68, 0.60, 0.60, chW);
      // 4 axles (8×8)
      addAxle(-0.88, 0.24, 0, 0.21, 0.13, 0.53);
      addAxle(-0.38, 0.24, 0, 0.21, 0.13, 0.53);
      addAxle( 0.38, 0.24, 0, 0.21, 0.13, 0.53);
      addAxle( 0.84, 0.24, 0, 0.21, 0.13, 0.53);
      // ── Tall VLS pod — KEY feature, clearly taller than PAC-3 canisters ──
      this._mk(new THREE.BoxGeometry(0.90, 0.62, chW*0.92), 0.28, chH + 0.31, 0);
      // 4 large tubes (2×2) — bigger diameter than SLS, fewer tubes
      for (let col = 0; col < 2; col++) {
        for (let row = 0; row < 2; row++) {
          const tx = 0.10 + (col - 0.5) * 0.34;
          const tz = (row - 0.5) * 0.32;
          this._mk(new THREE.CylinderGeometry(0.118, 0.118, 1.00, 8),
              tx, chH + 0.62 + 0.50, tz);
          this._mk(new THREE.CylinderGeometry(0.132, 0.118, 0.036, 8),
              tx, chH + 0.62 + 1.02, tz);
        }
      }
      // ── Radar mast — distinctive tall folding mast with phased-array panel ──
      this._mk(new THREE.CylinderGeometry(0.040, 0.048, 1.20, 8), 0.88, chH + 0.60, 0);
      // Phased-array panel (rectangular, tilted back)
      this._mk(new THREE.BoxGeometry(0.56, 0.44, 0.06), 0.88, chH + 1.30, 0, 0.32, 0, 0);
      // Panel ribs
      for (let r = 0; r < 4; r++) {
        this._mk(new THREE.BoxGeometry(0.54, 0.02, 0.05),
            0.88, chH + 1.08 + r*0.10, 0.04);
      }
      // Hydraulic outriggers (deployed, rear corners)
      for (const s of [-1, 1]) {
        this._mk(new THREE.BoxGeometry(0.34, 0.04, 0.04), 0.80, chH, s*0.46, 0, 0, Math.PI*0.06);
        mkM(new THREE.CylinderGeometry(0.07, 0.09, 0.03, 8), darkMat, 0.96, 0.005, s*0.50);
      }

    } else if (kind === 'pac_2') {
      // ── PAC-2 GEM+ — HEMTT truck + two angled launch rails + big radar ──
      // Silhouette: long truck, two missiles pointing diagonally forward, huge radar dish at rear
      const chL = 2.20, chH = 0.50, chW = 1.02;
      this.box = this._mk(new THREE.BoxGeometry(chL, chH, chW), 0, chH/2, 0);
      buildCab(-0.78, 0.65, 0.62, chW);
      // 4 axles
      addAxle(-1.00, 0.25, 0, 0.22, 0.14, 0.55);
      addAxle(-0.46, 0.25, 0, 0.22, 0.14, 0.55);
      addAxle( 0.36, 0.25, 0, 0.22, 0.14, 0.55);
      addAxle( 0.86, 0.25, 0, 0.22, 0.14, 0.55);
      // Erector pivot frame
      this._mk(new THREE.BoxGeometry(0.70, 0.10, 0.08), 0.10, chH + 0.05, -0.35);
      this._mk(new THREE.BoxGeometry(0.70, 0.10, 0.08), 0.10, chH + 0.05,  0.35);
      // ── Twin angled launch rails + missiles — KEY feature ──
      const railAngle = -Math.PI * 0.30; // ~54° elevation
      for (const s of [-0.28, 0.28]) {
        // Rail beam
        this._mk(new THREE.BoxGeometry(0.09, 1.20, 0.09),
            s, chH + 1.0, -0.22, railAngle, 0, 0);
        // MIM-104 missile (long cylinder + cone nose)
        this._mk(new THREE.CylinderGeometry(0.060, 0.054, 1.08, 10),
            s, chH + 0.96, -0.44, railAngle, 0, 0);
        this._mk(new THREE.ConeGeometry(0.060, 0.30, 10),
            s, chH + 1.60, -0.78, railAngle, 0, 0);
        // Tail fins (cross pattern at base of missile)
        for (let f = 0; f < 4; f++) {
          const fa = f * Math.PI / 2;
          this._mk(new THREE.BoxGeometry(0.20, 0.15, 0.025),
              s + Math.cos(fa)*0.12, chH + 0.22 + Math.sin(fa)*0.12, -0.14 + Math.cos(fa+Math.PI/2)*0.01,
              railAngle, fa, 0);
        }
      }
      // ── AN/MPQ-65 radar — very large, most dramatic feature ──
      // Mast
      this._mk(new THREE.CylinderGeometry(0.048, 0.058, 1.80, 8), 0.80, chH + 0.90, 0);
      // Cross braces
      this._mk(new THREE.BoxGeometry(0.044, 0.90, 0.044), 0.80, chH + 0.90, 0, 0, 0, 0.30);
      this._mk(new THREE.BoxGeometry(0.044, 0.90, 0.044), 0.80, chH + 0.90, 0, 0, 0, -0.30);
      // Large phased-array antenna face (tilted 25°)
      this._mk(new THREE.BoxGeometry(0.80, 0.74, 0.07), 0.80, chH + 1.86, 0, Math.PI*0.24, 0, 0);
      // Antenna horizontal ribs
      for (let r = 0; r < 5; r++) {
        this._mk(new THREE.BoxGeometry(0.78, 0.022, 0.06),
            0.80, chH + 1.55 + r * 0.13, 0.04);
      }
      // Antenna vertical struts
      this._mk(new THREE.BoxGeometry(0.022, 0.72, 0.06), 0.80 - 0.36, chH + 1.86, 0.04);
      this._mk(new THREE.BoxGeometry(0.022, 0.72, 0.06), 0.80 + 0.36, chH + 1.86, 0.04);
      // Outrigger feet
      for (const [ox, oz] of [[-0.90,-0.55],[-0.90,0.55],[0.90,-0.55],[0.90,0.55]]) {
        mkM(new THREE.CylinderGeometry(0.08, 0.10, 0.03, 8), darkMat, ox, 0.005, oz);
      }

    } else if (kind === 'pac_3') {
      // ── PAC-3 MSE — HEMTT truck + 4 square canister pods + smaller radar ──
      // Silhouette: same truck as PAC-2 but canisters point STRAIGHT UP (not angled)
      const chL = 2.20, chH = 0.50, chW = 1.02;
      this.box = this._mk(new THREE.BoxGeometry(chL, chH, chW), 0, chH/2, 0);
      buildCab(-0.78, 0.65, 0.62, chW);
      addAxle(-1.00, 0.25, 0, 0.22, 0.14, 0.55);
      addAxle(-0.46, 0.25, 0, 0.22, 0.14, 0.55);
      addAxle( 0.36, 0.25, 0, 0.22, 0.14, 0.55);
      addAxle( 0.86, 0.25, 0, 0.22, 0.14, 0.55);
      // ── 4 MSE canister pods — KEY feature, tall square boxes vertical ──
      // Arranged 2×2 on launch frame
      for (let col = 0; col < 2; col++) {
        for (let row = 0; row < 2; row++) {
          const tx = 0.18 + (col - 0.5) * 0.50;
          const tz = (row - 0.5) * 0.40;
          // Main canister body (square cross-section, tall)
          this._mk(new THREE.BoxGeometry(0.36, 1.35, 0.36), tx, chH + 0.675, tz);
          // Top cap
          this._mk(new THREE.BoxGeometry(0.38, 0.042, 0.38), tx, chH + 1.37, tz);
          // Corner bolted ribs (makes it look structural)
          for (const [cx, cz] of [[-0.18,-0.18],[-0.18,0.18],[0.18,-0.18],[0.18,0.18]]) {
            this._mk(new THREE.BoxGeometry(0.04, 1.35, 0.04), tx+cx, chH+0.675, tz+cz);
          }
          // Mid-band stiffener ring
          this._mk(new THREE.BoxGeometry(0.38, 0.042, 0.38), tx, chH + 0.38, tz);
        }
      }
      // Launch frame base plate
      this._mk(new THREE.BoxGeometry(0.88, 0.06, chW*0.92), 0.18, chH + 0.03, 0);
      // ── Radar mast (shorter than PAC-2, different recognition) ──
      this._mk(new THREE.CylinderGeometry(0.040, 0.048, 0.96, 8), 0.84, chH + 0.48, 0);
      // Smaller octagonal radar face
      this._mk(new THREE.CylinderGeometry(0.26, 0.26, 0.05, 8),
          0.84, chH + 0.98, 0, Math.PI*0.20, 0, 0);
      this._mk(new THREE.CylinderGeometry(0.20, 0.20, 0.04, 8),
          0.84, chH + 0.96, 0.06, Math.PI*0.20, 0, 0);
      // Electronics shelter on rear bed
      this._mk(new THREE.BoxGeometry(0.38, 0.32, chW*0.88), 0.84, chH + 0.16, 0);
      // Outrigger feet
      for (const [ox, oz] of [[-0.95,-0.54],[-0.95,0.54],[0.95,-0.54],[0.95,0.54]]) {
        mkM(new THREE.CylinderGeometry(0.08, 0.10, 0.03, 8), darkMat, ox, 0.005, oz);
      }

    } else {
      this.box = this._mk(new THREE.BoxGeometry(1.5, 0.8, 1.0), 0, 0.4, 0);
    }
  }

  setReloading(reloading) {
    if (reloading) {
      this.material.opacity = BOX_OPACITY_RELOAD;
      this.arcMaterial.opacity = ARC_OPACITY_RELOAD;
    } else {
      this.material.opacity = BOX_OPACITY_READY;
      this.arcMaterial.opacity = ARC_OPACITY_READY;
    }
  }

  // Emissive boost on selection (called every tick, cheap).
  setSelected(selected) {
    this.material.emissiveIntensity = selected ? 1.1 : 0.35;
  }

  dispose(scene) {
    scene.remove(this.group);
    // Dispose all mesh geometries in the group tree.
    this.group.traverse(obj => {
      if (obj.isMesh && obj.geometry) obj.geometry.dispose();
    });
    this.material.dispose();
    this.arc.geometry.dispose();
    this.arcMaterial.dispose();
  }
}

export class LauncherRegistry {
  constructor(scene) {
    this.scene = scene;
    this.byId = new Map();
  }

  updateFromSnapshot(snap) {
    const list = snap.launchers || [];
    const perKindCount = {};
    const seen = new Set();
    for (const lch of list) {
      const idx = perKindCount[lch.kind] ?? 0;
      perKindCount[lch.kind] = idx + 1;
      const id = lch.id || `${lch.kind}_${idx}`;
      seen.add(id);

      const [sx, sz] = worldToSceneXY(lch.pos[0], lch.pos[1]);
      let mesh = this.byId.get(id);
      if (!mesh) {
        mesh = new LauncherMesh(this.scene, lch.kind, sx, sz, id);
        this.byId.set(id, mesh);
      } else if (!mesh.group.userData.dragging) {
        mesh.group.position.set(sx, 0, sz);
      }
      mesh.setReloading(Boolean(lch.reloading));
    }
    for (const [id, mesh] of this.byId) {
      if (!seen.has(id)) {
        mesh.dispose(this.scene);
        this.byId.delete(id);
      }
    }
    const selectedId = getSelectedLauncherId();
    for (const [id, mesh] of this.byId) {
      mesh.setSelected(id === selectedId);
    }
  }
}

// ─── Red offensive launchers (Milestone H Part 3) ───────────────────────────
// Stylised threat vehicle: truck chassis + angled launch arm + side radar.
// No range ring (offensive, not defensive coverage).
class RedLauncherMesh {
  constructor(scene, sx, sz) {
    this.group = new THREE.Group();
    this.group.position.set(sx, 0, sz);
    this.group.scale.setScalar(1.5);

    this.material = new THREE.MeshStandardMaterial({
      color: 0xaa2030,
      emissive: 0x551018,
      emissiveIntensity: 0.5,
      roughness: 0.55,
      metalness: 0.2,
    });

    const mk = (geom, x = 0, y = 0, z = 0, rx = 0, ry = 0, rz = 0) => {
      const m = new THREE.Mesh(geom, this.material);
      m.position.set(x, y, z);
      if (rx || ry || rz) m.rotation.set(rx, ry, rz);
      this.group.add(m);
      return m;
    };

    // ── Generic threat launcher truck ──
    // Chassis
    this.box = mk(new THREE.BoxGeometry(1.65, 0.50, 0.88), 0, 0.25, 0);
    // Cab (front)
    mk(new THREE.BoxGeometry(0.54, 0.46, 0.88), -0.55, 0.73, 0);
    // Launch arm (angled skyward toward south, i.e. +Z — these are Red assets
    // firing northward, but visually the arm points up is enough)
    mk(new THREE.BoxGeometry(0.12, 0.95, 0.12), 0.32, 0.97, 0, -Math.PI * 0.18, 0, 0);
    // Radar / sensor disc on short mast (side)
    mk(new THREE.CylinderGeometry(0.030, 0.035, 0.58, 5), -0.55, 0.79, 0.35);
    mk(new THREE.CylinderGeometry(0.18, 0.18, 0.024, 8), -0.55, 1.11, 0.35);

    scene.add(this.group);
  }

  dispose(scene) {
    scene.remove(this.group);
    this.group.traverse(obj => {
      if (obj.isMesh && obj.geometry) obj.geometry.dispose();
    });
    this.material.dispose();
  }
}

export class RedLauncherRegistry {
  constructor(scene) {
    this.scene = scene;
    this.byId = new Map();
  }

  updateFromSnapshot(snap) {
    const list = snap.red_launchers || [];
    const perKindCount = {};
    const seen = new Set();
    for (const lch of list) {
      const idx = perKindCount[lch.kind] ?? 0;
      perKindCount[lch.kind] = idx + 1;
      const id = `${lch.kind}_${idx}`;
      seen.add(id);

      if (!this.byId.has(id)) {
        const [sx, sz] = worldToSceneXY(lch.pos[0], lch.pos[1]);
        this.byId.set(id, new RedLauncherMesh(this.scene, sx, sz));
      }
    }
    for (const [id, mesh] of this.byId) {
      if (!seen.has(id)) {
        mesh.dispose(this.scene);
        this.byId.delete(id);
      }
    }
  }
}
