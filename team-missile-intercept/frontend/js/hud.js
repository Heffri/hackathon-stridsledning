// HUD controls + log rendering.
import {
  getSelectedLauncherId,
  onSelectionChange,
  setSelectedLauncherId,
} from './launcher_selection.js';

// Real-world names for interceptor kinds, shown in the launch banner
// and in the Magazine HUD title when a launcher is selected.
const INTERCEPTOR_NAMES = {
  ciws: 'Lvkv 90',
  rbs_70: 'RBS 70 NG',
  iris_t_sls: 'IRIS-T SLS (RBS 98)',
  iris_t_slm: 'IRIS-T SLM',
  pac_2: 'Patriot PAC-2 GEM+',
  pac_3: 'Patriot PAC-3 MSE',
};

// Issue #25 (W11): static per-kind max-range table for the Magazine
// HUD detail row. Mirrors INTERCEPTOR_SPECS.max_range (m) / 1000 on the
// backend and the RANGE_KM table in launchers.js. Duplicated here to
// avoid importing through the scene module.
const RANGE_KM = {
  ciws: 4,
  rbs_70: 9,
  iris_t_sls: 12,
  iris_t_slm: 40,
  pac_2: 70,
  pac_3: 60,
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
  // Pause lives in the bottom bar. Its click dispatches via the
  // `data-mode` attribute so the same element flips between "Pause"
  // (RUNNING) and "Resume" (PAUSED) — M-TIER2-J Part 1 removed the
  // centre-screen PAUSED overlay so the operator can click-inspect the
  // frozen battlefield; the Pause button flip is the new resume
  // affordance. See renderPauseResumeButton below.
  const pauseBtn = document.getElementById('btn-pause');
  pauseBtn?.addEventListener('click', () => {
    const mode = pauseBtn.dataset.mode || 'pause';
    sendCmd({ cmd: mode });
  });
  document.getElementById('btn-start-match')?.addEventListener('click', () => {
    sendCmd({ cmd: 'start' });
  });
  // M-TIER2-J Part 1: AI Auto button on the SETUP ribbon. M-TIER2-J
  // Part 2 extended the backend handler to also restore the full
  // config-default roster (not just positions). Same WS command;
  // frontend just triggers it.
  document.getElementById('btn-ai-auto')?.addEventListener('click', () => {
    sendCmd({ cmd: 'ai_auto' });
  });
  // M-TIER2-J Part 2 (Issue #6): roster Add button. Reads the kind
  // dropdown + sends add_launcher at a safe south-mainland default pos
  // (near Blue base). Operator drags afterward via the W8 drag handler.
  document.getElementById('btn-add-launcher')?.addEventListener('click', () => {
    const select = document.getElementById('roster-kind');
    const kind = select?.value;
    if (!kind) return;
    // Default spawn pos: centre-south mainland. Matches
    // config.BLUE_BASE_POS (75_000, 5_000) — asserted on-land at
    // backend startup.
    sendCmd({ cmd: 'add_launcher', kind, pos: [75000, 5000] });
  });
  // M-TIER2-J Part 2: roster Remove button. Only enabled when a
  // launcher is click-selected (see launcher_selection.js, wired by
  // drag_launchers.js click handler).
  document.getElementById('btn-remove-launcher')?.addEventListener('click', () => {
    const id = getSelectedLauncherId();
    if (!id) return;
    sendCmd({ cmd: 'remove_launcher', launcher_id: id });
  });
  // Keep the Remove button's disabled state in sync with selection.
  onSelectionChange((id) => {
    const btn = document.getElementById('btn-remove-launcher');
    if (!btn) return;
    btn.disabled = !id;
  });
  // W16: Apply Layout — send set_layout with the selected slot. The
  // backend reads the candidate layouts JSON and swaps the Blue fleet
  // in-place; the next snapshot's `snap.launchers` will reflect the new
  // positions, so the 3D scene re-renders without any extra frontend
  // code. Ack/error is routed by main.js via `onLayoutResponse`.
  document.getElementById('btn-apply-layout')?.addEventListener('click', () => {
    const select = document.getElementById('layout-slot');
    const slot = select?.value;
    if (!slot) return;
    sendCmd({ cmd: 'set_layout', slot });
  });
  // Legacy btn-resume inside the match-overlay: no longer surfaced
  // (paused overlay is hidden; Pause button flips label instead). Click
  // handler kept for back-compat should the overlay ever re-expose it.
  document.getElementById('btn-resume')?.addEventListener('click', () => {
    sendCmd({ cmd: 'resume' });
  });
  // Reset also clears the match overlay / launch banner locally so the
  // HUD reads "fresh" the instant the operator clicks, without waiting
  // for the next WebSocket snapshot.
  document.getElementById('btn-reset')?.addEventListener('click', () => {
    sendCmd({ cmd: 'reset' });
    resetHudEventTracking();
  });
  // End-of-match Restart = reset + start in one click. The two
  // commands go out back-to-back; the server processes them FIFO
  // (reset first lands in SETUP, start then flips to RUNNING) so the
  // next snapshot the client receives shows a fresh RUNNING match.
  // Keeps demo UX as one-click while still exercising the real phase
  // FSM underneath.
  document.getElementById('btn-restart')?.addEventListener('click', () => {
    sendCmd({ cmd: 'reset' });
    sendCmd({ cmd: 'start' });
    resetHudEventTracking();
  });

  const speed = document.getElementById('speed');
  const speedVal = document.getElementById('speed-val');
  // Reserve room for the widest label ("50.0x") so the slider row doesn't
  // reflow as the user drags between single- and two-digit speeds.
  speedVal.style.display = 'inline-block';
  speedVal.style.minWidth = '3.4em';
  speedVal.style.textAlign = 'right';
  speedVal.style.fontVariantNumeric = 'tabular-nums';
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

  // Phase chip + phase-gated overlay (M-TIER2-PHASE).
  renderPhaseChip(snap.phase || 'setup');
  renderSetupRibbon(snap.phase || 'setup');
  renderPhaseOverlay(snap.phase || 'setup', snap.winner || null);
  renderPauseResumeButton(snap.phase || 'setup');

  // M-TIER2-J Part 2: if the currently selected launcher id is no
  // longer in the snapshot (server confirmed the Remove, or ai_auto
  // rebuilt the roster), clear the selection so the Remove button
  // disables and no stale outline is applied.
  const selectedId = getSelectedLauncherId();
  if (selectedId) {
    const stillPresent = (snap.launchers || []).some((l) => l.id === selectedId);
    if (!stillPresent) setSelectedLauncherId(null);
  }

  // Issue #25 (W11): Magazine panel now shows the selected launcher's
  // detail, not a per-kind aggregate. The aggregate view was ambiguous
  // once the roster went dynamic (W9 Part 2) — "PAC-3: 4" could be 1×4
  // or 4×1 launchers. Per-selection detail is unambiguous and also
  // communicates reload / cooldown state per instance.
  renderMagazinePanel(snap);
}

