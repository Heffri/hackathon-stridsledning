// App entry: boot Three.js, open WS, wire HUD.
import { createScene } from './scene.js';
import { EntityRegistry } from './entities.js';
import { LauncherRegistry, RedLauncherRegistry } from './launchers.js';
import { SiteRegistry } from './sites.js';
import { wireHud, updateHud, setWsStatus, showWsError, showLayoutStatus, toggleSetupPanel } from './hud.js';
import { initStatusPanel, updateStatusPanel } from './status_panel.js';
import { initLauncherDrag } from './drag_launchers.js';
import { onSelectionChange } from './launcher_selection.js';

const canvas = document.getElementById('view');
const {
  scene, camera, renderer, controls, resetCameraView, animateRadar,
  composer, waterUpdate, setCameraPreset,
} = createScene(canvas);
const registry = new EntityRegistry(scene);
const launchers = new LauncherRegistry(scene);
const redLaunchers = new RedLauncherRegistry(scene);
const sites = new SiteRegistry(scene);
initStatusPanel(canvas, camera, registry);

let latestSnap = null;
// Sync AI dropdowns from snapshot only once after (re)connect. Typed
// responses (red_ai_changed / blue_ai_changed) handle ongoing sync.
let _needsAiSync = true;

// --- WebSocket ---
let ws = null;
function openWs() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.addEventListener('open', () => {
    setWsStatus(true);
    // Sync speed to 1x on connect — backend may retain 50x from a previous session.
    sendCmd({ cmd: 'speed', value: 1 });
  });
  ws.addEventListener('close', () => {
    setWsStatus(false);
    _needsAiSync = true;
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
        const cost = msg.base_cost_usd;
        const costStr = cost ? ` — $${(cost / 1e6).toFixed(1)}M` : '';
        showLayoutStatus(`Applied: ${name} (${n} launchers${costStr})`, true);
      } else if (msg.type === 'blue_ai_changed') {
        showLayoutStatus(`Blue AI: ${msg.name}`, true);
        const bSel = document.getElementById('blue-ai-select');
        if (bSel && msg.slot) bSel.value = msg.slot;
      } else if (msg.type === 'red_ai_changed') {
        showLayoutStatus(`Red AI: ${msg.name}`, true);
        const rSel = document.getElementById('red-ai-select');
        if (rSel && msg.slot) rSel.value = msg.slot;
      } else if (msg.type !== 'phase_change') {
        console.warn('ws unknown typed frame:', msg);
      }
      return;
    }
    latestSnap = msg;
    // Sync AI dropdowns to server state ONCE on (re)connect only.
    // Continuous snapshot sync was reverting user selections before the
    // set_red_ai / set_blue_ai command round-tripped. After the initial
    // sync, typed responses (red_ai_changed / blue_ai_changed) keep
    // the dropdowns in sync.
    if (_needsAiSync) {
      const aiSelect = document.getElementById('blue-ai-select');
      if (aiSelect && msg.blue_ai_slot) aiSelect.value = msg.blue_ai_slot;
      const redAiSelect = document.getElementById('red-ai-select');
      if (redAiSelect && msg.red_ai_slot) redAiSelect.value = msg.red_ai_slot;
      _needsAiSync = false;
    }
    _lastPhase = msg.phase || 'setup';
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

// Force speed slider to 1x on load — browsers may restore a cached
// value from a previous session (form autofill), causing 50x on start.
const _speedSlider = document.getElementById('speed');
if (_speedSlider) {
  _speedSlider.value = '1';
  document.getElementById('speed-val').textContent = '1.0x';
}

// Connect immediately — no intro modal blocking the WS.
openWs();
let _lastPhase = null;

