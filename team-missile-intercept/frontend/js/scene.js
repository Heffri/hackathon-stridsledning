// Three.js scene setup: camera, lighting, ground grid, base marker.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { BOREAL_TERRAIN, BOREAL_LOCATIONS } from './terrain_data.js';

// World units: meters. Arena ~150km. We scale the whole world by 0.001 for
// rendering so Three.js works in km (avoids z-fighting and huge numbers).
export const SCALE = 0.001;

// Arena constants (must stay in sync with backend config.py)
export const ARENA_X = 150_000;
export const ARENA_Y = 250_000;
export const BASE_POS = [75_000, 5_000, 0];

export function createScene(canvas) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0a1424);
  scene.fog = new THREE.Fog(0x0a1424, 80, 450);

  // Dusk/dawn gradient skydome. A large inverted sphere with a shader
  // that lerps from a dark-blue zenith (high world Y) to a warm amber
  // horizon (Y ≈ 0). Rendered before everything else via renderOrder
  // = -1 and depthWrite: false so fog and geometry still composite on
  // top. Placed inside the fog so distant arena edges continue to
  // fade out; the sky itself is beyond the fog far plane.
  const skyGeom = new THREE.SphereGeometry(1000, 32, 16);
  const skyMat = new THREE.ShaderMaterial({
    side: THREE.BackSide,
    depthWrite: false,
    uniforms: {
      zenithColor: { value: new THREE.Color(0x0a1524) },
      horizonColor: { value: new THREE.Color(0x2a1a10) },
      glowColor: { value: new THREE.Color(0xffa64a) },
    },
    vertexShader: /* glsl */ `
      varying vec3 vWorldPos;
      void main() {
        vec4 wp = modelMatrix * vec4(position, 1.0);
        vWorldPos = wp.xyz;
        gl_Position = projectionMatrix * viewMatrix * wp;
      }
    `,
    fragmentShader: /* glsl */ `
      uniform vec3 zenithColor;
      uniform vec3 horizonColor;
      uniform vec3 glowColor;
      varying vec3 vWorldPos;
      void main() {
        // Normalised height factor: 0 at horizon, 1 at zenith.
        float h = clamp(vWorldPos.y / 600.0, -0.2, 1.0);
        float topMix = smoothstep(0.0, 0.6, h);
        float glow = smoothstep(0.15, -0.05, h);     // brightest at horizon
        vec3 col = mix(horizonColor, zenithColor, topMix);
        col += glowColor * glow * 0.35;
        gl_FragColor = vec4(col, 1.0);
      }
    `,
  });
  const sky = new THREE.Mesh(skyGeom, skyMat);
  sky.renderOrder = -1;
  scene.add(sky);

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(window.innerWidth, window.innerHeight);

  const camera = new THREE.PerspectiveCamera(
    55,
    window.innerWidth / window.innerHeight,
    0.1,
    2000,
  );
  // Camera pulled south and up to frame the full terrain (≈117 km deep).
  // The terrain centre in Z is roughly -58 (midpoint of [−117, 0]).
  // We sit at Z=+55 (south of the map) at altitude 85, looking toward the
  // centre so both mainland bands and the strait are visible on load.
  camera.position.set(0, 85, 55);
  camera.lookAt(0, 0, -58);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.1;
  controls.target.set(0, 0, -58);

  // Lighting
  const amb = new THREE.AmbientLight(0x6688cc, 0.65);
  scene.add(amb);
  const sun = new THREE.DirectionalLight(0xffe8b0, 1.6);
  sun.position.set(40, 100, 20);
  scene.add(sun);
  // Rim/fill light from south to illuminate the cliff faces of terrain
  const fill = new THREE.DirectionalLight(0x8ab4d8, 0.55);
  fill.position.set(-30, 30, 80);
  scene.add(fill);

  // Arena is asymmetric (150 km wide × 250 km deep to accommodate HGV
  // spawns 180 km north of the base). Ground plane is a rectangle
  // centred on the arena centre, not the base, so the whole fight area
  // is covered.
  // Sea plane and grid sized to the terrain's actual footprint:
  //   width  = 150 km (Saab X 0..1667 at scale 150/1667)
  //   depth  = 117 km (Saab Y 0..1300 at same scale)
  // Centre in Z = midpoint of [SCENE_Z_SOUTH, SCENE_Z_NORTH] = -58.5
  const TERRAIN_WIDTH  = 150;                     // scene units = km
  const TERRAIN_DEPTH_UNITS = (1300 / 1667) * 150; // ≈ 117.0
  const terrainCentreZ = -(TERRAIN_DEPTH_UNITS / 2); // ≈ -58.5
  const grid = makeRectGrid(
    TERRAIN_WIDTH,
    TERRAIN_DEPTH_UNITS,
    1,
    terrainCentreZ,
    0x224466,
    0x152842,
  );
  scene.add(grid);

  // "Sea" plane — slightly deeper blue so the landmasses read as
  // "land above water". Sits a hair below y=0 so extruded terrain
  // (from y=0 up to y=+0.3) doesn't z-fight.
  const groundGeom = new THREE.PlaneGeometry(TERRAIN_WIDTH, TERRAIN_DEPTH_UNITS);
  const groundMat = new THREE.MeshStandardMaterial({
    color: 0x0d2040,   // deeper navy-blue ocean
    roughness: 0.85,
    metalness: 0.08,   // slight sheen
  });
  const ground = new THREE.Mesh(groundGeom, groundMat);
  ground.rotation.x = -Math.PI / 2;
  ground.position.set(0, -0.01, terrainCentreZ);
  scene.add(ground);

  // Boreal Passage terrain — full Saab map extent matching the SVG
  // (viewBox 0 0 1000 780 at 0.6 px/km: 1667 km × 1300 km).
  // Saab coords: X east (0..1667 km), Y SOUTH-positive (0..1300 km).
  // Scene:       X east,              Z = -north (so +Z is south).
  // Full SVG extent — scale = 150/1667, aspect intact, no Y cropping.
  const SAAB_X_WINDOW = [0, 1667];
  const SAAB_Y_WINDOW = [0, 1300];   // full SVG extent, no cropping
  // Derive the scene depth from the same linear scale as the width so
  // the aspect ratio mirrors the SVG (1000 × 780).
  //   scale = 150 km / 1667 km ≈ 0.09001
  //   depth = 1300 km × scale ≈ 117 km
  // Saab Y is SOUTH-positive; scene Z is NORTH-negative, so y_norm=0
  // (top of SVG, north mainland) → scene_z = -117, and y_norm=1
  // (bottom of SVG, south mainland) → scene_z = 0 (where base sits).
  const SCENE_X = [-75, 75];
  const SCALE_KM = 150 / (SAAB_X_WINDOW[1] - SAAB_X_WINDOW[0]); // ~0.09001
  const TERRAIN_DEPTH = (SAAB_Y_WINDOW[1] - SAAB_Y_WINDOW[0]) * SCALE_KM; // ~117 km
  const SCENE_Z_NORTH = -TERRAIN_DEPTH; // scene-north edge (top of SVG)
  const SCENE_Z_SOUTH = 0;              // scene-south edge (base row)
  function saabToScene(x_km, y_km) {
    const xn = (x_km - SAAB_X_WINDOW[0]) / (SAAB_X_WINDOW[1] - SAAB_X_WINDOW[0]);
    const yn = (y_km - SAAB_Y_WINDOW[0]) / (SAAB_Y_WINDOW[1] - SAAB_Y_WINDOW[0]);
    const sx = SCENE_X[0] + xn * (SCENE_X[1] - SCENE_X[0]);
    const sz = SCENE_Z_NORTH + yn * (SCENE_Z_SOUTH - SCENE_Z_NORTH);
    return [sx, sz];
  }
  // Terrain color palette — brighter, readable against the dark ocean.
  // Mainlands: warm olive-green (like terrain maps). Islands: slightly
  // lighter to distinguish from the larger continental masses. Peninsula
  // gets a mid-tone. Side faces (cliff walls) are slightly darker.
  const MAINLAND_TOP_COLOR = 0x3d6b22;  // vivid olive green
  const ISLAND_TOP_COLOR   = 0x4a7a2e;  // lighter island green
  const PENI_TOP_COLOR     = 0x5a7a3a;  // peninsulas slightly lighter

  // Extrusion heights. Using 2 km for mainlands gives dramatic visible
  // relief from the overhead camera. Islands are 1.2 km. These are scene
  // units (1 unit = 1 km), so 2.0 = 2000 m peak height.
  const MAIN_DEPTH  = 2.0;
  const ISLAND_DEPTH = 1.2;

  for (const poly of BOREAL_TERRAIN) {
    const shape = new THREE.Shape();
    for (let i = 0; i < poly.coords.length; i++) {
      const [sx, sz] = saabToScene(poly.coords[i][0], poly.coords[i][1]);
      // Shape lives in local (X, Y); we'll rotate the mesh -π/2 around X
      // so local +Y maps to world -Z. To place the vertex at world Z=sz
      // we therefore pass -sz as the shape's local Y coordinate.
      if (i === 0) shape.moveTo(sx, -sz);
      else shape.lineTo(sx, -sz);
    }
    const isMainland  = poly.subtype === 'mainland';
    const isPeninsula = poly.subtype === 'peninsula';
    const depth = isMainland ? MAIN_DEPTH : ISLAND_DEPTH;

    const geom = new THREE.ExtrudeGeometry(shape, {
      depth,
      bevelEnabled: false,
    });

    const color = isMainland ? MAINLAND_TOP_COLOR
                : isPeninsula ? PENI_TOP_COLOR
                : ISLAND_TOP_COLOR;
    const mat = new THREE.MeshStandardMaterial({
      color,
      roughness: 0.88,
      metalness: 0.0,
      side: THREE.DoubleSide,
    });

    const mesh = new THREE.Mesh(geom, mat);
    // Shape lives in the XY plane; ExtrudeGeometry grows along +Z. Rotate
    // -90° around X so the shape ends up on the ground plane (XZ) and
    // the extrusion grows upward (+Y).
    mesh.rotation.x = -Math.PI / 2;
    mesh.position.y = 0;
    scene.add(mesh);
  }

  // The terrain surface is at world Y=0 (ExtrudeGeometry extrudes downward
  // after the -PI/2 X rotation; the shape cap stays at y=0). Landmarks and
  // mountains sit at Y=0 (on the surface), not at Y=MAIN_DEPTH.
  const TERRAIN_TOP_Y = 0;

  // Boreal Passage location landmarks — named air-bases, capitals, and
  // major cities parsed from the Saab CSV. Each location gets a small 3D
  // structure sitting on top of the extruded terrain (terrain top is at
  // y=0.3, structures start at y=0.32) and a canvas-textured Sprite label
  // above it. Side tinting: north = red accent, south = blue accent, so
  // a judge can spot which coast owns which at a glance.
  for (const loc of BOREAL_LOCATIONS) {
    const [sx, sz] = saabToScene(loc.x, loc.y);
    const group = new THREE.Group();
    const tint = loc.side === 'north' ? 0x442020 : 0x202a44;

    if (loc.subtype === 'air_base') {
      // 1 km runway oriented along X (concrete strip) + small control tower
      // offset to one side. Box dims: X × Y × Z = 1.0 (length) × 0.02
      // (height) × 0.15 (width).
      const runway = new THREE.Mesh(
        new THREE.BoxGeometry(1.0, 0.02, 0.15),
        new THREE.MeshStandardMaterial({ color: 0xb8b8b0, roughness: 0.85 }),
      );
      runway.position.set(0, 0.01, 0);
      group.add(runway);
      const tower = new THREE.Mesh(
        new THREE.BoxGeometry(0.08, 0.12, 0.1),
        new THREE.MeshStandardMaterial({
          color: 0x8a8a88,
          emissive: tint,
          emissiveIntensity: 0.45,
          roughness: 0.7,
        }),
      );
      tower.position.set(0.35, 0.06, 0.2);
      group.add(tower);
    } else if (loc.subtype === 'capital') {
      // Cluster of 5 tall boxes (skyline). Varying heights 0.18..0.35.
      const spec = [
        { w: 0.16, d: 0.15, h: 0.35, x: 0,     z: 0 },
        { w: 0.13, d: 0.13, h: 0.28, x: 0.18,  z: 0.05 },
        { w: 0.15, d: 0.14, h: 0.22, x: -0.15, z: 0.1 },
        { w: 0.12, d: 0.12, h: 0.3,  x: 0.05,  z: -0.15 },
        { w: 0.1,  d: 0.1,  h: 0.18, x: -0.18, z: -0.1 },
      ];
      for (const p of spec) {
        const box = new THREE.Mesh(
          new THREE.BoxGeometry(p.w, p.h, p.d),
          new THREE.MeshStandardMaterial({
            color: 0x333338,
            emissive: tint,
            emissiveIntensity: 0.55,
            roughness: 0.75,
          }),
        );
        box.position.set(p.x, p.h / 2, p.z);
        group.add(box);
      }
    } else {
      // major_city: 3 mid-rise buildings in a smaller footprint.
      const spec = [
        { w: 0.12, d: 0.11, h: 0.2,  x: 0,    z: 0 },
        { w: 0.1,  d: 0.1,  h: 0.14, x: 0.1,  z: 0.05 },
        { w: 0.1,  d: 0.09, h: 0.09, x: -0.09, z: -0.08 },
      ];
      for (const p of spec) {
        const box = new THREE.Mesh(
          new THREE.BoxGeometry(p.w, p.h, p.d),
          new THREE.MeshStandardMaterial({
            color: 0x444448,
            emissive: tint,
            emissiveIntensity: 0.5,
            roughness: 0.75,
          }),
        );
        box.position.set(p.x, p.h / 2, p.z);
        group.add(box);
      }
    }

    group.position.set(sx, TERRAIN_TOP_Y + 0.02, sz);
    scene.add(group);

    const label = makeTextSprite(loc.name, loc.side);
    // Sit the label above the terrain top surface + building heights.
    label.position.set(sx, TERRAIN_TOP_Y + 1.2, sz);
    label.scale.set(4, 1, 1);
    scene.add(label);
  }

  // The old blue base cylinder (CylinderGeometry(2.0, 2.5, 1.2, 12) at
  // BASE_POS) was removed in Milestone G: the base is now just one site
  // among many, rendered by the SiteRegistry as a small coloured ring
  // along with the Saab-named air bases, capital, and major cities.
  // `BASE_POS` stays exported above for scene-origin math elsewhere.

  // Weapon range arcs are now rendered per-launcher by
  // frontend/js/launchers.js (LauncherRegistry), centred on each
  // launcher's actual world position and dimming when that launcher
  // reloads. The old base-centred stack is gone — it visually conflicted
  // with the per-launcher arcs and implied every weapon fires from the
  // base, which is no longer true after Milestone F.

  // Mountain peaks — ConeGeometry clusters placed on the mainland ridges
  // matching the mountain symbols (mtn-n / mtn-s) in the SVG. Northern
  // mountains sit on the north mainland plateau; southern on the south.
  // Heights in scene km (1 unit = 1 km), base radii in scene km.
  const MTN_PEAKS = [
    // ── Northern mountain clusters (Saab X, Saab Y = south-positive) ──
    { x: 260, y: 130, h: 3.5, r: 3.2 },
    { x: 340, y: 170, h: 2.8, r: 2.5 },
    { x: 200, y: 220, h: 2.2, r: 2.0 },
    { x: 480, y: 100, h: 3.0, r: 2.8 },
    { x: 560, y: 160, h: 2.4, r: 2.2 },
    { x: 700, y: 90,  h: 3.2, r: 3.0 },
    { x: 820, y: 140, h: 2.6, r: 2.4 },
    { x: 950, y: 120, h: 3.0, r: 2.7 },
    { x: 1080, y: 170, h: 2.5, r: 2.3 },
    { x: 1200, y: 110, h: 2.8, r: 2.6 },
    { x: 1350, y: 150, h: 2.0, r: 1.8 },
    { x: 1480, y: 200, h: 2.3, r: 2.1 },
    // ── Southern mountain clusters ──
    { x: 100, y: 1130, h: 2.8, r: 2.5 },
    { x: 220, y: 1180, h: 2.4, r: 2.2 },
    { x: 380, y: 1160, h: 3.0, r: 2.8 },
    { x: 520, y: 1190, h: 2.2, r: 2.0 },
    { x: 650, y: 1140, h: 2.6, r: 2.4 },
    { x: 780, y: 1170, h: 2.0, r: 1.8 },
    { x: 920, y: 1150, h: 2.8, r: 2.6 },
    { x: 1060, y: 1180, h: 2.4, r: 2.2 },
    { x: 1200, y: 1200, h: 3.2, r: 3.0 },
    { x: 1360, y: 1180, h: 2.6, r: 2.4 },
    { x: 1520, y: 1160, h: 2.2, r: 2.0 },
  ];
  const mtnMat = new THREE.MeshStandardMaterial({
    color: 0x8a8070,        // rocky grey-tan
    roughness: 0.95,
    metalness: 0.0,
  });
  const snowMat = new THREE.MeshStandardMaterial({
    color: 0xe8e8ec,        // snow cap
    roughness: 0.6,
    metalness: 0.0,
  });
  for (const m of MTN_PEAKS) {
    const [sx, sz] = saabToScene(m.x, m.y);
    // Main peak
    const coneGeom = new THREE.ConeGeometry(m.r, m.h, 7, 1);
    const cone = new THREE.Mesh(coneGeom, mtnMat);
    cone.position.set(sx, TERRAIN_TOP_Y + m.h / 2, sz);
    scene.add(cone);
    // Snow cap (upper 30% of peak)
    const capH = m.h * 0.3;
    const capR = m.r * 0.35;
    const capGeom = new THREE.ConeGeometry(capR, capH, 7, 1);
    const cap = new THREE.Mesh(capGeom, snowMat);
    cap.position.set(sx, TERRAIN_TOP_Y + m.h - capH * 0.4, sz);
    scene.add(cap);
  }

  // Compass (simple N marker)
  const nLabel = new THREE.Mesh(
    new THREE.SphereGeometry(0.8, 8, 6),
    new THREE.MeshStandardMaterial({ color: 0xffcc44, emissive: 0x775500 }),
  );
  const [nx, ny] = worldToSceneXY(ARENA_X / 2, ARENA_Y - 2000);
  nLabel.position.set(nx, 2, ny);
  scene.add(nLabel);

  // Resize
  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  });

  return { scene, camera, renderer, controls };
}

