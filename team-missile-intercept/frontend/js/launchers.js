// Per-launcher visual layer: one coloured box + one northern semi-circle
// range arc per Launcher instance in snap.launchers. Replaces the base-
// centred range arcs from Milestone E.
//
// Each launcher is identified by `${kind}_${index}` where index is the
// ordinal position within its kind in the snapshot list (stable across
// ticks since positions are hard-coded in config.BLUE_LAUNCHER_POSITIONS).
//
// Reloading launchers dim both the box (opacity 0.5) and the arc
// (opacity 0.15) so the operator can see coverage gaps at a glance.
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
  constructor(scene, kind, sx, sz) {
    this.kind = kind;
    const color = LAUNCHER_COLORS[kind] ?? 0xffffff;

    // Box body: 1.5 x 0.8 x 1.0 (X x Y x Z) scene units. Centre at
    // (sx, 0.4, sz) so the bottom sits at y=0 — the extruded terrain
    // (y=0..0.3) hides the lower half when the launcher is on land,
    // which reads as "sitting on a pad".
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
    this.box.position.set(sx, 0.4, sz);
    scene.add(this.box);

    // Full-circle range arc. Launchers now sit forward of the base and
    // threats can approach from any bearing, so a northern semi-circle
    // no longer matches reality. 192 segments keeps the full circle
    // as smooth as the old half-circle at 96.
    const rKm = RANGE_KM[kind] ?? 4;
    const segments = 192;
    const pts = [];
    for (let i = 0; i <= segments; i++) {
      const theta = (i / segments) * Math.PI * 2;
      pts.push(
        new THREE.Vector3(
          sx + Math.cos(theta) * rKm,
          0.35,
          sz - Math.sin(theta) * rKm,
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
    scene.add(this.arc);
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
    scene.remove(this.box);
    this.box.geometry.dispose();
    this.material.dispose();
    scene.remove(this.arc);
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
      const id = `${lch.kind}_${idx}`;
      seen.add(id);

      let mesh = this.byId.get(id);
      if (!mesh) {
        const [sx, sz] = worldToSceneXY(lch.pos[0], lch.pos[1]);
        mesh = new LauncherMesh(this.scene, lch.kind, sx, sz);
        this.byId.set(id, mesh);
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
