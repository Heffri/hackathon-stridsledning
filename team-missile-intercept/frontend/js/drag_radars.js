// drag_radars.js — drag radar stations to any position on the map.
// Pure frontend: no server communication, works in all phases.
// Each radar is a single THREE.Group; dragging moves group.position on
// the ground plane (y = 0). The mast mesh has userData.isRadarHit = true
// so we can cheaply raycast against only the hit targets.
//
// Reliability fixes (matching drag_launchers.js robustness level):
//   • setPointerCapture on drag start — drag survives pointer leaving canvas.
//   • capturedPointerId tracked for all release paths.
//   • restoreIdle() single cleanup path shared by safety nets.
//   • lostpointercapture + visibilitychange + blur safety nets ensure
//     OrbitControls is never left disabled after an interrupted drag.
//   • Armed on empty canvas does NOT preventDefault so OrbitControls
//     still receives the event and can orbit normally.
//   • Hover raycast skipped while armed/dragging — no wasted raycasts.
import * as THREE from 'three';

const CLICK_DRAG_THRESHOLD_PX = 5;

export function initRadarDrag({ renderer, camera, controls, radarHitMeshes }) {
  const canvas = renderer.domElement;
  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  const groundPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
  const hitPoint = new THREE.Vector3();

  let armed = null;             // { group, pointerId, downX, downY }
  let dragging = null;          // { group }
  let capturedPointerId = null;

  function updateNDC(ev) {
    const r = canvas.getBoundingClientRect();
    pointer.x = ((ev.clientX - r.left) / r.width) * 2 - 1;
    pointer.y = -((ev.clientY - r.top) / r.height) * 2 + 1;
  }

  function radarGroupUnderPointer() {
    if (!radarHitMeshes || !radarHitMeshes.length) return null;
    raycaster.setFromCamera(pointer, camera);
    const hits = raycaster.intersectObjects(radarHitMeshes, false);
    if (!hits.length) return null;
    // mast is a direct child of the station group
    return hits[0].object.parent;
  }

  // Single-source cleanup — safe to call from any termination path.
  // Never calls sendCmd or changes selection (pure geometry restore).
  function restoreIdle() {
    dragging = null;
    armed = null;
    if (capturedPointerId != null) {
      try { canvas.releasePointerCapture(capturedPointerId); } catch (_) { /* already released */ }
      capturedPointerId = null;
    }
    if (controls) controls.enabled = true;
    // Only clear cursors we own; don't clobber 'grabbing' set by launcher drag.
    if (canvas.style.cursor === 'grab' || canvas.style.cursor === 'grabbing') {
      canvas.style.cursor = '';
    }
  }

  function snapToGround() {
    raycaster.setFromCamera(pointer, camera);
    if (raycaster.ray.intersectPlane(groundPlane, hitPoint)) {
      dragging.group.position.set(hitPoint.x, 0, hitPoint.z);
    }
  }

  canvas.addEventListener('pointermove', ev => {
    // Active drag — forward to ground plane, capture ensures we receive
    // these even when the pointer leaves the canvas.
    if (dragging) {
      updateNDC(ev);
      snapToGround();
      return;
    }

    // Armed — check if pointer has travelled far enough to start a drag.
    if (armed) {
      const dx = ev.clientX - armed.downX;
      const dy = ev.clientY - armed.downY;
      if (dx * dx + dy * dy >= CLICK_DRAG_THRESHOLD_PX ** 2) {
        if (armed.group) {
          // Promote to drag.
          dragging = { group: armed.group };
          armed = null;
          if (controls) controls.enabled = false;
          canvas.style.cursor = 'grabbing';
          updateNDC(ev);
          snapToGround();
        } else {
          // Threshold exceeded on empty canvas — orbit gesture, drop armed.
          armed = null;
        }
      }
      return;
    }

    // Idle hover — show grab cursor over radar stations only.
    updateNDC(ev);
    const g = radarGroupUnderPointer();
    if (g) {
      canvas.style.cursor = 'grab';
    } else if (canvas.style.cursor === 'grab') {
      canvas.style.cursor = '';
    }
  });

  // Capture phase (third arg true) fires BEFORE OrbitControls' bubble-phase
  // listener. This is critical: if we detect a radar hit, we call
  // stopPropagation() so OrbitControls never sees the pointerdown and
  // never starts an orbit gesture. Without this, the camera orbits for
  // a few pixels before our threshold kicks in.
  canvas.addEventListener('pointerdown', ev => {
    if (ev.button !== 0) return;
    updateNDC(ev);
    const group = radarGroupUnderPointer();

    if (group) {
      // Radar hit — own this gesture immediately.
      // stopPropagation prevents OrbitControls (bubble phase) from seeing
      // the event at all, so the camera never starts moving.
      ev.stopPropagation();
      ev.preventDefault();
      armed = { group, pointerId: ev.pointerId, downX: ev.clientX, downY: ev.clientY };
      try {
        canvas.setPointerCapture(ev.pointerId);
        capturedPointerId = ev.pointerId;
      } catch (_) { /* capture unavailable in some test environments */ }
    } else {
      // Empty canvas — let OrbitControls orbit; just track for click detection.
      armed = { group: null, pointerId: ev.pointerId, downX: ev.clientX, downY: ev.clientY };
    }
  }, true /* capture phase */);

  canvas.addEventListener('pointerup', ev => {
    if (ev.button !== 0) return;
    if (dragging) {
      // Drag committed — radar stays where it was dropped (pure frontend).
      restoreIdle();
      return;
    }
    if (armed) {
      // Click under threshold — no selection change for radars (they're
      // not selectable, only draggable). Just clean up.
      restoreIdle();
    }
  });

  canvas.addEventListener('pointercancel', () => {
    restoreIdle();
  });

  // Safety nets — fire when a drag is interrupted by browser/OS.
  // Without these, OrbitControls stays disabled indefinitely.
  canvas.addEventListener('lostpointercapture', () => {
    // Fires both when WE call releasePointerCapture (no-op: already cleaned)
    // and when the browser force-drops the capture mid-drag (needs cleanup).
    if (dragging || armed || (controls && !controls.enabled)) {
      restoreIdle();
    }
  });
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') restoreIdle();
  });
  window.addEventListener('blur', () => restoreIdle());
}
