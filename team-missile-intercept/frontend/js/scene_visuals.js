// Visual enhancements for Boreal Passage — purely cosmetic, no game values.
// Stylized low-poly: animated water, biome terrain, instanced trees, roads,
// coastline highlights.
import * as THREE from 'three';

// ── Deterministic PRNG (mulberry32) ─────────────────────────────────────
function mulberry32(seed) {
  return function () {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ── Ray-cast point-in-polygon ───────────────────────────────────────────
function pointInPoly(px, py, polygon) {
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const [xi, yi] = polygon[i];
    const [xj, yj] = polygon[j];
    if (
      yi > py !== yj > py &&
      px < ((xj - xi) * (py - yi)) / (yj - yi) + xi
    ) {
      inside = !inside;
    }
  }
  return inside;
}

// ═══════════════════════════════════════════════════════════════════════
// 1. ANIMATED WATER — replaces flat sea plane
// ═══════════════════════════════════════════════════════════════════════
export function createWater(width, depth, centreZ) {
  const geom = new THREE.PlaneGeometry(
    width * 1.25,
    depth * 1.25,
    80,
    80,
  );
  const mat = new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      uDeep: { value: new THREE.Color(0x091628) },
      uMid: { value: new THREE.Color(0x142a48) },
      uShallow: { value: new THREE.Color(0x1c4a6a) },
    },
    vertexShader: /* glsl */ `
      uniform float uTime;
      varying vec2 vUv;
      varying float vElev;
      void main() {
        vUv = uv;
        vec3 p = position;
        float w1 = sin(p.x * 0.06 + uTime * 0.35) * 0.15;
        float w2 = sin(p.y * 0.04 + uTime * 0.22) * 0.10;
        float w3 = sin((p.x + p.y) * 0.035 + uTime * 0.48) * 0.07;
        vElev = w1 + w2 + w3;
        p.z += vElev;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0);
      }
    `,
    fragmentShader: /* glsl */ `
      uniform vec3 uDeep;
      uniform vec3 uMid;
      uniform vec3 uShallow;
      varying vec2 vUv;
      varying float vElev;
      void main() {
        float d = smoothstep(0.1, 0.9, vUv.y);
        vec3 col = mix(uShallow, uDeep, d);
        col = mix(col, uMid, smoothstep(0.3, 0.6, d));
        // Wave crests brighten
        float crest = smoothstep(0.14, 0.24, vElev);
        col += vec3(0.04, 0.07, 0.11) * crest;
        // Subtle shimmer on peaks
        float shimmer = pow(max(0.0, vElev * 3.0), 2.0) * 0.15;
        col += vec3(0.03, 0.05, 0.08) * shimmer;
        gl_FragColor = vec4(col, 0.95);
      }
    `,
    transparent: true,
    side: THREE.DoubleSide,
    depthWrite: true,
  });

  const mesh = new THREE.Mesh(geom, mat);
  mesh.rotation.x = -Math.PI / 2;
  mesh.position.set(0, -0.04, centreZ);
  // Prevent water from blocking launcher / radar raycasts
  mesh.raycast = () => {};

  return {
    mesh,
    update(t) {
      mat.uniforms.uTime.value = t;
    },
  };
}

// ═══════════════════════════════════════════════════════════════════════
// 2. TERRAIN ENHANCEMENT — vertex noise + biome vertex colors
//    Mutates geometry in-place. Call BEFORE creating the mesh material.
// ═══════════════════════════════════════════════════════════════════════
export function enhanceTerrainGeometry(geom, extrudeDepth, isIsland, side) {
  const pos = geom.attributes.position;
  const count = pos.count;
  const colors = new Float32Array(count * 3);

  // Side-dependent base green
  let base;
  if (isIsland) {
    base =
      side === 'north' ? [0.20, 0.34, 0.18] : [0.24, 0.38, 0.20];
  } else {
    base =
      side === 'north' ? [0.24, 0.42, 0.19] : [0.29, 0.46, 0.21];
  }

  for (let i = 0; i < count; i++) {
    const x = pos.getX(i);
    const y = pos.getY(i);
    const z = pos.getZ(i);
    const isTop = Math.abs(z - extrudeDepth) < 0.05;

    if (isTop) {
      // Displace top vertices → faceted low-poly look
      const n =
        Math.sin(x * 17.3 + y * 11.7) * Math.cos(x * 7.1 - y * 13.3);
      pos.setZ(i, z + n * 0.10 + 0.03);

      // Biome color variation
      const v1 = Math.sin(x * 5.3 + y * 3.7) * 0.035;
      const v2 = Math.cos(x * 8.1 - y * 6.3) * 0.025;
      colors[i * 3] = base[0] + v1;
      colors[i * 3 + 1] = base[1] + v1 + v2;
      colors[i * 3 + 2] = base[2] + v1 * 0.5;
    } else {
      // Cliff / side faces — earthy rock
      const rock = Math.sin(x * 11.0 + y * 9.0) * 0.02;
      colors[i * 3] = 0.21 + rock;
      colors[i * 3 + 1] = 0.19 + rock;
      colors[i * 3 + 2] = 0.14;
    }
  }

  pos.needsUpdate = true;
  geom.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  geom.computeVertexNormals();
}