function renderMagazinePanel(snap) {
  const titleEl = document.getElementById('ammo-panel-title');
  const bodyEl = document.getElementById('ammo-panel-body');
  if (!titleEl || !bodyEl) return;

  const selectedId = getSelectedLauncherId();
  const lch = selectedId
    ? (snap.launchers || []).find((l) => l.id === selectedId)
    : null;

  if (!lch) {
    // No selection (or selection no longer in the snapshot — the
    // existing auto-deselect in updateHud handles the latter).
    titleEl.textContent = 'Magazine';
    bodyEl.innerHTML =
      '<div class="ammo-placeholder">Click a launcher to inspect its ' +
      'magazine and reload state.</div>';
    return;
  }

  const name = INTERCEPTOR_NAMES[lch.kind] || lch.kind;
  titleEl.textContent = `Magazine — ${name}`;

  const capacity = lch.capacity ?? 0;
  const current = lch.current ?? 0;
  const ammoPct = capacity > 0 ? Math.max(0, Math.min(100, (current / capacity) * 100)) : 0;

  // Status: reloading > cooldown > ready. cooldown_remaining is 0 when
  // reloading (backend sets it that way) so the precedence is explicit.
  let statusCls, statusLabel;
  if (lch.reloading) {
    const rr = lch.reload_remaining ?? 0;
    statusCls = 'reloading';
    statusLabel = `Reloading ${rr.toFixed(1)}s`;
  } else if ((lch.cooldown_remaining ?? 0) > 0.05) {
    statusCls = 'cooldown';
    statusLabel = `Cooldown ${lch.cooldown_remaining.toFixed(1)}s`;
  } else {
    statusCls = 'ready';
    statusLabel = 'Ready';
  }

  const baseCost = lch.base_cost_usd ?? 0;
  const baseCostStr = baseCost > 0
    ? `$${(baseCost / 1_000_000).toFixed(1)}M`
    : '—';
  const rangeKm = RANGE_KM[lch.kind];
  const rangeStr = rangeKm != null ? `${rangeKm} km` : '—';
  const posX = (lch.pos?.[0] ?? 0) / 1000;
  const posY = (lch.pos?.[1] ?? 0) / 1000;

  bodyEl.innerHTML =
    `<div class="ammo-detail-row">` +
      `<span class="ammo-detail-label">Ammo</span>` +
      `<span class="ammo-detail-val">${current} / ${capacity}</span>` +
    `</div>` +
    `<div class="ammo-bar-outer">` +
      `<div class="ammo-bar-inner" style="width:${ammoPct}%"></div>` +
    `</div>` +
    `<div class="ammo-detail-row">` +
      `<span class="ammo-detail-label">Status</span>` +
      `<span class="ammo-status ${statusCls}">${escapeHtml(statusLabel)}</span>` +
    `</div>` +
    `<div class="ammo-detail-row">` +
      `<span class="ammo-detail-label">Range</span>` +
      `<span class="ammo-detail-val">${rangeStr}</span>` +
    `</div>` +
    `<div class="ammo-detail-row">` +
      `<span class="ammo-detail-label">Base cost</span>` +
      `<span class="ammo-detail-val">${baseCostStr}</span>` +
    `</div>` +
    `<div class="ammo-detail-row">` +
      `<span class="ammo-detail-label">Position</span>` +
      `<span class="ammo-detail-val">(${posX.toFixed(1)}, ${posY.toFixed(1)}) km</span>` +
    `</div>`;
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
  _renderBudgetBar(
    stats.blue_budget, stats.blue_budget_max,
    'budget-current', 'budget-max', 'budget-bar-inner',
  );
  // M-TIER3-RED-BUDGET (Issue #8): mirror bar for Red's spending pool.
  // Fields are null-safe — legacy snapshots without red_budget render
  // the em-dash placeholder instead of crashing.
  _renderBudgetBar(
    stats.red_budget, stats.red_budget_max,
    'red-budget-current', 'red-budget-max', 'red-budget-bar-inner',
  );
}

