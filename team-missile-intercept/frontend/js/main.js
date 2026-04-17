// App entry: boot Three.js, open WS, wire HUD.
import { createScene } from './scene.js';
import { EntityRegistry } from './entities.js';
import { wireHud, updateHud, setWsStatus } from './hud.js';
import { initStatusPanel, updateStatusPanel } from './status_panel.js';

const canvas = document.getElementById('view');
const { scene, camera, renderer, controls } = createScene(canvas);
const registry = new EntityRegistry(scene);
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
    try {
      latestSnap = JSON.parse(ev.data);
    } catch (_) { /* ignore */ }
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
    updateHud(latestSnap);
    updateStatusPanel(latestSnap);
  }
  renderer.render(scene, camera);
}
animate();
