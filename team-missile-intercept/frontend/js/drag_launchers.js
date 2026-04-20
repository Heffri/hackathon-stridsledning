// Launcher drag-drop + click-to-select handler (M-TIER2-J Part 1 / 2
// + Issue #26 W12).
//
// Click-to-select works in every phase (SETUP / RUNNING / PAUSED /
// FINISHED): pointer-up under the pixel-distance threshold on a
// launcher box selects it; pointer-up under threshold on empty canvas
// deselects. Drag-to-reposition remains SETUP-only — pointer-move past
// threshold on a launcher in SETUP promotes to a drag that updates the
// Group via a ground-plane raycast and emits `place_launcher` on
// pointer-up. Pointer-move past threshold outside SETUP (or on empty
// canvas) is interpreted as an OrbitControls orbit: we clear the armed
// state and let OrbitControls have the gesture.
//
// The server validates land-only placement
// (terrain.point_on_south_land) — on rejection the next snapshot
// restores the old position and the phase-chip red-flash fires via
// the typed-frame error route wired in main.js.
//
// OrbitControls is disabled for the duration of an actual drag so the
// camera doesn't move under the operator. Cursor flips to `grab` on
// hover and `grabbing` during drag (SETUP only — non-SETUP hover leaves
// the cursor alone so the OrbitControls default applies).
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

  // Issue #27 (W12): contextmenu must preventDefault regardless of
  // which element the browser fired it on. W11 attached to the canvas
  // only, so a right-click whose release landed over an HUD panel, the
  // setup ribbon, or the status panel skipped the handler entirely and
  // the browser menu popped. Move to window-level with a guard that
  // covers every game surface and still respects form controls where
  // right-click-to-paste is useful.
  const GAME_SURFACE_SELECTOR =
    '#view, #hud, #setup-ribbon, #match-overlay, #status-panel, #launch-banner';
  window.addEventListener('contextmenu', (ev) => {
    const t = ev.target;
    if (!t) return;
    if (t.matches?.('input, select, textarea')) return;
    if (t.closest?.(GAME_SURFACE_SELECTOR)) {
      ev.preventDefault();
    }
  });
  // selectstart stays belt-and-braces on the canvas alongside the CSS
  // `user-select: none` rule (Issue #23).
  canvas.addEventListener('selectstart', (ev) => ev.preventDefault());

  // Pointer-down state. `armed` holds the info needed to tell click
  // apart from drag on pointer-up / pointer-move. `dragging` holds the
  // active drag once the threshold is exceeded. `capturedPointerId`
  // tracks the pointerId currently owned via setPointerCapture so every
  // termination path — including the visibilitychange / blur /
  // lostpointercapture safety nets wired below — can call
  // releasePointerCapture with the right id even when the originating
  // event object is unavailable (Issue #27).
  let armed = null;    // { mesh, id, downX, downY }
  let dragging = null; // { mesh, id }
  let capturedPointerId = null;

  // Issue #27 (W12): single-source-of-truth cleanup for the drag
  // lifecycle. Called from the safety nets (lostpointercapture,
  // visibilitychange → hidden, window.blur) where we have no event
  // object and no way to know if the gesture was supposed to commit;
  // always discards pending state and restores OrbitControls to a
  // usable idle. Must stay strictly invariant-restoring — side-effects
  // like sendCmd or setSelectedLauncherId belong on the explicit
  // pointerup / pointercancel paths.
  function restoreIdle() {
    if (dragging) {
      dragging.mesh.group.userData.dragging = false;
      dragging = null;
    }
    armed = null;
    if (capturedPointerId != null) {
      try { canvas.releasePointerCapture?.(capturedPointerId); } catch (_) { /* already released */ }
      capturedPointerId = null;
    }
    if (controls) controls.enabled = true;
    if (canvas.style.cursor) canvas.style.cursor = '';
  }

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
    // Armed pointer — decide what the gesture becomes once the pointer
    // travels past the click threshold. Uses absolute pixel delta against
    // the pointer-down position (not NDC) so the threshold is resolution-
    // independent.
    //
    // Issue #26 (W12): drag is SETUP-only. In any other phase, or when
    // the pointer-down landed on empty canvas, a past-threshold move is
    // an OrbitControls orbit — drop the armed state and let OrbitControls
    // take over. No selection change on pointer-up in that case.
    if (armed) {
      const dx = ev.clientX - armed.downX;
      const dy = ev.clientY - armed.downY;
      if (dx * dx + dy * dy >= CLICK_DRAG_THRESHOLD_PX * CLICK_DRAG_THRESHOLD_PX) {
        if (getPhase() === 'setup' && armed.mesh) {
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
        } else {
          armed = null;
        }
      }
      return;
    }
    // Idle hover state (not armed, not dragging). Grab cursor is SETUP-
    // only (there is no drag affordance outside SETUP); let OrbitControls'
    // default cursor show in RUNNING / PAUSED / FINISHED.
    if (getPhase() === 'setup') {
      const id = findLauncherIdUnderPointer();
      canvas.style.cursor = id ? 'grab' : '';
    } else if (canvas.style.cursor) {
      canvas.style.cursor = '';
    }
  });

  canvas.addEventListener('pointerdown', (ev) => {
    if (ev.button !== 0) return; // left button only
    updatePointerNDC(ev);
    const id = findLauncherIdUnderPointer();
    const isSetup = getPhase() === 'setup';
    if (!id) {
      // Pointer-down on empty canvas: remember the start position so a
      // click under threshold on empty space clears the selection.
      // Works in every phase (Issue #26).
      armed = { mesh: null, id: null, downX: ev.clientX, downY: ev.clientY };
      return;
    }
    const mesh = launchers.byId.get(id);
    if (!mesh) return;
    // Arm a potential click or drag. Drag only promotes in SETUP; click-
    // to-select promotes in every phase on pointer-up under threshold.
    armed = { mesh, id, downX: ev.clientX, downY: ev.clientY };
    // Only capture the pointer + preventDefault in SETUP — owning the
    // gesture guarantees the drag discriminator gets a consistent event
    // sequence even if the pointer leaves the canvas mid-drag. Outside
    // SETUP we deliberately leave the gesture to OrbitControls so a
    // drag-past-threshold orbits the camera without fighting our capture.
    if (isSetup) {
      try { canvas.setPointerCapture?.(ev.pointerId); } catch (_) { /* capture may fail in rare races — fall through */ }
      capturedPointerId = ev.pointerId;
      ev.preventDefault();
    }
  });

  function endDrag(commit, ev) {
    if (!dragging) return;
    const { mesh, id } = dragging;
    dragging = null;
    mesh.group.userData.dragging = false;
    if (controls) controls.enabled = true;
    canvas.style.cursor = '';
    // Always release any outstanding capture — fall back to the tracked
    // pointerId when the caller didn't bring one (Issue #27 safety).
    const pid = (ev && ev.pointerId != null) ? ev.pointerId : capturedPointerId;
    if (pid != null) {
      try { canvas.releasePointerCapture?.(pid); } catch (_) { /* already released */ }
    }
    capturedPointerId = null;
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
    // Only the left-button release ends a gesture we own. Right-button
    // releases fired mid-left-drag (e.g. the operator right-clicks while
    // repositioning a launcher) previously committed the half-finished
    // drag as a place_launcher — Issue #27 trigger for "both buttons go
    // dead" as the partial commit left controls in a bad state.
    if (ev.button !== 0) return;
    // Drag-in-progress: commit the new position.
    if (dragging) {
      endDrag(true, ev);
      return;
    }
    // Armed without being promoted = click. Select (or deselect on empty
    // space). Issue #26: works in every phase, not just SETUP. The re-
    // raycast here (rather than trusting armed.id from pointerdown) lets
    // the final-intent interpretation survive tiny camera drift between
    // down and up — if the operator sub-threshold shifts the pointer off
    // the launcher, the final pixel decides.
    if (armed) {
      armed = null;
      const pid = (ev.pointerId != null) ? ev.pointerId : capturedPointerId;
      if (pid != null) {
        try { canvas.releasePointerCapture?.(pid); } catch (_) { /* already released */ }
      }
      capturedPointerId = null;
      updatePointerNDC(ev);
      const hitId = findLauncherIdUnderPointer();
      setSelectedLauncherId(hitId || null);
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
      const pid = (ev && ev.pointerId != null) ? ev.pointerId : capturedPointerId;
      if (pid != null) {
        try { canvas.releasePointerCapture?.(pid); } catch (_) { /* already released */ }
      }
      capturedPointerId = null;
    }
  });

  // Issue #27 (W12) safety nets. None of these fire on the happy path —
  // they exist so a gesture interrupted by a tab switch, a focus loss,
  // or a browser-initiated capture release can't leave OrbitControls
  // permanently disabled. Each reuses restoreIdle so there is exactly
  // one place the drag invariant is restored.
  canvas.addEventListener('lostpointercapture', () => {
    // Fires on every releasePointerCapture we do ourselves (by that
    // point dragging/armed are already null → no-op) AND when the
    // browser force-drops the capture mid-drag. The guard keeps the
    // no-op case free.
    if (dragging || armed || controls?.enabled === false) restoreIdle();
  });
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') restoreIdle();
  });
  window.addEventListener('blur', () => restoreIdle());
}
