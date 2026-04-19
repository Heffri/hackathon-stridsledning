// App entry: boot Three.js, open WS, wire HUD.
import { createScene } from './scene.js';
import { EntityRegistry } from './entities.js';
import { LauncherRegistry, RedLauncherRegistry } from './launchers.js';
import { SiteRegistry } from './sites.js';
import { wireHud, updateHud, setWsStatus } from './hud.js';
import { initStatusPanel, updateStatusPanel } from './status_panel.js';

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
    // M-TIER2-PHASE: typed frames carry a `type` field (phase_change,
    // error). Snapshots are untyped. Full UI handling of phase_change
    // / error lands in Subtask D; guard here so a typed message can't
    // get mistaken for a snapshot and crash the HUD.
    if (msg && typeof msg.type === 'string') return;
    latestSnap = msg;
  });
}

function sendCmd(obj) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
}

wireHud(sendCmd);
openWs();

// --- Render loop ---
function animate() {
  requestAnimationFrame(animate);
  controls.update();
  if (latestSnap) {
    registry.updateFromSnapshot(latestSnap);
    launchers.updateFromSnapshot(latestSnap);
    redLaunchers.updateFromSnapshot(latestSnap);
    sites.updateFromSnapshot(latestSnap);
    updateHud(latestSnap);
    updateStatusPanel(latestSnap);
  }
  renderer.render(scene, camera);
}
animate();