// Backend coords: X=east, Y=north, Z=up (meters).
// Scene coords:   X=east,  Y=up,    Z=south  (three.js default axes).
//
// X: arena center (ARENA_X/2 = 75 km) maps to scene X=0; scale = SCALE=0.001.
//
// Z: derived through the Saab terrain coordinate chain so that simulation
//    entities land on the correct terrain polygon:
//      1. world_y (m) → saab_y (km): saab_y = 280 + (1 − wy/250 000) × 800
//         (the sim arena window [0..250 km world] maps to Saab Y [280..1080 km])
//      2. saab_y → scene_z: scene_z = −TERRAIN_DEPTH + saab_y × (TERRAIN_DEPTH/1300)
//         (full-map scale: 1300 km → 117 km scene depth)
//    Combining:  scene_z = _SZ_S − world_y × _SZ_SLOPE
//
// Verified anchors:
//   world_y =   5 000 m → scene_z ≈ −21.2  (Saab ~1064 km, south mainland)
//   world_y = 245 000 m → scene_z ≈ −90.3  (Saab ~296 km,  north mainland)
const _TD    = (1300 / 1667) * 150;                   // terrain depth ≈ 117.0 scene-km
const _SZ_S  = -_TD * (1 - 1080 / 1300);             // scene_z at sim south edge ≈ −19.8
const _SZ_SL = 800 * _TD / (1300 * ARENA_Y);         // scene_z slope ≈ 0.000288 per m

