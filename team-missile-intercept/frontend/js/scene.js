// Three.js scene setup: camera, lighting, ground grid, base marker.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

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

  const groundGeom = new THREE.PlaneGeometry(widthUnits, depthUnits);
  const groundMat = new THREE.MeshStandardMaterial({
    color: 0x0e1a2c,
    roughness: 0.95,
    metalness: 0.0,
  });
  const ground = new THREE.Mesh(groundGeom, groundMat);
  ground.rotation.x = -Math.PI / 2;
  ground.position.set(0, -0.01, arenaCentreZ);
  scene.add(ground);

  // Blue base marker (a cylinder at BASE_POS, transformed to scene coords)
  const [bx, by] = worldToSceneXY(BASE_POS[0], BASE_POS[1]);
  const base = new THREE.Mesh(
    new THREE.CylinderGeometry(2.0, 2.5, 1.2, 12),
    new THREE.MeshStandardMaterial({ color: 0x3b82f6, emissive: 0x2255aa, emissiveIntensity: 0.5 }),
  );
  base.position.set(bx, 0.6, by);
  scene.add(base);

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
