// HUD controls + log rendering.

// Real-world names for interceptor kinds, shown in the launch banner.
const INTERCEPTOR_NAMES = {
  ciws: 'Lvkv 90',
  rbs_70: 'RBS 70 NG',
  iris_t_sls: 'IRIS-T SLS (RBS 98)',
  iris_t_slm: 'IRIS-T SLM',
  pac_2: 'Patriot PAC-2 GEM+',
  pac_3: 'Patriot PAC-3 MSE',
};

// Mesh-colour swatch per interceptor kind (mirrors scene.js range arcs
// and entities.js bodyMat colours). Used as a 6×6 px dot prefix so an
// operator can scan weapon usage at a glance.
const WEAPON_COLORS = {
  ciws: '#d9b36a',
  rbs_70: '#4a8a3a',
  iris_t_sls: '#ff9944',
  iris_t_slm: '#ff8c1a',
  pac_2: '#ff69b4',
  pac_3: '#a855f7',
};

export function wireHud(sendCmd) {
  const bindClick = (id, cmd) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('click', () => sendCmd(cmd));
  };
  bindClick('btn-start', { cmd: 'start' });
  bindClick('btn-pause', { cmd: 'pause' });
  // Reset also clears the match overlay / launch banner locally so the
  // HUD reads "fresh" the instant the operator clicks, without waiting
  // for the next WebSocket snapshot.
  document.getElementById('btn-reset')?.addEventListener('click', () => {
    sendCmd({ cmd: 'reset' });
    resetHudEventTracking();
  });

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

  // Per-site HP bars (Milestone I — replaces the old leak counters).
  renderSiteHp(snap.sites || []);

  // Blue budget bar (Milestone I).
  renderBudget(snap.stats || {});

  // End-of-match overlay (Milestone I).
  renderMatchOverlay(snap.winner || null);

  // Ammo rows (falls back to ∞ when server omits the field, e.g. legacy runs)
  const ammo = snap.ammo || {};
  for (const kind of ['ciws', 'rbs_70', 'iris_t_sls', 'iris_t_slm', 'pac_2', 'pac_3']) {
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

// Site subtype → dot-colour + badge label. Keeps the HUD colour coding
// consistent with the 3D scene rings (sites.js SITE_COLORS).
const SITE_SUBTYPE_COLORS = {
  capital: '#ff5050',
  air_base: '#ff9944',
  major_city: '#ffd24a',
  base: '#5a9cff',
};
const SITE_SUBTYPE_LABEL = {
  capital: 'Capital',
  air_base: 'Airbase',
  major_city: 'City',
  base: 'Base',
};

function renderSiteHp(sitesList) {
  const el = document.getElementById('site-damage-list');
  if (!el) return;
  if (!sitesList.length) {
    el.innerHTML = '<div class="site-damage-empty">waiting for scenario…</div>';
    return;
  }
  el.innerHTML = sitesList
    .map((s) => {
      const color = SITE_SUBTYPE_COLORS[s.subtype] || '#888';
      const kind = SITE_SUBTYPE_LABEL[s.subtype] || s.subtype;
      const hp = Math.max(0, s.hp || 0);
      const hpMax = Math.max(1, s.hp_max || 100);
      const pct = Math.min(100, (hp / hpMax) * 100);
      let barCls = 'site-hp-bar-inner';
      if (hp <= 0) barCls += ' dead';
      else if (pct < 30) barCls += ' low';
      return (
        `<div class="site-hp-row">` +
        `<div class="site-hp-head">` +
        `<span class="site-damage-dot" style="background:${color}"></span>` +
        `<span class="site-damage-name">${escapeHtml(s.name)}</span>` +
        `<span class="site-damage-sub">${kind}</span>` +
        `<span class="site-hp-val">${hp}/${hpMax}</span>` +
        `</div>` +
        `<div class="site-hp-bar-outer">` +
        `<div class="${barCls}" style="width:${pct}%"></div>` +
        `</div>` +
        `</div>`
      );
    })
    .join('');
}

function formatMoney(n) {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n}`;
}

function renderBudget(stats) {
  const curEl = document.getElementById('budget-current');
  const maxEl = document.getElementById('budget-max');
  const barEl = document.getElementById('budget-bar-inner');
  if (!curEl || !maxEl || !barEl) return;
  const cur = stats.blue_budget;
  const max = stats.blue_budget_max;
  if (cur == null || max == null) {
    curEl.textContent = '—';
    maxEl.textContent = '—';
    barEl.style.width = '0%';
    return;
  }
  curEl.textContent = formatMoney(cur);
  maxEl.textContent = formatMoney(max);
  const pct = max > 0 ? Math.max(0, Math.min(100, (cur / max) * 100)) : 0;
  barEl.style.width = `${pct}%`;
  barEl.classList.remove('low', 'critical', 'empty');
  if (cur <= 0) barEl.classList.add('empty');
  else if (pct < 15) barEl.classList.add('critical');
  else if (pct < 35) barEl.classList.add('low');
}

const OVERLAY_TEXT = {
  blue: { title: 'BLUE WINS', sub: 'Red force neutralised — all waves defeated.' },
  red:  { title: 'RED WINS',  sub: 'Blue defence collapsed — site destroyed or budget exhausted.' },
  draw: { title: 'DRAW',      sub: 'Safety time cap reached.' },
};

function renderMatchOverlay(winner) {
  const el = document.getElementById('match-overlay');
  if (!el) return;
  if (!winner) {
    el.classList.add('hidden');
    return;
  }
  const text = OVERLAY_TEXT[winner] || { title: winner.toUpperCase(), sub: '' };
  const titleEl = document.getElementById('mo-title');
  const subEl = document.getElementById('mo-sub');
  if (titleEl) {
    titleEl.textContent = text.title;
    titleEl.className = `mo-title mo-${winner}`;
  }
  if (subEl) subEl.textContent = text.sub;
  el.classList.remove('hidden');
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
  document.getElementById('launch-banner')?.classList.add('hidden');
  document.getElementById('match-overlay')?.classList.add('hidden');
}

export function setWsStatus(connected) {
  const el = document.getElementById('ws-status');
  if (!el) return;
  el.textContent = connected ? 'connected' : 'disconnected';
  el.className = connected ? 'connected' : 'disconnected';
  // Update the sibling dot in the new sidebar footer.
  const dot = el.closest('.sb-footer')?.querySelector('.ws-dot');
  if (dot) {
    if (connected) {
      dot.style.background = 'var(--accent-green, #50d9a0)';
      dot.style.boxShadow = '0 0 6px rgba(80, 217, 160, 0.75)';
    } else {
      dot.style.background = '#ff5a5a';
      dot.style.boxShadow = 'none';
    }
  }
}

function setText(id, v) {
  const el = document.getElementById(id);
  if (el) el.textContent = String(v);
}

// Keep a bounded tail of the log so DOM-diff stays cheap at high entry
// counts. With `renderLog` rewriting innerHTML every tick, rendering 80
// entries 15 Hz is ~1200 div creations / second — still fine. The cap
// is here in case scenarios produce hundreds of entries.
const LOG_TAIL = 120;

function renderLog(id, entries) {
  const el = document.getElementById(id);
  if (!el) return;
  // Preserve whether the user has scrolled up to read history: only
  // auto-scroll if they were already pinned to the bottom.
  const pinned = Math.abs(el.scrollHeight - el.clientHeight - el.scrollTop) < 4;
  const tail = entries.slice(-LOG_TAIL);
  el.innerHTML = tail.map(formatLogLine).join('');
  if (pinned) el.scrollTop = el.scrollHeight;
}

// Format one raw backend log line into coloured HTML.
//
// Blue lines look like:
//   "[ 42.3s] pac_3 [FALLBACK] → cruise_sub (hp 20/30, 2 in flight, …)"
//   "[ 50.1s] ciws [CIWS] → drone (…)"
//   "[ 30.0s] iris_t_slm → cruise_sub (…)"
// Red lines are currently just wave announcements:
//   "[  2.0s] Wave 1 launched (3 threats)"
//
// We look for a "[TIMESTAMP] <token>" prefix where <token> is a known
// interceptor kind; if found, render a colour dot + class the whole line
// by the priority tag it contains.
function formatLogLine(raw) {
  const safe = escapeHtml(raw);
  // Detect trailing tags (colour takes precedence of seriousness).
  let cls = '';
  if (/\[LAST RESORT\]/.test(raw)) cls = 'log-last-resort';
  else if (/\[FALLBACK\]/.test(raw)) cls = 'log-fallback';
  else if (/\[CIWS\]/.test(raw)) cls = 'log-ciws';

  // Highlight the tag token itself so it stands out even inside the
  // coloured-class background.
  const withTag = safe
    .replace('[LAST RESORT]', '<span class="log-tag log-tag-lastresort">[LAST RESORT]</span>')
    .replace('[FALLBACK]', '<span class="log-tag log-tag-fallback">[FALLBACK]</span>')
    .replace('[CIWS]', '<span class="log-tag log-tag-ciws">[CIWS]</span>');

  // Weapon-colour dot: take the first whitespace-separated token AFTER
  // the "[Ts]" timestamp. Matches interceptor kind strings exactly.
  const m = raw.match(/^\[\s*[\d.]+s\]\s+(\w+)/);
  let dotHtml = '';
  if (m && WEAPON_COLORS[m[1]]) {
    dotHtml = `<span class="log-dot" style="background:${WEAPON_COLORS[m[1]]}"></span>`;
  }

  return `<div class="${cls}">${dotHtml}${withTag}</div>`;
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}
