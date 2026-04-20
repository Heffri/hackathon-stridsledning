// App entry: boot Three.js, open WS, wire HUD.
import { createScene } from './scene.js';
import { EntityRegistry } from './entities.js';
import { LauncherRegistry, RedLauncherRegistry } from './launchers.js';
import { SiteRegistry } from './sites.js';
import { wireHud, updateHud, setWsStatus, showWsError } from './hud.js';
import { initStatusPanel, updateStatusPanel } from './status_panel.js';
import { initLauncherDrag } from './drag_launchers.js';
import { onSelectionChange } from './launcher_selection.js';

const canvas = document.getElementById('view');
const { scene, camera, renderer, controls } = createScene(canvas);
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
      } else if (msg.type !== 'phase_change') {
        console.warn('ws unknown typed frame:', msg);
      }
      return;
    }
    latestSnap = msg;
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
openWs();

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
function animate() {
  requestAnimationFrame(animate);
  controls.update();
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
