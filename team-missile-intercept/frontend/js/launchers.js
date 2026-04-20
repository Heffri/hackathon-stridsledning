// Per-launcher visual layer: one coloured box + one full-circle range
// ring per Launcher instance in snap.launchers. Replaces the base-
// centred range arcs from Milestone E.
//
// Each launcher is identified by `${kind}_${index}` where index is the
// ordinal position within its kind in the snapshot list (stable across
// ticks since positions are hard-coded in config.BLUE_LAUNCHER_POSITIONS).
//
// Reloading launchers dim both the box (opacity 0.5) and the arc
// (opacity 0.15) so the operator can see coverage gaps at a glance.
//
// Milestone H Part 4: each launcher is a THREE.Group positioned at the
// launcher's world coord. The box and ring live as children in LOCAL
// coords so a future deployment-UI move operation can reposition the
// Group and the ring follows automatically.
//
// Red launchers (RedLauncherRegistry) render a red-tinted box only —
// no range ring since they're offensive (no defensive coverage to show).
import * as THREE from 'three';
import { worldToSceneXY } from './scene.js';

// Mesh colours — matches entities.js body colours + scene.js range arc
// colours so boxes, interceptor bodies, and arcs all read as "the same
// weapon" at first glance.
const LAUNCHER_COLORS = {
  ciws: 0xd9b36a,
  rbs_70: 0x4a8a3a,
  iris_t_sls: 0xff9944,
  iris_t_slm: 0xff8c1a,
  pac_2: 0xff69b4,
  pac_3: 0xa855f7,
};

// Per-kind max_range in km. Mirrors backend INTERCEPTOR_SPECS.max_range
// (m) divided by 1000 and matches the old base-centred arc radii. Kept
// as a frontend constant so the arc can render before the first
// snapshot arrives; the server's launcher records don't carry range.
const RANGE_KM = {
  ciws: 4,
  rbs_70: 9,
  iris_t_sls: 12,
  iris_t_slm: 40,
  pac_2: 70,
  pac_3: 60,
};

const BOX_OPACITY_READY = 1.0;
const BOX_OPACITY_RELOAD = 0.5;
const ARC_OPACITY_READY = 0.4;
const ARC_OPACITY_RELOAD = 0.15;

