// Entity rendering: cones for threats/interceptors, trails, explosions.
import * as THREE from 'three';
import { worldToScene, SCALE } from './scene.js';

const TRAIL_LEN = 60;

class EntityMesh {
  constructor(scene, id, team, kind, color) {
    this.id = id;
    this.team = team;
    this.kind = kind;

    const isThreat = team === 'red';
    // Threats: cones pointing along velocity. Interceptors: similar but yellow.
    const radius = isThreat ? 0.7 : 0.5;
    const height = isThreat ? 2.2 : 1.6;
    const coneGeom = new THREE.ConeGeometry(radius, height, 8);
    // Reorient so cone points along +Z local (easier to align with velocity)
    coneGeom.translate(0, height / 2, 0); // apex at +Y now
    const mat = new THREE.MeshStandardMaterial({
      color: new THREE.Color(color || (isThreat ? '#ff3040' : '#ffd24a')),
      emissive: new THREE.Color(color || (isThreat ? '#ff3040' : '#ffd24a')),
      emissiveIntensity: 0.45,
      roughness: 0.5,
    });
    this.mesh = new THREE.Mesh(coneGeom, mat);
    scene.add(this.mesh);

    // Trail: Line with dynamic geometry
    this.trailPoints = [];
    const trailGeom = new THREE.BufferGeometry();
    trailGeom.setAttribute(
      'position',
      new THREE.BufferAttribute(new Float32Array(TRAIL_LEN * 3), 3),
    );
    trailGeom.setDrawRange(0, 0);
    const trailMat = new THREE.LineBasicMaterial({
      color: new THREE.Color(color || (isThreat ? '#ff5570' : '#ffcc33')),
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
      // default cone axis is +Y after translate above
      const up = new THREE.Vector3(0, 1, 0);
      this.mesh.quaternion.setFromUnitVectors(up, dir);
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
    this.mesh.geometry.dispose();
    this.mesh.material.dispose();
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