function _renderBudgetBar(cur, max, curId, maxId, barId) {
  const curEl = document.getElementById(curId);
  const maxEl = document.getElementById(maxId);
  const barEl = document.getElementById(barId);
  if (!curEl || !maxEl || !barEl) return;
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
  red:  { title: 'RED WINS',  sub: 'Blue defence collapsed — all military sites destroyed.' },
  draw: { title: 'DRAW',      sub: 'Safety time cap reached.' },
};

const PHASE_LABEL = {
  setup:    'SETUP',
  running:  'RUNNING',
  paused:   'PAUSED',
  finished: 'FINISHED',
};

// Phase chip — small colour-coded indicator near the HUD title so the
// current Match Phase is visible at all times, independent of the
// centre-screen overlay. Data-phase attr drives CSS styling.
function renderPhaseChip(phase) {
  const el = document.getElementById('phase-chip');
  const labelEl = document.getElementById('phase-chip-label');
  if (!el || !labelEl) return;
  el.dataset.phase = phase;
  labelEl.textContent = PHASE_LABEL[phase] || String(phase).toUpperCase();
}

// M-TIER2.7 (W6 audit E): brief red-flash + tooltip on a WS `error`.
// Non-blocking, self-clearing; stacked errors reuse the single timer.
let _errorFlashTimer = null;
export function showWsError(reason) {
  const el = document.getElementById('phase-chip');
  if (!el) return;
  el.classList.add('error-flash');
  el.title = `WS error: ${reason}`;
  if (_errorFlashTimer !== null) clearTimeout(_errorFlashTimer);
  _errorFlashTimer = setTimeout(() => {
    el.classList.remove('error-flash');
    el.title = '';
    _errorFlashTimer = null;
  }, 3000);
}