class LauncherMesh {
  constructor(scene, kind, sx, sz, launcherId) {
    this.kind = kind;
    this.launcherId = launcherId;
    const color = LAUNCHER_COLORS[kind] ?? 0xffffff;

    // Milestone H Part 4: every launcher is a Group positioned at
    // (sx, 0, sz). The box mesh and the range-ring Line live as
    // children in LOCAL coordinates (ring centred on the origin,
    // radius = max_range in scene units). If the Group later moves
    // (Milestone I deployment UI), the ring follows automatically.
    this.group = new THREE.Group();
    this.group.position.set(sx, 0, sz);
    // M-TIER2-J Part 1: id is stamped on userData so the drag handler
    // (drag_launchers.js) can walk from a raycast hit up to the Group
    // and emit a `place_launcher` command addressed by stable string.
    // `dragging` flag suppresses snapshot-driven position updates while
    // the operator holds the pointer so the drag stays smooth.
    this.group.userData.launcherId = launcherId;
    this.group.userData.dragging = false;

    // Box body: 1.5 x 0.8 x 1.0 (X x Y x Z) scene units. Bottom sits
    // at local y=0 — the extruded terrain (y=0..0.3) hides the lower
    // half when the launcher is on land, reading as "sitting on a pad".
    this.material = new THREE.MeshStandardMaterial({
      color,
      emissive: color,
      emissiveIntensity: 0.35,
      roughness: 0.5,
      metalness: 0.2,
      transparent: true,
      opacity: BOX_OPACITY_READY,
    });
    this.box = new THREE.Mesh(
      new THREE.BoxGeometry(1.5, 0.8, 1.0),
      this.material,
    );
    this.box.position.set(0, 0.4, 0);
    this.group.add(this.box);

    // Full-circle range ring in local coords (centered on group origin).
    // 192 segments keeps the full circle as smooth as the old half-
    // circle at 96.
    const rKm = RANGE_KM[kind] ?? 4;
    const segments = 192;
    const pts = [];
    for (let i = 0; i <= segments; i++) {
      const theta = (i / segments) * Math.PI * 2;
      pts.push(
        new THREE.Vector3(
          Math.cos(theta) * rKm,
          0.35,
          -Math.sin(theta) * rKm,
        ),
      );
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

  setReloading(reloading) {
    if (reloading) {
      this.material.opacity = BOX_OPACITY_RELOAD;
      this.arcMaterial.opacity = ARC_OPACITY_RELOAD;
    } else {
      this.material.opacity = BOX_OPACITY_READY;
      this.arcMaterial.opacity = ARC_OPACITY_READY;
    }
  }

  dispose(scene) {
    scene.remove(this.group);
    this.box.geometry.dispose();
    this.material.dispose();
    this.arc.geometry.dispose();
    this.arcMaterial.dispose();
  }
}

export class LauncherRegistry {
  constructor(scene) {
    this.scene = scene;
    // id (`${kind}_${index}`) → LauncherMesh. Stable across ticks because
    // backend emits launchers in deterministic order.
    this.byId = new Map();
  }

  updateFromSnapshot(snap) {
    const list = snap.launchers || [];
    // Running index per kind = which-th launcher of this kind we've
    // seen in this snapshot. Backend guarantees stable order per tick.
    const perKindCount = {};
    const seen = new Set();
    for (const lch of list) {
      const idx = perKindCount[lch.kind] ?? 0;
      perKindCount[lch.kind] = idx + 1;
      // Prefer the server-provided id (M-TIER2-J Part 1, Subtask A);
      // fall back to the local `${kind}_${idx}` computation for
      // snapshots from older backends.
      const id = lch.id || `${lch.kind}_${idx}`;
      seen.add(id);

      const [sx, sz] = worldToSceneXY(lch.pos[0], lch.pos[1]);
      let mesh = this.byId.get(id);
      if (!mesh) {
        mesh = new LauncherMesh(this.scene, lch.kind, sx, sz, id);
        this.byId.set(id, mesh);
      } else if (!mesh.group.userData.dragging) {
        // Snapshot carries the authoritative committed position — apply
        // it unless the operator is currently dragging this launcher
        // (drag handler owns the Group transform during that window).
        mesh.group.position.set(sx, 0, sz);
      }
      mesh.setReloading(Boolean(lch.reloading));
    }
    // Dispose any launcher that disappeared (e.g. on scenario reset with
    // a different positions dict).
    for (const [id, mesh] of this.byId) {
      if (!seen.has(id)) {
        mesh.dispose(this.scene);
        this.byId.delete(id);
      }
    }
  }
}

// --- Red offensive launcher boxes (Milestone H Part 3) ---
//
// Same geometry as Blue boxes but a red emissive material and no range
// ring. Visible anchors for where drones / cruise missiles spawn from.
// Infinite ammo, so no opacity rule — always fully lit.
const RED_LAUNCHER_COLOR = 0xaa2030;
const RED_LAUNCHER_EMISSIVE = 0x441015;

class RedLauncherMesh {
  constructor(scene, sx, sz) {
    this.material = new THREE.MeshStandardMaterial({
      color: RED_LAUNCHER_COLOR,
      emissive: RED_LAUNCHER_EMISSIVE,
      emissiveIntensity: 0.4,
      roughness: 0.55,
      metalness: 0.2,
    });
    this.box = new THREE.Mesh(
      new THREE.BoxGeometry(1.5, 0.8, 1.0),
      this.material,
    );
    this.box.position.set(sx, 0.4, sz);
    scene.add(this.box);
  }

  dispose(scene) {
    scene.remove(this.box);
    this.box.geometry.dispose();
    this.material.dispose();
  }
}

export class RedLauncherRegistry {
  constructor(scene) {
    this.scene = scene;
    // id (`${kind}_${index}`) → RedLauncherMesh. Backend emits Red
    // launchers in the same deterministic order every tick.
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
