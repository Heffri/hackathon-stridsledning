// App entry: boot Three.js, open WS, wire HUD.
import { createScene } from './scene.js';
import { EntityRegistry } from './entities.js';
import { LauncherRegistry, RedLauncherRegistry } from './launchers.js';
import { SiteRegistry } from './sites.js';
import { wireHud, updateHud, setWsStatus, showWsError, showLayoutStatus } from './hud.js';
import { initStatusPanel, updateStatusPanel } from './status_panel.js';
import { initLauncherDrag } from './drag_launchers.js';
import { onSelectionChange } from './launcher_selection.js';
import { showIntro, showSetupTip } from './tutorial.js';

const canvas = document.getElementById('view');
const { scene, camera, renderer, controls, resetCameraView, animateRadar } = createScene(canvas);
const registry = new EntityRegistry(scene);
const launchers = new LauncherRegistry(scene);
const redLaunchers = new RedLauncherRegistry(scene);
const sites = new SiteRegistry(scene);
initStatusPanel(canvas, camera, registry);

let latestSnap = null;

// --- WebSocket ---
let ws = null;
function openWs() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.addEventListener('open', () => setWsStatus(true));
  ws.addEventListener('close', () => {
    setWsStatus(false);
    setTimeout(openWs, 1500);
  });
  ws.addEventListener('error', () => setWsStatus(false));
  ws.addEventListener('message', (ev) => {
    let msg;
    try {
      msg = JSON.parse(ev.data);
    } catch (_) { return; }
    // M-TIER2.7 (W6 audit E follow-up): route typed frames. Snapshots
    // are untyped; typed frames skip latestSnap. phase_change ignored
    // here — snapshot path's `snap.phase` already covers transitions.
    if (msg && typeof msg.type === 'string') {
      if (msg.type === 'error') {
        console.warn('ws error:', msg);
        showWsError(msg.reason || 'unknown');
        // W16: layout-specific errors also echo to the SETUP ribbon
        // status line so the operator sees which slot failed + why.
        if (msg.reason === 'illegal_layout') {
          showLayoutStatus(`Error: ${msg.detail || 'layout rejected'}`, false);
        }
      } else if (msg.type === 'layout_applied') {
        // W16: ack from the backend set_layout handler.
        const name = msg.name || msg.slot || 'layout';
        const n = msg.launcher_count ?? 0;
        showLayoutStatus(`Applied: ${name} (${n} launchers)`, true);
      } else if (msg.type !== 'phase_change') {
        console.warn('ws unknown typed frame:', msg);
      }
      return;
    }
    latestSnap = msg;
    // Show one-shot setup tips when phase first becomes 'setup'.
    const phase = msg.phase || 'setup';
    if (phase === 'setup' && _lastPhase !== 'setup') showSetupTip();
    _lastPhase = phase;
  });
}

function sendCmd(obj) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
}

wireHud(sendCmd);
// M-TIER2-J Part 1: launcher drag-drop is SETUP-phase-only. `getPhase`
// reads from the most recent snapshot so the drag handler can gate
// itself without a dedicated WS subscription.
initLauncherDrag({
  renderer,
  camera,
  controls,
  launchers,
  sendCmd,
  getPhase: () => latestSnap?.phase || 'setup',
});

// Show intro modal on load; open WS only after user dismisses so the
// server isn't stalled waiting while the user reads the intro.
showIntro().then(() => openWs());

// Track last phase to detect SETUP entry for the one-shot tips card.
let _lastPhase = null;

// W13 Phase 7: demo-recovery camera reset. `R` keydown (window-level)
// + the bottom-bar "Reset Camera" button both call resetCameraView.
// Keydown ignores the event when a form control has focus so operator
// typing into the roster dropdown doesn't snap the camera mid-edit.
window.addEventListener('keydown', (ev) => {
  if (ev.key !== 'r' && ev.key !== 'R') return;
  if (ev.ctrlKey || ev.altKey || ev.metaKey) return;
  const t = ev.target;
  if (t && t.matches?.('input, select, textarea')) return;
  resetCameraView();
});
document.getElementById('btn-reset-camera')?.addEventListener('click', () => {
  resetCameraView();
});

// --- Render loop ---
// W13 perf: only the registries that carry per-frame animations
// (EntityRegistry — thrust flame, propeller spin, seeker cone, trail,
// explosion animations; SiteRegistry — HP pulse) need to run on every
// requestAnimationFrame tick. HUD, launcher reload rings, and the
// status panel are pure DOM-write renderers driven by the snapshot,
// and the snapshot only arrives at ~15 Hz — running them on every
// 60 Hz RAF frame re-renders the same values 3-4× per snapshot for
// no visible benefit. Gate those paths on snapshot-reference change.
let _lastSnapProcessed = null;
// Selection is frontend-only state, not snapshot-driven. Clicking a
// launcher mid-snapshot must still refresh the Magazine HUD within one
// RAF tick — invalidate the cache so the next animate() frame re-runs
// the gated HUD/launcher render with the current snapshot.
onSelectionChange(() => { _lastSnapProcessed = null; });
const _startTime = performance.now() / 1000;
function animate() {
  requestAnimationFrame(animate);
  controls.update();
  animateRadar(performance.now() / 1000 - _startTime);
  if (latestSnap) {
    registry.updateFromSnapshot(latestSnap);
    sites.updateFromSnapshot(latestSnap);
    if (latestSnap !== _lastSnapProcessed) {
      launchers.updateFromSnapshot(latestSnap);
      redLaunchers.updateFromSnapshot(latestSnap);
      updateHud(latestSnap);
      updateStatusPanel(latestSnap);
      _lastSnapProcessed = latestSnap;
    }
  }
  renderer.render(scene, camera);
}
animate();
