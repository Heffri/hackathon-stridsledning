// Launcher drag-drop handler (M-TIER2-J Part 1, Subtask E).
//
// Pointer-down on a launcher Group in SETUP phase starts a drag; pointer-
// move updates the Group position via a ground-plane raycast; pointer-up
// emits a `place_launcher` WS command. The server validates land-only
// placement (terrain.point_on_south_land) — on rejection the next
// snapshot restores the old position and the phase-chip red-flash fires
// via the typed-frame error route wired in main.js.
//
// OrbitControls is disabled for the duration of a drag so the camera
// doesn't move under the operator. Cursor flips to `grab` on hover and
// `grabbing` during drag.
//
// Not wired outside SETUP: pointer handlers short-circuit when
// `getPhase() !== 'setup'` so launchers are immovable during RUNNING /
// PAUSED / FINISHED.
import * as THREE from 'three';
import { SCALE } from './scene.js';

// Inverse of worldToSceneXY. Base position (75_000, 5_000) is the
// scene origin; world→scene is (dx, -dy) * SCALE with SCALE=0.001.
const WORLD_UNIT = 1 / SCALE;    // 1000
const BASE_WX = 75_000;
const BASE_WY = 5_000;

function sceneToWorldXY(sx, sz) {
  const wx = sx * WORLD_UNIT + BASE_WX;
  const wy = -sz * WORLD_UNIT + BASE_WY;
  return [wx, wy];
}

export function initLauncherDrag({
  renderer,
  camera,
  controls,
  launchers,
  sendCmd,
  getPhase,
}) {
  const canvas = renderer.domElement;
  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  const groundPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
  const hitPoint = new THREE.Vector3();

  let dragging = null; // { mesh, id }

  function updatePointerNDC(ev) {
    const rect = canvas.getBoundingClientRect();
    pointer.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1;
  }

  function groupsForHitTest() {
    const groups = [];
    for (const mesh of launchers.byId.values()) {
      groups.push(mesh.group);
    }
    return groups;
  }

  function findLauncherIdUnderPointer() {
    const groups = groupsForHitTest();
    if (groups.length === 0) return null;
    raycaster.setFromCamera(pointer, camera);
    // Recursive intersectObjects walks through each Group's children
    // (box mesh + arc line). The arc is a THREE.Line which does hit-test
    // only along the line itself, not as a disc, so we rely on the box
    // for click targeting.
    const hits = raycaster.intersectObjects(groups, true);
    if (!hits.length) return null;
    let obj = hits[0].object;
    while (obj && !obj.userData?.launcherId) {
      obj = obj.parent;
    }
    return obj?.userData?.launcherId ?? null;
  }

  canvas.addEventListener('pointermove', (ev) => {
    updatePointerNDC(ev);
    if (dragging) {
      raycaster.setFromCamera(pointer, camera);
      if (raycaster.ray.intersectPlane(groundPlane, hitPoint)) {
        // Keep Group at y=0 (ground level); child box and arc have their
        // own local offsets.
        dragging.mesh.group.position.set(hitPoint.x, 0, hitPoint.z);
      }
      return;
    }
    if (getPhase() === 'setup') {
      const id = findLauncherIdUnderPointer();
      canvas.style.cursor = id ? 'grab' : '';
    } else if (canvas.style.cursor) {
      canvas.style.cursor = '';
    }
  });

  canvas.addEventListener('pointerdown', (ev) => {
    if (getPhase() !== 'setup') return;
    if (ev.button !== 0) return; // left button only
    updatePointerNDC(ev);
    const id = findLauncherIdUnderPointer();
    if (!id) return;
    const mesh = launchers.byId.get(id);
    if (!mesh) return;
    dragging = { mesh, id };
    mesh.group.userData.dragging = true;
    if (controls) controls.enabled = false;
    canvas.style.cursor = 'grabbing';
    canvas.setPointerCapture?.(ev.pointerId);
    ev.preventDefault();
  });

  function endDrag(commit, ev) {
    if (!dragging) return;
    const { mesh, id } = dragging;
    dragging = null;
    mesh.group.userData.dragging = false;
    if (controls) controls.enabled = true;
    canvas.style.cursor = '';
    if (ev && ev.pointerId != null) {
      canvas.releasePointerCapture?.(ev.pointerId);
    }
    if (commit) {
      const sx = mesh.group.position.x;
      const sz = mesh.group.position.z;
      const [wx, wy] = sceneToWorldXY(sx, sz);
      sendCmd({
        cmd: 'place_launcher',
        launcher_id: id,
        pos: [wx, wy],
      });
    }
  }

  canvas.addEventListener('pointerup', (ev) => endDrag(true, ev));
  canvas.addEventListener('pointercancel', (ev) => endDrag(false, ev));
}
