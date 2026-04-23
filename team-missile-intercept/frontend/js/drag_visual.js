// drag_visual.js — unified visual-only drag for any draggable scene object.
//
// Replaces drag_radars.js. Works for:
//   • Radar stations    (radarHitMeshes from scene.js)
//   • Red launchers     (getHitMeshes() on RedLauncherRegistry)
//   • Landmark groups   (landmarkHitMeshes from scene.js)
//
// API: initVisualDrag({ renderer, camera, controls, getHitMeshes })
//   getHitMeshes() — called each time we need to raycast; returns the
//   current flat array of candidate meshes. Each mesh's .parent must be
//   the THREE.Group to drag (or set userData.dragGroup explicitly).
//
// Contract with callers:
//   • Dragging sets group.userData.dragging = true so snapshot-driven
//     registries (RedLauncherRegistry) know not to override the position.
//   • Y position is preserved — radars sit at y=0, landmarks at y=0.32.
//   • Full pointer-capture + safety-net robustness matches drag_launchers.js.
import * as THREE from 'three';

const CLICK_DRAG_THRESHOLD_PX = 5;

export function initVisualDrag({ renderer, camera, controls, getHitMeshes }) {
  const canvas = renderer.domElement;
  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  const groundPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
  const hitPoint = new THREE.Vector3();

  let armed = null;             // { group, dragY, pointerId, downX, downY }
  let dragging = null;          // { group, dragY }
  let capturedPointerId = null;

  function updateNDC(ev) {
    const r = canvas.getBoundingClientRect();
    pointer.x = ((ev.clientX - r.left) / r.width) * 2 - 1;
    pointer.y = -((ev.clientY - r.top) / r.height) * 2 + 1;
  }

  function groupUnderPointer() {
    const meshes = getHitMeshes();
    if (!meshes || !meshes.length) return null;
    raycaster.setFromCamera(pointer, camera);
    const hits = raycaster.intersectObjects(meshes, false);
    if (!hits.length) return null;
    const obj = hits[0].object;
    // Explicit override takes priority (e.g. landmark hit child vs group).
    return obj.userData.dragGroup ?? obj.parent;
  }

  // Single-source cleanup — called from all termination paths and safety nets.
  function restoreIdle() {
    if (dragging) {
      dragging.group.userData.dragging = false;
      dragging = null;
    }
    armed = null;
    if (capturedPointerId != null) {
      try { canvas.releasePointerCapture(capturedPointerId); } catch (_) {}
      capturedPointerId = null;
    }
    if (controls) controls.enabled = true;
    if (canvas.style.cursor === 'grab' || canvas.style.cursor === 'grabbing') {
      canvas.style.cursor = '';
    }
  }

  function moveToGround(group, dragY) {
    raycaster.setFromCamera(pointer, camera);
    if (raycaster.ray.intersectPlane(groundPlane, hitPoint)) {
      group.position.set(hitPoint.x, dragY, hitPoint.z);
    }
  }

  canvas.addEventListener('pointermove', ev => {
    if (dragging) {
      updateNDC(ev);
      moveToGround(dragging.group, dragging.dragY);
      return;
    }
    if (armed) {
      const dx = ev.clientX - armed.downX;
      const dy = ev.clientY - armed.downY;
      if (dx * dx + dy * dy >= CLICK_DRAG_THRESHOLD_PX ** 2) {
        if (armed.group) {
          dragging = { group: armed.group, dragY: armed.dragY };
          dragging.group.userData.dragging = true;
          armed = null;
          if (controls) controls.enabled = false;
          canvas.style.cursor = 'grabbing';
          updateNDC(ev);
          moveToGround(dragging.group, dragging.dragY);
        } else {
          // Threshold on empty canvas = orbit gesture, yield to OrbitControls.
          armed = null;
        }
      }
      return;
    }
    // Idle hover — grab cursor over draggable objects only.
    updateNDC(ev);
    const g = groupUnderPointer();
    if (g) {
      canvas.style.cursor = 'grab';
    } else if (canvas.style.cursor === 'grab') {
      canvas.style.cursor = '';
    }
  });

  // Capture phase — fires before OrbitControls' bubble-phase listener.
  // On a hit: stopPropagation prevents OrbitControls from seeing the event
  // so the camera never starts an orbit before we take over.
  canvas.addEventListener('pointerdown', ev => {
    if (ev.button !== 0) return;
    updateNDC(ev);
    const group = groupUnderPointer();
    if (group) {
      ev.stopPropagation();
      ev.preventDefault();
      armed = {
        group,
        dragY: group.position.y,  // preserve object's ground offset
        pointerId: ev.pointerId,
        downX: ev.clientX,
        downY: ev.clientY,
      };
      try {
        canvas.setPointerCapture(ev.pointerId);
        capturedPointerId = ev.pointerId;
      } catch (_) {}
    } else {
      // Empty canvas — don't capture; let OrbitControls orbit freely.
      armed = { group: null, dragY: 0, pointerId: ev.pointerId, downX: ev.clientX, downY: ev.clientY };
    }
  }, true /* capture phase */);

  canvas.addEventListener('pointerup', ev => {
    if (ev.button !== 0) return;
    restoreIdle();
  });

  canvas.addEventListener('pointercancel', () => {
    restoreIdle();
  });

  // Safety nets — prevent OrbitControls staying disabled on interrupted gestures.
  canvas.addEventListener('lostpointercapture', () => {
    if (dragging || armed || (controls && !controls.enabled)) restoreIdle();
  });
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') restoreIdle();
  });
  window.addEventListener('blur', () => restoreIdle());
}