export function worldToScene(x, y, z) {
  return [
    (x - ARENA_X / 2) * SCALE,     // east, centred on arena mid-point
    z * SCALE,                      // up → +Y
    _SZ_S - y * _SZ_SL,            // north → −Z (aligned to Saab terrain)
  ];
}

export function worldToSceneXY(x, y) {
  return [(x - ARENA_X / 2) * SCALE, _SZ_S - y * _SZ_SL];
}

// Rectangular floor grid — THREE.GridHelper is always square, so we build
// one manually from LineSegments whose extent matches the rectangular
// ground plane exactly. `spacing` is in scene units (1 unit = 1 km); every
// 10th line is drawn in `mainColor`, the rest in `subColor`, reproducing
// the main/sub colour hierarchy GridHelper provided.
function makeRectGrid(width, depth, spacing, centreZ, mainColor, subColor) {
  const halfW = width / 2;
  const halfD = depth / 2;
  const minX = -halfW;
  const minZ = centreZ - halfD;
  const maxZ = centreZ + halfD;
  const mainPositions = [];
  const subPositions = [];
  // East-west lines (vary Z).
  const nZ = Math.round(depth / spacing);
  for (let i = 0; i <= nZ; i++) {
    const z = minZ + i * spacing;
    const arr = (i % 10 === 0) ? mainPositions : subPositions;
    arr.push(minX, 0, z, halfW, 0, z);
  }
  // North-south lines (vary X).
  const nX = Math.round(width / spacing);
  for (let i = 0; i <= nX; i++) {
    const x = minX + i * spacing;
    const arr = (i % 10 === 0) ? mainPositions : subPositions;
    arr.push(x, 0, minZ, x, 0, maxZ);
  }
  const group = new THREE.Group();
  for (const [positions, color] of [[mainPositions, mainColor], [subPositions, subColor]]) {
    if (positions.length === 0) continue;
    const geom = new THREE.BufferGeometry();
    geom.setAttribute(
      'position',
      new THREE.BufferAttribute(new Float32Array(positions), 3),
    );
    const mat = new THREE.LineBasicMaterial({
      color,
      transparent: true,
      opacity: 0.55,
    });
    group.add(new THREE.LineSegments(geom, mat));
  }
  return group;
}

// Canvas-textured Sprite label used for Boreal Passage landmarks. A 256×64
// offscreen canvas with a dark translucent fill, a side-coloured border
// (red for north, blue for south), and white bold text. Sprites billboard
// to the camera so labels always face the operator. depthTest:false keeps
// them readable even when they pass behind closer terrain silhouettes.
function makeTextSprite(text, side) {
  const canvas = document.createElement('canvas');
  canvas.width = 256;
  canvas.height = 64;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = 'rgba(10, 14, 24, 0.78)';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.strokeStyle = side === 'north' ? '#c85050' : '#5080c8';
  ctx.lineWidth = 3;
  ctx.strokeRect(1.5, 1.5, canvas.width - 3, canvas.height - 3);
  ctx.fillStyle = '#ffffff';
  ctx.font = 'bold 22px sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, canvas.width / 2, canvas.height / 2);
  const tex = new THREE.CanvasTexture(canvas);
  tex.minFilter = THREE.LinearFilter;
  tex.magFilter = THREE.LinearFilter;
  const mat = new THREE.SpriteMaterial({
    map: tex,
    depthTest: false,
    transparent: true,
  });
  return new THREE.Sprite(mat);
}
