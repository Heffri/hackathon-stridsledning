// Per-site markers rendered on the terrain. Milestone G replaces the
// single base cylinder with one coloured flat ring per Red-targetable
// site (Saab named locations + the legacy base). Each ring's radius is
// the 800 m damage footprint. A canvas-texture Sprite above the ring
// shows the site's current leak count when leaks > 0.
//
// Data comes from `snap.sites` (emitted by backend scenarios.py).
// Ring colour by subtype:
//   capital    → pulsing red  (highest strategic value)
//   air_base   → orange
//   major_city → yellow
//   base       → blue
import * as THREE from 'three';
import { worldToSceneXY } from './scene.js';

const SITE_COLORS = {
  capital: 0xff2a2a,
  air_base: 0xff8800,
  major_city: 0xffd24a,
  base: 0x3b82f6,
};

// 800 m world = 0.8 scene units. Ring mesh uses inner/outer radii so
// the marker reads as a disc outline rather than a solid cap; the
// flatterrain already has enough fill shapes competing for the eye.
const RING_INNER = 0.55;
const RING_OUTER = 0.8;

function makeLeakBadgeSprite(n) {
  const canvas = document.createElement('canvas');
  canvas.width = 128;
  canvas.height = 64;
  const ctx = canvas.getContext('2d');
  // Rounded-rect background
  ctx.fillStyle = 'rgba(80, 12, 12, 0.88)';
  ctx.beginPath();
  const r = 14;
  const w = canvas.width;
  const h = canvas.height;
  ctx.moveTo(r, 0);
  ctx.arcTo(w, 0, w, h, r);
  ctx.arcTo(w, h, 0, h, r);
  ctx.arcTo(0, h, 0, 0, r);
  ctx.arcTo(0, 0, w, 0, r);
  ctx.closePath();
  ctx.fill();
  ctx.strokeStyle = '#ffaa55';
  ctx.lineWidth = 3;
  ctx.stroke();
  ctx.fillStyle = '#ffffff';
  ctx.font = 'bold 34px sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  const label = n === 1 ? `${n} leak` : `${n} leaks`;
  ctx.fillText(label, canvas.width / 2, canvas.height / 2 + 2);
  const tex = new THREE.CanvasTexture(canvas);
  tex.minFilter = THREE.LinearFilter;
  tex.magFilter = THREE.LinearFilter;
  const mat = new THREE.SpriteMaterial({ map: tex, depthTest: false, transparent: true });
  return new THREE.Sprite(mat);
}

class SiteMesh {
  constructor(scene, site) {
    this.scene = scene;
    this.subtype = site.subtype;
    const color = SITE_COLORS[site.subtype] ?? 0xaaaaaa;
    const [sx, sz] = worldToSceneXY(site.pos[0], site.pos[1]);
    this.sx = sx;
    this.sz = sz;

    const geom = new THREE.RingGeometry(RING_INNER, RING_OUTER, 48);
    this.material = new THREE.MeshBasicMaterial({
      color,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.7,
      depthWrite: false,
    });
    this.ring = new THREE.Mesh(geom, this.material);
    // RingGeometry lives in local XY; rotate so it lies flat on the
    // ground (XZ plane). A small y-lift keeps it above the 0.3-unit
    // extruded terrain so it isn't hidden by the mainland polygon.
    this.ring.rotation.x = -Math.PI / 2;
    this.ring.position.set(sx, 0.36, sz);
    scene.add(this.ring);

    // Leak count badge (created lazily when leaks > 0).
    this.leakSprite = null;
    this.lastLeaks = 0;
    this.pulsePhase = 0;
  }

  setLeaks(n) {
    if (n === this.lastLeaks) return;
    this.lastLeaks = n;
    if (this.leakSprite) {
      this.scene.remove(this.leakSprite);
      this.leakSprite.material.map.dispose();
      this.leakSprite.material.dispose();
      this.leakSprite = null;
    }
    if (n > 0) {
      this.leakSprite = makeLeakBadgeSprite(n);
      this.leakSprite.position.set(this.sx, 1.4, this.sz);
      this.leakSprite.scale.set(3.2, 1.6, 1);
      this.scene.add(this.leakSprite);
    }
  }

  // Capitals pulse subtly when damaged so the highest-value target
  // reads as urgent on the HUD. Other subtypes stay static.
  pulse(dt) {
    if (this.subtype !== 'capital' || this.lastLeaks === 0) return;
    this.pulsePhase += dt * 3.0;
    const intensity = 0.55 + 0.35 * Math.sin(this.pulsePhase);
    this.material.opacity = intensity;
  }

  dispose() {
    this.scene.remove(this.ring);
    this.ring.geometry.dispose();
    this.material.dispose();
    if (this.leakSprite) {
      this.scene.remove(this.leakSprite);
      this.leakSprite.material.map.dispose();
      this.leakSprite.material.dispose();
    }
  }
}

export class SiteRegistry {
  constructor(scene) {
    this.scene = scene;
    this.byName = new Map();
    this._lastFrame = performance.now();
  }

  updateFromSnapshot(snap) {
    const list = snap.sites || [];
    const now = performance.now();
    const dt = (now - this._lastFrame) / 1000;
    this._lastFrame = now;

    const seen = new Set();
    for (const site of list) {
      seen.add(site.name);
      let mesh = this.byName.get(site.name);
      if (!mesh) {
        mesh = new SiteMesh(this.scene, site);
        this.byName.set(site.name, mesh);
      }
      mesh.setLeaks(site.leaks || 0);
      mesh.pulse(dt);
    }
    // Drop any site no longer in the snapshot (scenario change).
    for (const [name, mesh] of this.byName) {
      if (!seen.has(name)) {
        mesh.dispose();
        this.byName.delete(name);
      }
    }
  }
}
