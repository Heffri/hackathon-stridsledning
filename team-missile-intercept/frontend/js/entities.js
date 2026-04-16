// Entity rendering: per-kind procedural meshes, trails, explosions.
//
// Convention: each model's long axis is +Y in local space so the generic
// orientation code (setFromUnitVectors(+Y, velocity_dir)) keeps working
// regardless of threat/interceptor kind.
import * as THREE from 'three';
import { worldToScene, SCALE } from './scene.js';

const TRAIL_LEN = 60;

function buildModel(kind, team, color) {
  const c = new THREE.Color(color || (team === 'red' ? '#ff3040' : '#ffd24a'));
  const bodyMat = new THREE.MeshStandardMaterial({
    color: c,
    emissive: c,
    emissiveIntensity: 0.35,
    roughness: 0.5,
    metalness: 0.1,
  });
  const darkMat = new THREE.MeshStandardMaterial({
    color: c.clone().multiplyScalar(0.55),
    emissive: c.clone().multiplyScalar(0.2),
    emissiveIntensity: 0.15,
    roughness: 0.7,
  });

  const g = new THREE.Group();

  if (kind === 'drone') {
    // Simple delta-wing planform with a tail-mounted propeller disc.
    // Long flight axis = +Y (nose forward), wing plane in X-Y, thin in Z.
    // The body is a 3-segment cone squashed flat so it reads as a flat
    // triangle: nose at +Y, two wing corners trailing at -Y.
    const body = new THREE.Mesh(
      new THREE.ConeGeometry(0.95, 1.9, 3),
      bodyMat,
    );
    body.scale.set(1.0, 1.0, 0.18); // squash on Z → flat triangle
    // Tail propeller: a thin disc at the rear (-Y), perpendicular to flight.
    // Cylinder default axis is +Y so we tilt it 90° so the disc face points
    // backward (its plane is X-Z = perpendicular to Y).
    const prop = new THREE.Mesh(
      new THREE.CylinderGeometry(0.32, 0.32, 0.05, 12),
      darkMat,
    );
    prop.rotation.x = Math.PI / 2; // disc face perpendicular to flight axis
    prop.position.set(0, -0.95, 0);
    g.add(body, prop);
    // Tag the propeller for spin animation in the update loop.
    g.userData.propeller = prop;
  } else if (kind === 'cruise_sub') {
    // Kalibr-class: long slender cigar with two horizontal mid-wings and a
    // cruciform tail. Long axis = +Y (nose forward).
    // Box dims = (X span, Y chord, Z thickness). Wings lie flat in the X-Y
    // plane (thin Z) so the missile silhouette reads as a horizontal cross
    // when viewed from above.
    const body = new THREE.Mesh(
      new THREE.CylinderGeometry(0.2, 0.24, 2.6, 14),
      bodyMat,
    );
    const nose = new THREE.Mesh(
      new THREE.ConeGeometry(0.2, 0.7, 14),
      bodyMat,
    );
    nose.position.y = 1.65;
    // Mid-body horizontal wings ONLY: span 2.4 (X), chord 0.6 (Y), thin
    // along vertical (Z). They extend symmetrically to either side of the
    // fuselage and lie flat — no vertical mid-body fin.
    const midWing = new THREE.Mesh(
      new THREE.BoxGeometry(2.4, 0.6, 0.05),
      darkMat,
    );
    midWing.position.set(0, 0.1, 0);
    // Cruciform tail: horizontal fin (X span) + vertical fin (Z span) —
    // both have the same chord along Y so they read as a "+" from behind.
    const tailH = new THREE.Mesh(
      new THREE.BoxGeometry(1.0, 0.35, 0.04),
      darkMat,
    );
    const tailV = new THREE.Mesh(
      new THREE.BoxGeometry(0.04, 0.35, 1.0),
      darkMat,
    );
    tailH.position.y = -1.15;
    tailV.position.y = -1.15;
    g.add(body, nose, midWing, tailH, tailV);
  } else if (kind === 'ballistic') {
    // Big fat reentry body: larger cylinder + sharp ogive nose + 4 grid fins
    const body = new THREE.Mesh(
      new THREE.CylinderGeometry(0.45, 0.55, 3.2, 14),
      bodyMat,
    );
    const nose = new THREE.Mesh(
      new THREE.ConeGeometry(0.45, 1.3, 14),
      bodyMat,
    );
    nose.position.y = 2.25;
    // Grid fins (4 small boxes at the base)
    for (let i = 0; i < 4; i++) {
      const fin = new THREE.Mesh(
        new THREE.BoxGeometry(0.08, 0.6, 0.45),
        darkMat,
      );
      fin.position.set(
        Math.cos((i * Math.PI) / 2) * 0.55,
        -1.45,
        Math.sin((i * Math.PI) / 2) * 0.55,
      );
      fin.rotation.y = -(i * Math.PI) / 2;
      g.add(fin);
    }
    g.add(body, nose);
  } else if (
    kind === 'ciws' ||
    kind === 'short_sam' ||
    kind === 'med_sam' ||
    kind === 'long_sam'
  ) {
    // Blue interceptor SAM. Slender rocket + nose cone + 4 tail fins + exhaust plume.
    const size = kind === 'long_sam' ? 1.15 : kind === 'ciws' ? 0.65 : 1.0;
    const body = new THREE.Mesh(
      new THREE.CylinderGeometry(0.13 * size, 0.16 * size, 1.8 * size, 12),
      bodyMat,
    );
    const nose = new THREE.Mesh(
      new THREE.ConeGeometry(0.13 * size, 0.5 * size, 12),
      bodyMat,
    );
    nose.position.y = 1.15 * size;
    // 4 tail fins
    for (let i = 0; i < 4; i++) {
      const fin = new THREE.Mesh(
        new THREE.BoxGeometry(0.05 * size, 0.45 * size, 0.35 * size),
        darkMat,
      );
      const a = (i * Math.PI) / 2;
      fin.position.set(
        Math.cos(a) * 0.22 * size,
        -0.85 * size,
        Math.sin(a) * 0.22 * size,
      );
      fin.rotation.y = -a;
      g.add(fin);
    }
    // Exhaust plume (points backward = -Y)
    const flameMat = new THREE.MeshBasicMaterial({
      color: 0xffb347,
      transparent: true,
      opacity: 0.75,
    });
    const flame = new THREE.Mesh(
      new THREE.ConeGeometry(0.22 * size, 0.9 * size, 10),
      flameMat,
    );
    flame.position.y = -1.45 * size;
    flame.rotation.z = Math.PI; // tip points -Y
    g.add(body, nose, flame);
    // tag the flame for pulsing animation
    g.userData.flame = flame;
  } else {
    // Fallback: original single cone.
    const h = team === 'red' ? 2.2 : 1.6;
    const r = team === 'red' ? 0.7 : 0.5;
    const geo = new THREE.ConeGeometry(r, h, 8);
    geo.translate(0, h / 2, 0);
    g.add(new THREE.Mesh(geo, bodyMat));
  }

  return g;
}

