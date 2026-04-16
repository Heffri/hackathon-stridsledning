// Three.js scene setup: camera, lighting, ground grid, base marker.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// World units: meters. Arena ~150km. We scale the whole world by 0.001 for
// rendering so Three.js works in km (avoids z-fighting and huge numbers).
export const SCALE = 0.001;

// Arena constants (must stay in sync with backend config.py)
export const ARENA_X = 150_000;
export const ARENA_Y = 150_000;
export const BASE_POS = [75_000, 5_000, 0];

export function createScene(canvas) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0a1424);
  scene.fog = new THREE.Fog(0x0a1424, 80, 300);

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
  camera.position.set(18, 25, 55);
  camera.lookAt(0, 6, -30);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.1;
  // Aim the orbit pivot a bit into the arena and up — this tilts the
  // default view upward so ballistics entering from 35 km altitude are
  // framed above the horizon line, not at screen top edge.
  controls.target.set(0, 6, -30);

  // Lighting
  const amb = new THREE.AmbientLight(0x5577aa, 0.5);
  scene.add(amb);
  const sun = new THREE.DirectionalLight(0xffe0aa, 1.0);
  sun.position.set(40, 80, 40);
  scene.add(sun);

  // Ground plane (150x150km → 150x150 units at SCALE)
  const gridSize = ARENA_X * SCALE;
  const gridDivisions = 30;
  const grid = new THREE.GridHelper(gridSize, gridDivisions, 0x224466, 0x152842);
  grid.position.set(0, 0, 0);
  scene.add(grid);

  const groundGeom = new THREE.PlaneGeometry(gridSize, gridSize);
  const groundMat = new THREE.MeshStandardMaterial({
    color: 0x0e1a2c,
    roughness: 0.95,
    metalness: 0.0,
  });
  const ground = new THREE.Mesh(groundGeom, groundMat);
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -0.01;
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
