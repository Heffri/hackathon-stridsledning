// Launcher drag-drop + click-to-select handler (M-TIER2-J Part 1 / 2).
//
// Pointer-down on a launcher Group in SETUP phase arms a potential
// drag; pointer-move past a pixel-distance threshold promotes it to a
// real drag (updates the Group position via a ground-plane raycast),
// pointer-up emits a `place_launcher` WS command. If the pointer-up
// arrives without the threshold being exceeded, the event is
// interpreted as a click — the launcher is selected (Subtask D) and
// the Remove button in the SETUP ribbon enables.
//
// Click on empty scene space in SETUP clears the selection. Pointer-
// up outside SETUP does nothing.
//
// The server validates land-only placement
// (terrain.point_on_south_land) — on rejection the next snapshot
// restores the old position and the phase-chip red-flash fires via
// the typed-frame error route wired in main.js.
//
// OrbitControls is disabled for the duration of an actual drag so the
// camera doesn't move under the operator. Cursor flips to `grab` on
// hover and `grabbing` during drag.
import * as THREE from 'three';
import { SCALE } from './scene.js';
import { setSelectedLauncherId } from './launcher_selection.js';

// Click-vs-drag pixel threshold. A pointer-down + pointer-up pair with
// total travel distance below this counts as a click; at/above it the
// event is treated as a drag. 5 px is a conservative value — trackpad
// jitter during a "stationary" click typically stays under 2-3 px.
const CLICK_DRAG_THRESHOLD_PX = 5;

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

  // Issue #23: suppress browser-default behaviours that leak into the
  // 3D canvas.
  //   - contextmenu: right-click would otherwise pop the browser menu
  //     (Copy / Reload / Back), which is never useful on a WebGL surface.
  //   - selectstart: belt-and-braces against the left-drag text-selection
  //     box, in addition to the CSS `user-select: none` rule.
  // Installed once at setup, never per-frame.
  canvas.addEventListener('contextmenu', (ev) => ev.preventDefault());
  canvas.addEventListener('selectstart', (ev) => ev.preventDefault());

  // Pointer-down state. `armed` holds the info needed to tell click
  // apart from drag on pointer-up / pointer-move. `dragging` holds the
  // active drag once the threshold is exceeded. Mutually exclusive.
  let armed = null;    // { mesh, id, downX, downY }
  let dragging = null; // { mesh, id }

  function updatePointerNDC(ev) {
    const rect = canvas.getBoundingClientRect();
    pointer.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1;
  }

  // Issue #23: raycast only against launcher box meshes, never the range
  // rings. The previous recursive intersect walked the whole Group
  // (box + THREE.Line arc); on glancing pointer paths the arc could be
  // the first hit and confuse the picker. Boxes are the sole selectable
  // affordance — return a flat list of them.
  function boxesForHitTest() {
    const boxes = [];
    for (const mesh of launchers.byId.values()) {
      boxes.push(mesh.box);
    }
    return boxes;
  }

  function findLauncherIdUnderPointer() {
    const boxes = boxesForHitTest();
    if (boxes.length === 0) return null;
    raycaster.setFromCamera(pointer, camera);
    // Non-recursive: `boxes` is already the authoritative candidate list.
    // The box's parent is the launcher Group whose userData carries the
    // stable launcherId stamped at construction in launchers.js.
    const hits = raycaster.intersectObjects(boxes, false);
    if (!hits.length) return null;
    const group = hits[0].object.parent;
    return group?.userData?.launcherId ?? null;
  }

  canvas.addEventListener('pointermove', (ev) => {
    updatePointerNDC(ev);
    // Once we're actually dragging, forward raycast to ground plane.
    if (dragging) {
      raycaster.setFromCamera(pointer, camera);
      if (raycaster.ray.intersectPlane(groundPlane, hitPoint)) {
        // Keep Group at y=0 (ground level); child box and arc have their
        // own local offsets.
        dragging.mesh.group.position.set(hitPoint.x, 0, hitPoint.z);
      }
      return;
    }
    // Armed pointer — promote to a real drag once the pointer travels
    // past the click threshold. Uses absolute pixel delta against the
    // pointer-down position (not NDC) so the threshold is resolution-
    // independent.
    if (armed) {
      const dx = ev.clientX - armed.downX;
      const dy = ev.clientY - armed.downY;
      if (dx * dx + dy * dy >= CLICK_DRAG_THRESHOLD_PX * CLICK_DRAG_THRESHOLD_PX) {
        const { mesh, id } = armed;
        armed = null;
        dragging = { mesh, id };
        mesh.group.userData.dragging = true;
        if (controls) controls.enabled = false;
        canvas.style.cursor = 'grabbing';
        // Snap Group position to pointer on the first drag tick so the
        // launcher doesn't jump from its old pose.
        raycaster.setFromCamera(pointer, camera);
        if (raycaster.ray.intersectPlane(groundPlane, hitPoint)) {
          mesh.group.position.set(hitPoint.x, 0, hitPoint.z);
        }
      }
      return;
    }
    // Idle hover state (not armed, not dragging).
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
    if (!id) {
      // Pointer-down on empty scene: remember the position so a click
      // on empty space (no drag) can clear the selection on pointer-up.
      armed = { mesh: null, id: null, downX: ev.clientX, downY: ev.clientY };
      return;
    }
    const mesh = launchers.byId.get(id);
    if (!mesh) return;
    // Arm a potential click or drag. We don't commit to either yet —
    // pointermove promotes to drag past threshold; pointerup without
    // promotion is a click.
    armed = { mesh, id, downX: ev.clientX, downY: ev.clientY };
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

  canvas.addEventListener('pointerup', (ev) => {
    // Drag-in-progress: commit the new position.
    if (dragging) {
      endDrag(true, ev);
      return;
    }
    // Armed without being promoted = click. Select (or deselect on
    // empty space).
    if (armed) {
      const { id } = armed;
      armed = null;
      if (ev.pointerId != null) canvas.releasePointerCapture?.(ev.pointerId);
      if (getPhase() === 'setup') {
        setSelectedLauncherId(id || null);
      }
    }
  });
  canvas.addEventListener('pointercancel', (ev) => {
    if (dragging) {
      endDrag(false, ev);
      return;
    }
    // Cancel while armed = drop the click intent without changing
    // selection.
    if (armed) {
      armed = null;
      if (ev.pointerId != null) canvas.releasePointerCapture?.(ev.pointerId);
    }
  });
}