class EntityMesh {
  constructor(scene, id, team, kind, color) {
    this.id = id;
    this.team = team;
    this.kind = kind;

    this.mesh = buildModel(kind, team, color);
    scene.add(this.mesh);

    // Trail: Line with dynamic geometry
    this.trailPoints = [];
    const trailGeom = new THREE.BufferGeometry();
    trailGeom.setAttribute(
      'position',
      new THREE.BufferAttribute(new Float32Array(TRAIL_LEN * 3), 3),
    );
    trailGeom.setDrawRange(0, 0);
    const trailColor = new THREE.Color(
      color || (team === 'red' ? '#ff5570' : '#ffcc33'),
    );
    const trailMat = new THREE.LineBasicMaterial({
      color: trailColor,
      transparent: true,
      opacity: 0.7,
    });
    this.trail = new THREE.Line(trailGeom, trailMat);
    scene.add(this.trail);
  }

  update(pos, vel) {
    const [x, y, z] = worldToScene(pos[0], pos[1], pos[2]);
    this.mesh.position.set(x, y, z);

    // Orient cone along velocity vector
    const [vx, vy, vz] = worldToScene(
      pos[0] + vel[0],
      pos[1] + vel[1],
      pos[2] + vel[2],
    );
    const dir = new THREE.Vector3(vx - x, vy - y, vz - z);
    if (dir.lengthSq() > 1e-10) {
      dir.normalize();
      // All models are built with long axis = +Y in local space so this
      // single rotation works for every kind.
      const up = new THREE.Vector3(0, 1, 0);
      this.mesh.quaternion.setFromUnitVectors(up, dir);
    }

    // Flicker the SAM exhaust plume, if present.
    const flame = this.mesh.userData?.flame;
    if (flame) {
      const t = performance.now() / 1000;
      flame.material.opacity = 0.55 + 0.25 * Math.sin(t * 22 + this.id);
      const s = 0.9 + 0.2 * Math.sin(t * 18 + this.id * 1.3);
      flame.scale.set(s, 1, s);
    }

    // Spin the drone propeller around the flight axis (its local +Y, which
    // is the cylinder's "ring" axis after the rotation.x = π/2 we applied).
    const prop = this.mesh.userData?.propeller;
    if (prop) {
      prop.rotation.y += 0.6; // ~ visual spin per frame
    }

    // Trail
    this.trailPoints.push([x, y, z]);
    if (this.trailPoints.length > TRAIL_LEN) this.trailPoints.shift();
    const arr = this.trail.geometry.attributes.position.array;
    for (let i = 0; i < this.trailPoints.length; i++) {
      const [tx, ty, tz] = this.trailPoints[i];
      arr[i * 3] = tx;
      arr[i * 3 + 1] = ty;
      arr[i * 3 + 2] = tz;
    }
    this.trail.geometry.attributes.position.needsUpdate = true;
    this.trail.geometry.setDrawRange(0, this.trailPoints.length);
  }