// ═══════════════════════════════════════════════════════════════════════
// 3. LOW-POLY TREES — InstancedMesh cones + trunks
// ═══════════════════════════════════════════════════════════════════════
export function scatterTrees(scene, terrainPolys, saabToSceneFn, locations) {
  const rand = mulberry32(42);

  // Convert terrain polygons to scene-space coordinate arrays
  const scenePolys = terrainPolys.map((p) => ({
    ...p,
    sc: p.coords.map((c) => saabToSceneFn(c[0], c[1])),
  }));

  // Location exclusion zones (scene coords)
  const locSC = locations.map((l) => saabToSceneFn(l.x, l.y));

  // Generate tree positions via rejection sampling
  const treePos = [];
  for (const poly of scenePolys) {
    const { sc } = poly;
    let minX = Infinity,
      maxX = -Infinity,
      minZ = Infinity,
      maxZ = -Infinity;
    for (const [x, z] of sc) {
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (z < minZ) minZ = z;
      if (z > maxZ) maxZ = z;
    }

    const area = (maxX - minX) * (maxZ - minZ);
    const density = poly.subtype === 'mainland' ? 0.008 : 0.02;
    const target = Math.min(Math.floor(area * density), 140);

    let placed = 0,
      attempts = 0;
    while (placed < target && attempts < target * 20) {
      attempts++;
      const x = minX + rand() * (maxX - minX);
      const z = minZ + rand() * (maxZ - minZ);

      if (!pointInPoly(x, z, sc)) continue;

      // Clear zone around landmarks (~5 km radius)
      let skip = false;
      for (const [lx, lz] of locSC) {
        if ((x - lx) ** 2 + (z - lz) ** 2 < 25) {
          skip = true;
          break;
        }
      }
      if (skip) continue;

      treePos.push([x, z]);
      placed++;
    }
  }

  if (treePos.length === 0) return;

  // ── Instanced geometries ──
  // Bottom foliage cone (wider)
  const fGeo1 = new THREE.ConeGeometry(0.28, 0.7, 5);
  const fMat1 = new THREE.MeshStandardMaterial({
    color: 0x2a6620,
    roughness: 0.92,
    flatShading: true,
  });
  const foliage1 = new THREE.InstancedMesh(fGeo1, fMat1, treePos.length);

  // Top foliage cone (narrower, higher)
  const fGeo2 = new THREE.ConeGeometry(0.19, 0.50, 5);
  const fMat2 = new THREE.MeshStandardMaterial({
    color: 0x1e5018,
    roughness: 0.92,
    flatShading: true,
  });
  const foliage2 = new THREE.InstancedMesh(fGeo2, fMat2, treePos.length);

  // Trunks (square cross-section for low-poly)
  const tGeo = new THREE.CylinderGeometry(0.05, 0.07, 0.28, 4);
  const tMat = new THREE.MeshStandardMaterial({
    color: 0x4a3018,
    roughness: 0.95,
    flatShading: true,
  });
  const trunks = new THREE.InstancedMesh(tGeo, tMat, treePos.length);

  const dummy = new THREE.Object3D();
  for (let i = 0; i < treePos.length; i++) {
    const [x, z] = treePos[i];
    const s = 0.6 + rand() * 0.9; // scale 0.6–1.5
    const rot = rand() * Math.PI * 2;

    // Trunk
    dummy.position.set(x, 0.32 + 0.14 * s, z);
    dummy.scale.set(s, s, s);
    dummy.rotation.y = rot;
    dummy.updateMatrix();
    trunks.setMatrixAt(i, dummy.matrix);

    // Bottom foliage
    dummy.position.set(x, 0.32 + 0.28 * s + 0.35 * s, z);
    dummy.updateMatrix();
    foliage1.setMatrixAt(i, dummy.matrix);

    // Top foliage
    dummy.position.set(x, 0.32 + 0.28 * s + 0.70 * s, z);
    dummy.scale.set(s * 0.75, s * 0.75, s * 0.75);
    dummy.updateMatrix();
    foliage2.setMatrixAt(i, dummy.matrix);
  }

  // Disable raycasting so trees don't block launcher/radar drags
  foliage1.raycast = () => {};
  foliage2.raycast = () => {};
  trunks.raycast = () => {};

  scene.add(trunks);
  scene.add(foliage1);
  scene.add(foliage2);
}

