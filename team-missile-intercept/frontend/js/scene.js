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
  scene.fog = new THREE.Fog(0x0a1424, 100, 500);

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
  // Pull camera south of the base, medium altitude (~25 km world → 25 units
  // at SCALE=0.001), looking north and slightly up so high-altitude entities
  // (ballistic threats at 30-40 km) clearly arc down from above the horizon.
  // Three.js axes: +X=east, +Y=up, -Z=north. Camera is south-east of base
  // looking toward the deep arena.
  // Position: 18 east, 25 up, 55 south. OrbitControls target slightly north
  // and above the base so the battle volume fills the view.
  // Camera pulled further back + aimed deeper into the 250 km arena so
  // HGV / ballistic spawn borders at Z ≈ -175 are in the frame.
  camera.position.set(30, 50, 110);
  camera.lookAt(0, 12, -70);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.1;
  controls.target.set(0, 12, -70);

  // Lighting
  const amb = new THREE.AmbientLight(0x5577aa, 0.5);
  scene.add(amb);
  const sun = new THREE.DirectionalLight(0xffe0aa, 1.0);
  sun.position.set(40, 80, 40);
  scene.add(sun);

  // Arena is asymmetric (150 km wide × 250 km deep to accommodate HGV
  // spawns 180 km north of the base). Ground plane is a rectangle
  // centred on the arena centre, not the base, so the whole fight area
  // is covered. Grid uses the larger dimension so gridlines extend
  // through the full depth (few east-west gridlines drape off the edge,
  // fine visually).
  const widthUnits = ARENA_X * SCALE;
  const depthUnits = ARENA_Y * SCALE;
  const arenaCentreZ = -(ARENA_Y / 2 - BASE_POS[1]) * SCALE;
  const gridSize = Math.max(widthUnits, depthUnits);
  // 1 division per kilometre — gridSize is in scene units and 1 scene
  // unit = 1 km (SCALE = 0.001). Lets the operator eyeball weapon
  // ranges on the floor: CIWS 4 km = 4 cells, RBS 70 9 km = 9 cells,
  // SLS 12, SLM 40, PAC-3 60, PAC-2 70.
  const gridDivisions = Math.round(gridSize);
  const grid = new THREE.GridHelper(gridSize, gridDivisions, 0x224466, 0x152842);
  grid.position.set(0, 0, arenaCentreZ);
  scene.add(grid);

  // "Sea" plane — slightly deeper blue so the landmasses read as
  // "land above water". Sits a hair below y=0 so extruded terrain
  // (from y=0 up to y=+0.3) doesn't z-fight.
  const groundGeom = new THREE.PlaneGeometry(widthUnits, depthUnits);
  const groundMat = new THREE.MeshStandardMaterial({
    color: 0x0c182a,
    roughness: 0.95,
    metalness: 0.0,
  });
  const ground = new THREE.Mesh(groundGeom, groundMat);
  ground.rotation.x = -Math.PI / 2;
  ground.position.set(0, -0.01, arenaCentreZ);
  scene.add(ground);

  // Boreal Passage terrain — Saab's hand-authored scenario geometry.
  // Saab coords: X east (0..1667 km), Y SOUTH-positive (0..1300 km).
  // Scene:       X east,              Z = -north (so +Z is south).
  // We crop a 1667 × 800 km window (Y 280..1080) which contains the
  // mainland/strait/mainland band + relevant islands, then stretch
  // that window to fit the 150 × 250 km arena. Non-uniform scale is
  // accepted — the demo jury reads "two lands across a strait", not
  // a 1:1 overlay of the Saab reference.
  const SAAB_X_WINDOW = [0, 1667];
  const SAAB_Y_WINDOW = [280, 1080];
  // Map window → arena. Saab Y is SOUTH-positive: low Y is the north
  // edge of Saab's map, high Y is the south edge. Our scene Z is
  // inverted: -Z is north, +Z is south (base at scene Z=0). So the
  // correct mapping sends y_norm=0 (Saab north, top of the CSV) to
  // scene_z = -245 (scene far-north edge), and y_norm=1 (Saab south)
  // to scene_z = +5 (scene south edge, where the base sits). This is
  // the OPPOSITE direction of the task-spec pseudocode — following the
  // pseudocode literally would put the southern mainland in our scene
  // north and vice versa, contradicting the acceptance criteria.
  const SCENE_X = [-75, 75];
  const SCENE_Z_NORTH = -245;   // scene-north edge (y_norm = 0)
  const SCENE_Z_SOUTH = 5;      // scene-south edge (y_norm = 1)
  function saabToScene(x_km, y_km) {
    const xn = (x_km - SAAB_X_WINDOW[0]) / (SAAB_X_WINDOW[1] - SAAB_X_WINDOW[0]);
    const yn = (y_km - SAAB_Y_WINDOW[0]) / (SAAB_Y_WINDOW[1] - SAAB_Y_WINDOW[0]);
    const sx = SCENE_X[0] + xn * (SCENE_X[1] - SCENE_X[0]);
    const sz = SCENE_Z_NORTH + yn * (SCENE_Z_SOUTH - SCENE_Z_NORTH);
    return [sx, sz];
  }
  const MAINLAND_COLOR = 0x2f3a2a;  // dark olive
  const ISLAND_COLOR   = 0x2b382c;  // slightly different tint
  const EXTRUDE_DEPTH  = 0.3;       // scene units = 300 m above sea level
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
    const geom = new THREE.ExtrudeGeometry(shape, {
      depth: EXTRUDE_DEPTH,
      bevelEnabled: false,
    });
    const isIsland = poly.subtype !== 'mainland';
    const mat = new THREE.MeshStandardMaterial({
      color: isIsland ? ISLAND_COLOR : MAINLAND_COLOR,
      roughness: 0.92,
      metalness: 0.0,
      // DoubleSide: shape is built with a Y-flip (see shape.moveTo above)
      // which inverts winding, so the top cap's normal would otherwise
      // point down and back-face cull against the overhead camera.
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

    group.position.set(sx, 0.32, sz);
    scene.add(group);

    const label = makeTextSprite(loc.name, loc.side);
    // Sit the label ~700 m above sea so it clears the tallest (0.35 tall)
    // capital buildings with headroom and reads well from the default
    // overhead camera.
    label.position.set(sx, 1.0, sz);
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
// Scene coords:   X=east,  Y=up,    Z=south (=-north)  (three default axes).
// We center the scene on the blue base so the camera can sit at origin.
const BASE_X = BASE_POS[0];
const BASE_Y = BASE_POS[1];

export function worldToScene(x, y, z) {
  return [
    (x - BASE_X) * SCALE,           // east → +X
    z * SCALE,                      // up → +Y
    -(y - BASE_Y) * SCALE,          // north → -Z
  ];
}

export function worldToSceneXY(x, y) {
  return [(x - BASE_X) * SCALE, -(y - BASE_Y) * SCALE];
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