  dispose(scene) {
    scene.remove(this.mesh);
    // mesh is a Group — walk children to release GPU resources.
    this.mesh.traverse((obj) => {
      if (obj.geometry) obj.geometry.dispose();
      if (obj.material) {
        if (Array.isArray(obj.material)) {
          obj.material.forEach((m) => m.dispose());
        } else {
          obj.material.dispose();
        }
      }
    });
    scene.remove(this.trail);
    this.trail.geometry.dispose();
    this.trail.material.dispose();
  }
}

export class EntityRegistry {
  constructor(scene) {
    this.scene = scene;
    this.byId = new Map();
    this.explosions = [];
  }

  updateFromSnapshot(snap) {
    // Reconcile entities
    const seen = new Set();
    for (const e of snap.entities) {
      seen.add(e.id);
      let em = this.byId.get(e.id);
      if (!em) {
        em = new EntityMesh(this.scene, e.id, e.team, e.kind, e.color);
        this.byId.set(e.id, em);
      }
      if (e.alive) em.update(e.pos, e.vel);
    }
    // Dispose disappeared entities
    for (const [id, em] of this.byId) {
      if (!seen.has(id)) {
        em.dispose(this.scene);
        this.byId.delete(id);
      }
    }

    // Explosions
    for (const ex of snap.explosions) {
      // Only spawn a visual once per explosion — use position+t as key
      const key = `${ex.t.toFixed(3)}_${ex.pos[0].toFixed(1)}_${ex.pos[1].toFixed(1)}`;
      if (!this._exKeys) this._exKeys = new Set();
      if (!this._exKeys.has(key)) {
        this._exKeys.add(key);
        this._spawnExplosion(ex.pos);
        // prune old keys
        if (this._exKeys.size > 500) {
          this._exKeys = new Set(Array.from(this._exKeys).slice(-200));
        }
      }
    }
    // Step explosion animations
    const now = performance.now() / 1000;
    for (const ex of this.explosions) {
      const age = now - ex.born;
      const t = Math.min(1, age / ex.lifetime);
      const scale = 1 + t * 18;
      ex.mesh.scale.setScalar(scale * SCALE * 1000); // convert world→scene scale
      ex.mesh.material.opacity = Math.max(0, 0.9 - t);
    }
    this.explosions = this.explosions.filter((ex) => {
      const age = now - ex.born;
      if (age >= ex.lifetime) {
        this.scene.remove(ex.mesh);
        ex.mesh.geometry.dispose();
        ex.mesh.material.dispose();
        return false;
      }
      return true;
    });
  }

  _spawnExplosion(pos) {
    const [x, y, z] = worldToScene(pos[0], pos[1], pos[2]);
    const mat = new THREE.MeshBasicMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: 0.95,
    });
    const mesh = new THREE.Mesh(new THREE.SphereGeometry(0.5, 12, 10), mat);
    mesh.position.set(x, y, z);
    this.scene.add(mesh);
    this.explosions.push({
      mesh,
      born: performance.now() / 1000,
      lifetime: 1.0,
    });
  }
}