// Keyboard shortcuts — demo-friendly hotkeys for the 4-minute presentation.
// All ignore modifier keys + form-focused states so roster editing is safe.
window.addEventListener('keydown', (ev) => {
  if (ev.ctrlKey || ev.altKey || ev.metaKey) return;
  const t = ev.target;
  if (t && t.matches?.('input, select, textarea')) return;

  switch (ev.key) {
    case 'r': case 'R':
      resetCameraView();
      break;
    case ' ':
      ev.preventDefault();
      sendCmd({ cmd: latestSnap?.phase === 'paused' ? 'resume' : 'pause' });
      break;
    case '+': case '=': {
      const slider = document.getElementById('speed');
      if (slider) {
        slider.value = Math.min(50, parseFloat(slider.value) + 0.5);
        slider.dispatchEvent(new Event('input'));
      }
      break;
    }
    case '-': case '_': {
      const slider = document.getElementById('speed');
      if (slider) {
        slider.value = Math.max(0.5, parseFloat(slider.value) - 0.5);
        slider.dispatchEvent(new Event('input'));
      }
      break;
    }
    case 'm': case 'M':
      if (latestSnap?.phase === 'setup') toggleSetupPanel();
      break;
    // Camera presets — number keys snap to predefined views.
    case '1': setCameraPreset('south'); break;
    case '2': setCameraPreset('topdown'); break;
    case '3': setCameraPreset('north'); break;
    case '4': setCameraPreset('wide'); break;
  }
});
document.getElementById('btn-toggle-setup')?.addEventListener('click', () => {
  toggleSetupPanel();
});
document.getElementById('btn-reset-camera')?.addEventListener('click', () => {
  resetCameraView();
});

// Camera-preset panel — small floating button stack near the existing
// Reset Camera button. Buttons trigger the same setCameraPreset path
// as the 1-4 number keys, so operators who don't know the shortcuts
// still have a discoverable affordance during the live demo.
function _injectCameraPresetButtons() {
  const wrap = document.createElement('div');
  Object.assign(wrap.style, {
    position: 'fixed',
    bottom: '64px',
    left: '16px',
    zIndex: '15',
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    font: '11px/1.2 system-ui, sans-serif',
  });
  const presets = [
    { name: 'south',   label: '1 · South (default)' },
    { name: 'topdown', label: '2 · Top-Down' },
    { name: 'north',   label: '3 · North View' },
    { name: 'wide',    label: '4 · Wide' },
  ];
  for (const p of presets) {
    const btn = document.createElement('button');
    btn.textContent = p.label;
    Object.assign(btn.style, {
      padding: '4px 10px',
      background: 'rgba(20, 30, 48, 0.85)',
      color: '#cfe2ff',
      border: '1px solid rgba(120, 160, 220, 0.4)',
      borderRadius: '4px',
      cursor: 'pointer',
      textAlign: 'left',
    });
    btn.addEventListener('click', () => setCameraPreset(p.name));
    wrap.appendChild(btn);
  }
  document.body.appendChild(wrap);
}
_injectCameraPresetButtons();
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
  const elapsed = performance.now() / 1000 - _startTime;

  // Drag-handler robustness guard: drag is SETUP-only, so outside SETUP
  // controls must be enabled. If a SETUP drag terminates off-canvas
  // (e.g. pointer released on the Start Match button) the usual
  // pointerup/lostpointercapture restore path doesn't fire and
  // controls.enabled stays false — operator can't rotate the camera
  // during the match. Re-enable every RAF tick once we leave SETUP.
  const _phase = latestSnap?.phase || 'setup';
  if (_phase !== 'setup' && controls.enabled === false) {
    controls.enabled = true;
  }

  controls.update();
  animateRadar(elapsed);
  waterUpdate(elapsed);
  if (latestSnap) {
    // On new snapshot: reconcile entities, update HUD, etc.
    if (latestSnap !== _lastSnapProcessed) {
      registry.updateFromSnapshot(latestSnap);
      launchers.updateFromSnapshot(latestSnap);
      redLaunchers.updateFromSnapshot(latestSnap);
      updateHud(latestSnap);
      updateStatusPanel(latestSnap);
      _lastSnapProcessed = latestSnap;
    }
    // Every frame: smooth interpolation + explosion/site animations.
    registry.interpolateEntities();
    sites.updateFromSnapshot(latestSnap);
  }
  composer.render();
}
animate();
