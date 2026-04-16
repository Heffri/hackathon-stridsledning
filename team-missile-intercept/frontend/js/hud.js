// HUD controls + log rendering.

export function wireHud(sendCmd) {
  const bindClick = (id, cmd) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('click', () => sendCmd(cmd));
  };
  bindClick('btn-start', { cmd: 'start' });
  bindClick('btn-pause', { cmd: 'pause' });
  bindClick('btn-reset', { cmd: 'reset' });

  const speed = document.getElementById('speed');
  const speedVal = document.getElementById('speed-val');
  speed.addEventListener('input', () => {
    const v = parseFloat(speed.value);
    speedVal.textContent = `${v.toFixed(1)}x`;
    sendCmd({ cmd: 'speed', value: v });
  });
}

export function updateHud(snap) {
  setText('stat-t', snap.t.toFixed(1));
  setText('stat-wave', snap.wave ?? 0);
  setText('stat-waves', snap.total_waves ?? 0);
  setText('stat-active-t', snap.stats?.active_threats ?? 0);
  setText('stat-intercepts', snap.stats?.intercepts ?? 0);
  setText('stat-leaked', snap.stats?.leaked ?? 0);

  renderLog('log-red', snap.red_log || []);
  renderLog('log-blue', snap.blue_log || []);
}

export function setWsStatus(connected) {
  const el = document.getElementById('ws-status');
  if (!el) return;
  el.textContent = connected ? 'connected' : 'disconnected';
  el.className = connected ? 'connected' : 'disconnected';
}

function setText(id, v) {
  const el = document.getElementById(id);
  if (el) el.textContent = String(v);
}

function renderLog(id, entries) {
  const el = document.getElementById(id);
  if (!el) return;
  el.innerHTML = entries
    .slice(-6)
    .map((s) => `<div>${escapeHtml(s)}</div>`)
    .join('');
  el.scrollTop = el.scrollHeight;
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}
