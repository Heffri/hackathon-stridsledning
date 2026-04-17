// Three.js scene setup: camera, lighting, ground grid, base marker.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { BOREAL_TERRAIN } from './terrain_data.js';

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

  // Blue base marker (a cylinder at BASE_POS, transformed to scene coords)
  const [bx, by] = worldToSceneXY(BASE_POS[0], BASE_POS[1]);
  const base = new THREE.Mesh(
    new THREE.CylinderGeometry(2.0, 2.5, 1.2, 12),
    new THREE.MeshStandardMaterial({ color: 0x3b82f6, emissive: 0x2255aa, emissiveIntensity: 0.5 }),
  );
  base.position.set(bx, 0.6, by);
  scene.add(base);

  // Weapon-range arcs — northern semi-circles around the base coloured
  // by weapon type. Threats always approach from the north, so only the
  // north half of the envelope is relevant. Radii = spec max_range
  // (unscaled by the 1.1 launch margin; this shows the hard kinematic
  // limit). Colours match each weapon's mesh in entities.js.
  const rangeArcs = [
    { name: 'CIWS (Lvkv 90)',        rangeKm:  4, color: 0xd9b36a },
    { name: 'RBS 70 NG',             rangeKm:  9, color: 0x4a8a3a },
    { name: 'IRIS-T SLS (RBS 98)',   rangeKm: 12, color: 0xff9944 },
    { name: 'IRIS-T SLM',            rangeKm: 40, color: 0xff8c1a },
    { name: 'Patriot PAC-3 MSE',     rangeKm: 60, color: 0xa855f7 },
    { name: 'Patriot PAC-2 GEM+',    rangeKm: 70, color: 0xff69b4 },
  ];
  const arcSegments = 96;
  for (const weapon of rangeArcs) {
    const pts = [];
    for (let i = 0; i <= arcSegments; i++) {
      // θ sweeps from 0 (east, +X) through π/2 (north, -Z) to π (west, -X).
      const theta = (i / arcSegments) * Math.PI;
      pts.push(
        new THREE.Vector3(
          Math.cos(theta) * weapon.rangeKm,
          // Sit just above the extruded terrain (0.3 scene units = 300 m)
          // so arcs remain visible even when they overlap land shapes.
          0.35,
          -Math.sin(theta) * weapon.rangeKm,
        ),
      );
    }
    const geom = new THREE.BufferGeometry().setFromPoints(pts);
    const mat = new THREE.LineBasicMaterial({
      color: weapon.color,
      transparent: true,
      opacity: 0.55,
    });
    const arc = new THREE.Line(geom, mat);
    // Arcs are centred on the base (which sits at scene origin after the
    // world-to-scene transform, because BASE_POS is the reference point).
    scene.add(arc);
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
