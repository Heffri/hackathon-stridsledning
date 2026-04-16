// HUD controls + log rendering.

// Real-world names for interceptor kinds, shown in the launch banner.
const INTERCEPTOR_NAMES = {
  ciws: 'Lvkv 90',
  short_sam: 'RBS 70 NG',
  med_sam: 'IRIS-T SLM',
  long_sam: 'Patriot PAC-2 GEM+',
  hit_to_kill: 'Patriot PAC-3 MSE',
};

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

// Track events we've already shown so snapshot replay doesn't re-fire.
const _seenEvents = new Set();
let _bannerHideTimer = null;

export function updateHud(snap) {
  setText('stat-t', snap.t.toFixed(1));
  setText('stat-wave', snap.wave ?? 0);
  setText('stat-waves', snap.total_waves ?? 0);
  setText('stat-active-t', snap.stats?.active_threats ?? 0);
  setText('stat-intercepts', snap.stats?.intercepts ?? 0);
  setText('stat-leaked', snap.stats?.leaked ?? 0);

  renderLog('log-red', snap.red_log || []);
  renderLog('log-blue', snap.blue_log || []);

  // Launch banner: trigger on new "launch" events in this snapshot
  for (const ev of snap.events || []) {
    if (ev.type !== 'launch') continue;
    const key = `launch_${ev.id}`;
    if (_seenEvents.has(key)) continue;
    _seenEvents.add(key);
    showLaunchBanner(ev.kind, ev.target);
  }
  // Keep the set from growing forever
  if (_seenEvents.size > 500) {
    _seenEvents.clear();
  }

  // Ammo rows (falls back to ∞ when server omits the field, e.g. legacy runs)
  const ammo = snap.ammo || {};
  for (const kind of ['ciws', 'short_sam', 'med_sam', 'long_sam', 'hit_to_kill']) {
    const el = document.getElementById(`ammo-${kind}`);
    if (!el) continue;
    const info = ammo[kind];
    if (!info) {
      el.textContent = '∞';
      el.classList.remove('low', 'empty', 'reloading');
      continue;
    }
    const { current, capacity, reloading, reload_remaining } = info;
    const row = el.closest('.ammo-row');
    if (reloading) {
      el.textContent = `RELOAD ${reload_remaining.toFixed(0)}s`;
      row?.classList.add('reloading');
      row?.classList.remove('low');
    } else {
      el.textContent = `${current}/${capacity}`;
      row?.classList.remove('reloading');
      const ratio = capacity > 0 ? current / capacity : 1;
      if (current === 0) {
        row?.classList.add('empty');
      } else {
        row?.classList.remove('empty');
      }
      if (ratio < 0.25 && current > 0) {
        row?.classList.add('low');
      } else {
        row?.classList.remove('low');
      }
    }
  }
}

function showLaunchBanner(interceptorKind, targetId) {
  const el = document.getElementById('launch-banner');
  if (!el) return;
  const name = INTERCEPTOR_NAMES[interceptorKind] || interceptorKind;
  el.innerHTML =
    `<div class="lb-title">LAUNCH: ${escapeHtml(name)}</div>` +
    `<div class="lb-line">vs Target #${targetId}</div>`;
  el.classList.remove('hidden');
  if (_bannerHideTimer) clearTimeout(_bannerHideTimer);
  _bannerHideTimer = setTimeout(() => {
    el.classList.add('hidden');
  }, 2000);
}

// Called by main.js on websocket reset so Reset button clears the banner
// state and banner re-triggers for the next game.
export function resetHudEventTracking() {
  _seenEvents.clear();
  const el = document.getElementById('launch-banner');
  el?.classList.add('hidden');
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