// W16: Apply-layout status line in the SETUP ribbon. `ok=true` ack
// prints the slot + launcher count in green; `ok=false` (error frame)
// prints the detail in red. Self-clearing after 4 s so the ribbon
// doesn't accumulate stale status between presses.
let _layoutStatusTimer = null;
export function showLayoutStatus(text, ok) {
  const el = document.getElementById('layout-status');
  if (!el) return;
  el.textContent = text;
  el.style.color = ok ? '#8fe58f' : '#ff7a7a';
  if (_layoutStatusTimer !== null) clearTimeout(_layoutStatusTimer);
  _layoutStatusTimer = setTimeout(() => {
    el.textContent = '';
    el.style.color = '';
    _layoutStatusTimer = null;
  }, 4000);
}

// Bottom-bar Pause/Resume button (M-TIER2-J Part 1). Visible in RUNNING
// and PAUSED, hidden in SETUP and FINISHED. Text + data-mode flip so the
// same DOM element acts as Pause (RUNNING → sends 'pause') or Resume
// (PAUSED → sends 'resume'); wireHud's click handler reads dataset.mode.
// Replaces the centre-screen PAUSED overlay so the operator can click-
// inspect entities on a frozen battlefield.
function renderPauseResumeButton(phase) {
  const btn = document.getElementById('btn-pause');
  if (!btn) return;
  if (phase === 'running') {
    btn.classList.remove('hidden');
    btn.textContent = 'Pause';
    btn.dataset.mode = 'pause';
    return;
  }
  if (phase === 'paused') {
    btn.classList.remove('hidden');
    btn.textContent = 'Resume';
    btn.dataset.mode = 'resume';
    return;
  }
  // SETUP / FINISHED — no pause/resume affordance.
  btn.classList.add('hidden');
  btn.textContent = 'Pause';
  btn.dataset.mode = 'pause';
}

// Top SETUP ribbon — non-blocking, shown only during SETUP phase so the
// 3D canvas stays visible for launcher drag-drop (M-TIER2-J Part 1).
// Replaces the old centre-screen MATCH SETUP overlay.
function renderSetupRibbon(phase) {
  const el = document.getElementById('setup-ribbon');
  if (!el) return;
  el.classList.toggle('hidden', phase !== 'setup');
}

// Centre-screen match overlay — reused for FINISHED only (SETUP → ribbon
// now, PAUSED → no overlay, see Subtasks C+D). RUNNING hides the overlay
// entirely. Only Restart is surfaced in FINISHED.
function renderPhaseOverlay(phase, winner) {
  const el = document.getElementById('match-overlay');
  if (!el) return;
  const titleEl = document.getElementById('mo-title');
  const subEl = document.getElementById('mo-sub');
  const btnResume = document.getElementById('btn-resume');
  const btnRestart = document.getElementById('btn-restart');

  // Action buttons hidden by default; the phase branch re-shows the
  // single phase-appropriate one.
  btnResume?.classList.add('hidden');
  btnRestart?.classList.add('hidden');

  if (phase === 'running') {
    el.classList.add('hidden');
    return;
  }
  if (phase === 'setup') {
    // M-TIER2-J Part 1: SETUP uses the non-blocking top ribbon, not
    // the centre-screen overlay — the 3D canvas must stay visible for
    // launcher drag-drop (see renderSetupRibbon).
    el.classList.add('hidden');
    return;
  }
  if (phase === 'paused') {
    // M-TIER2-J Part 1: PAUSED no longer surfaces the centre-screen
    // overlay — operator needs the full canvas to click-inspect the
    // frozen battlefield. The bottom-bar Pause button flips to Resume
    // (see renderPauseResumeButton).
    el.classList.add('hidden');
    return;
  }
  if (phase === 'finished') {
    const text = OVERLAY_TEXT[winner] || { title: 'FINISHED', sub: '' };
    if (titleEl) {
      titleEl.textContent = text.title;
      titleEl.className = `mo-title mo-${winner || 'draw'}`;
    }
    if (subEl) subEl.textContent = text.sub;
    btnRestart?.classList.remove('hidden');
    el.classList.remove('hidden');
    return;
  }
  // Unknown phase — hide overlay so the HUD isn't locked.
  el.classList.add('hidden');
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
  // Ribbon re-shows on the next SETUP snapshot; hiding it here avoids a
  // stale-visible flash between Reset click and the first snapshot.
  document.getElementById('setup-ribbon')?.classList.add('hidden');
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