// ═══════════════════════════════════════════════════════════════════════
// 4. ROADS — lines connecting same-side locations
// ═══════════════════════════════════════════════════════════════════════
export function createRoads(scene, locations, saabToSceneFn) {
  const scLocs = locations.map((l) => {
    const [x, z] = saabToSceneFn(l.x, l.y);
    return { ...l, sx: x, sz: z };
  });

  const pts = [];
  const done = new Set();

  for (let i = 0; i < scLocs.length; i++) {
    const a = scLocs[i];
    // Connect to nearest 2 same-side neighbors
    const neighbors = scLocs
      .map((b, j) => ({
        j,
        dist: Math.hypot(a.sx - b.sx, a.sz - b.sz),
      }))
      .filter((n) => n.j !== i && scLocs[n.j].side === a.side)
      .sort((x, y) => x.dist - y.dist)
      .slice(0, 2);

    for (const { j } of neighbors) {
      const key = `${Math.min(i, j)}-${Math.max(i, j)}`;
      if (done.has(key)) continue;
      done.add(key);
      const b = scLocs[j];
      pts.push(a.sx, 0.34, a.sz, b.sx, 0.34, b.sz);
    }
  }

  if (!pts.length) return;

  const geom = new THREE.BufferGeometry();
  geom.setAttribute(
    'position',
    new THREE.BufferAttribute(new Float32Array(pts), 3),
  );
  const line = new THREE.LineSegments(
    geom,
    new THREE.LineBasicMaterial({
      color: 0x8a8a68,
      transparent: true,
      opacity: 0.30,
    }),
  );
  line.raycast = () => {};
  scene.add(line);
}

// ═══════════════════════════════════════════════════════════════════════
// 5. RADAR SCAN DOME — reusable rotating pie-sweep for AWACS / other
//    "this thing is scanning the airspace" visual cues.
//
//    Carries its own `userData.update(t)` callback so the caller just has
//    to add the group to a parent and tick `update(elapsedSec)` per frame.
//    `range` is in scene units (= km at the project's SCALE = 0.001) and
//    sets the radius of both the static full-circle silhouette ring and
//    the rotating sweep slice.
// ═══════════════════════════════════════════════════════════════════════
export function createRadarScanDome(range, color, speed = 0.5) {
  const group = new THREE.Group();
  const pivot = new THREE.Group();
  group.add(pivot);

  // Static full-range ring (doesn't rotate — silhouette only)
  const ringPts = [];
  for (let i = 0; i <= 64; i++) {
    const a = (i / 64) * Math.PI * 2;
    ringPts.push(new THREE.Vector3(Math.sin(a) * range, 0, Math.cos(a) * range));
  }
  group.add(new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(ringPts),
    new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.25 }),
  ));

  // Rotating sweep pie slice
  const SWEEP_ANGLE = Math.PI / 4;
  const SEGS = 20;
  const pos = [0, 0, 0];
  for (let i = 0; i <= SEGS; i++) {
    const a = (i / SEGS) * SWEEP_ANGLE;
    pos.push(Math.sin(a) * range, 0, -Math.cos(a) * range);
  }
  const sweepGeom = new THREE.BufferGeometry();
  sweepGeom.setAttribute('position', new THREE.BufferAttribute(new Float32Array(pos), 3));
  const idx = [];
  for (let i = 0; i < SEGS; i++) idx.push(0, i + 1, i + 2);
  sweepGeom.setIndex(idx);
  sweepGeom.computeVertexNormals();
  const sweep = new THREE.Mesh(sweepGeom, new THREE.MeshBasicMaterial({
    color, transparent: true, opacity: 0.18, side: THREE.DoubleSide, depthWrite: false,
  }));
  pivot.add(sweep);

  // Arc edge line (brighter outer rim of the sweep)
  const arcPts = [];
  for (let i = 0; i <= SEGS; i++) {
    const a = (i / SEGS) * SWEEP_ANGLE;
    arcPts.push(new THREE.Vector3(Math.sin(a) * range, 0.01, -Math.cos(a) * range));
  }
  pivot.add(new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(arcPts),
    new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.55 }),
  ));

  group.userData.update = (t) => {
    pivot.rotation.y = t * speed * Math.PI * 2;
  };
  return group;
}

// ═══════════════════════════════════════════════════════════════════════
// 6. COASTLINE HIGHLIGHTS — shore edge lines at waterline
// ═══════════════════════════════════════════════════════════════════════
export function createCoastlines(scene, terrainPolys, saabToSceneFn) {
  for (const poly of terrainPolys) {
    const points = poly.coords.map((c) => {
      const [x, z] = saabToSceneFn(c[0], c[1]);
      return new THREE.Vector3(x, 0.06, z);
    });
    // Close loop
    const [x0, z0] = saabToSceneFn(
      poly.coords[0][0],
      poly.coords[0][1],
    );
    points.push(new THREE.Vector3(x0, 0.06, z0));

    const geom = new THREE.BufferGeometry().setFromPoints(points);
    const line = new THREE.Line(
      geom,
      new THREE.LineBasicMaterial({
        color: poly.subtype === 'mainland' ? 0x5a9a78 : 0x4a8a68,
        transparent: true,
        opacity: 0.40,
      }),
    );
    line.raycast = () => {};
    scene.add(line);
  }
}
