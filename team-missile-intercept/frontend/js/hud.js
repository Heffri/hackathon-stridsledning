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
  // Blue AI model selector — sends set_blue_ai command on change.
  document.getElementById('blue-ai-select')?.addEventListener('change', (e) => {
    sendCmd({ cmd: 'set_blue_ai', slot: e.target.value });
  });
  // Red AI model selector — sends set_red_ai command on change.
  document.getElementById('red-ai-select')?.addEventListener('change', (e) => {
    sendCmd({ cmd: 'set_red_ai', slot: e.target.value });
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
  // Budget panel Apply button (SETUP-only). Server re-validates phase +
  // range; we just pack the two inputs into a set_budget command. Next
  // snapshot carries the updated Red/Blue budget totals to the HUD bars.
  document.getElementById('btn-apply-budget')?.addEventListener('click', () => {
    const redInput = document.getElementById('red-budget-input');
    const blueInput = document.getElementById('blue-budget-input');
    const redM = Number(redInput?.value);
    const blueM = Number(blueInput?.value);
    if (!Number.isFinite(redM) || !Number.isFinite(blueM)) return;
    sendCmd({
      cmd: 'set_budget',
      red_budget_usd: Math.round(redM * 1_000_000),
      blue_budget_usd: Math.round(blueM * 1_000_000),
    });
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
  // Delegated click handler on #match-overlay so the dashboard's
  // dynamically-injected #pms-restart button works after innerHTML
  // replacement wipes the original btn-restart listener.
  document.getElementById('match-overlay')?.addEventListener('click', (e) => {
    if (e.target.id === 'pms-restart') {
      sendCmd({ cmd: 'reset' });
      sendCmd({ cmd: 'start' });
      resetHudEventTracking();
    } else if (e.target.id === 'pms-close') {
      // Operator wants to inspect the post-match map (red impact bubbles,
      // destroyed sites, debris). Hide the dashboard but keep the match
      // in FINISHED so the battlefield stays frozen. The floating
      // "Show Summary" button in the bottom-right brings it back.
      _dashboardDismissed = true;
      document.getElementById('match-overlay')?.classList.add('hidden');
      const showBtn = _ensureShowSummaryBtn();
      showBtn.style.display = 'block';
    }
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

export function updateHud(snap) {
  setText('stat-t', snap.t.toFixed(1));
  setText('stat-wave', snap.wave ?? 0);
  setText('stat-waves', snap.total_waves ?? 0);
  setText('stat-active-t', snap.stats?.active_threats ?? 0);
  setText('stat-intercepts', snap.stats?.intercepts ?? 0);
  setText('stat-leaked', snap.stats?.leaked ?? 0);

  // Kill-feed: detect intercept count increase
  const intercepts = snap.stats?.intercepts ?? 0;
  if (intercepts > _lastIntercepts && _lastIntercepts > 0) {
    const delta = intercepts - _lastIntercepts;
    for (let i = 0; i < Math.min(delta, 3); i++) {
      pushKillFeed(`Threat intercepted (#${_lastIntercepts + i + 1})`);
    }
  }
  _lastIntercepts = intercepts;

  // Sim clock progress bar
  updateSimClock(snap.t, snap.max_sim_time);

  // Live battle dashboards — Blue defense + Red attack
  renderBlueDashboard(snap);
  renderRedDashboard(snap);

  // Per-site HP bars (Milestone I — replaces the old leak counters).
  renderSiteHp(snap.sites || []);

  // Blue budget bar (Milestone I).
  renderBudget(snap.stats || {});

  // Phase chip + phase-gated overlay (M-TIER2-PHASE).
  const phase = snap.phase || 'setup';
  renderPhaseChip(phase);
  renderSetupRibbon(phase);
  renderPhaseOverlay(phase, snap.winner || null, snap);
  renderPauseResumeButton(phase);
  // Drive CSS phase-gated panel visibility on #hud.
  const hudEl = document.getElementById('hud');
  if (hudEl) hudEl.dataset.phase = phase;

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

// ── Post-Match Summary Dashboard state ───────────────────────────────
let _dashboardRendered = false;
let _originalMoInnerHtml = null;
// Operator-dismissed flag: when true, renderPhaseOverlay keeps the
// FINISHED overlay hidden so the battle-scarred map (red impact bubbles,
// destroyed sites, debris) stays visible. A floating "Show Summary"
// button in the bottom-right re-opens the dashboard. Reset on
// resetHudEventTracking so the next match's FINISHED screen still
// auto-pops.
let _dashboardDismissed = false;

function _ensureShowSummaryBtn() {
  let btn = document.getElementById('btn-show-summary');
  if (btn) return btn;
  btn = document.createElement('button');
  btn.id = 'btn-show-summary';
  btn.textContent = 'Show Summary';
  // Inline styles so we don't need a style.css change for a one-purpose
  // re-open affordance.
  Object.assign(btn.style, {
    position: 'fixed',
    bottom: '64px',
    right: '16px',
    zIndex: '25',
    padding: '8px 14px',
    background: 'rgba(20, 30, 48, 0.85)',
    color: '#cfe2ff',
    border: '1px solid rgba(120, 160, 220, 0.5)',
    borderRadius: '6px',
    font: '12px/1.2 system-ui, sans-serif',
    cursor: 'pointer',
    display: 'none',
  });
  btn.addEventListener('click', () => {
    _dashboardDismissed = false;
    btn.style.display = 'none';
    const el = document.getElementById('match-overlay');
    if (el) el.classList.remove('hidden');
  });
  document.body.appendChild(btn);
  return btn;
}

// (Ammo fired tracking now uses backend total_fired field.)

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

// SETUP panel — centered floating card, visible only during SETUP phase.
// Toggle button lets the user hide the panel to see the map, then bring
// it back. 'M' keyboard shortcut toggles during SETUP.
let _setupPanelCollapsed = false;
function renderSetupRibbon(phase) {
  const el = document.getElementById('setup-ribbon');
  const btn = document.getElementById('btn-toggle-setup');
  if (!el) return;
  const isSetup = phase === 'setup';
  if (btn) btn.classList.toggle('hidden', !isSetup);
  if (!isSetup) {
    el.classList.add('hidden');
    _setupPanelCollapsed = false;
    return;
  }
  el.classList.toggle('hidden', _setupPanelCollapsed);
  if (btn) btn.textContent = _setupPanelCollapsed ? 'Show Setup (M)' : 'Hide Setup (M)';
}
export function toggleSetupPanel() {
  _setupPanelCollapsed = !_setupPanelCollapsed;
  const el = document.getElementById('setup-ribbon');
  const btn = document.getElementById('btn-toggle-setup');
  if (el) el.classList.toggle('hidden', _setupPanelCollapsed);
  if (btn) btn.textContent = _setupPanelCollapsed ? 'Show Setup (M)' : 'Hide Setup (M)';
}

// ── Post-Match Summary — metrics computation ─────────────────────────
function computeDashboardMetrics(snap) {
  const stats = snap.stats || {};
  const spawned = stats.spawned ?? 0;
  const intercepts = stats.intercepts ?? 0;
  const leaked = stats.leaked ?? 0;
  const activeThreats = stats.active_threats ?? 0;

  const interceptRate = spawned > 0 ? (intercepts / spawned) * 100 : 0;
  const leakRate = spawned > 0 ? (leaked / spawned) * 100 : 0;
  const activeRate = spawned > 0 ? (activeThreats / spawned) * 100 : 0;

  // Per-category breakdown: drones vs missiles (cruise + ballistic + HGV)
  const spByKind = stats.spawned_by_kind || {};
  const intByKind = stats.intercepts_by_kind || {};
  const leakByKind = stats.leaked_by_kind || {};
  const MISSILE_KINDS = ['cruise_sub', 'ballistic', 'hgv'];
  const droneSpawned = spByKind.drone ?? 0;
  const droneInt = intByKind.drone ?? 0;
  const droneLeak = leakByKind.drone ?? 0;
  const missileSpawned = MISSILE_KINDS.reduce((a, k) => a + (spByKind[k] ?? 0), 0);
  const missileInt = MISSILE_KINDS.reduce((a, k) => a + (intByKind[k] ?? 0), 0);
  const missileLeak = MISSILE_KINDS.reduce((a, k) => a + (leakByKind[k] ?? 0), 0);
  const droneRate = droneSpawned > 0 ? (droneInt / droneSpawned) * 100 : 0;
  const missileRate = missileSpawned > 0 ? (missileInt / missileSpawned) * 100 : 0;

  // Per-threat-kind detail breakdown
  const THREAT_KINDS = ['drone', 'cruise_sub', 'ballistic', 'hgv'];
  const threatBreakdown = THREAT_KINDS.map((k) => {
    const sp = spByKind[k] ?? 0;
    const int = intByKind[k] ?? 0;
    const lk = leakByKind[k] ?? 0;
    return {
      kind: k,
      spawned: sp,
      intercepted: int,
      leaked: lk,
      rate: sp > 0 ? (int / sp) * 100 : 0,
    };
  }).filter((t) => t.spawned > 0);

  const blueBudgetMax = stats.blue_budget_max ?? 0;
  const blueBudget = stats.blue_budget ?? 0;
  const redBudgetMax = stats.red_budget_max ?? 0;
  const redBudget = stats.red_budget ?? 0;
  const blueSpent = blueBudgetMax - blueBudget;
  const redSpent = redBudgetMax - redBudget;
  const costPerIntercept = intercepts > 0 ? blueSpent / intercepts : 0;
  const exchangeRatio = blueSpent > 0 ? redSpent / blueSpent : 0;

  const sites = snap.sites || [];
  const sitesIntact = sites.filter((s) => (s.hp ?? 0) > 0).length;
  const sitesDestroyed = sites.filter((s) => (s.hp ?? 0) <= 0).length;
  const totalHp = sites.reduce((a, s) => a + Math.max(0, s.hp ?? 0), 0);
  const totalHpMax = sites.reduce((a, s) => a + Math.max(1, s.hp_max ?? 100), 0);
  const totalSiteHpPct = totalHpMax > 0 ? (totalHp / totalHpMax) * 100 : 0;
  const totalLeaks = sites.reduce((a, s) => a + (s.leaks ?? 0), 0);

  const t = snap.t ?? 0;
  const matchMinutes = Math.floor(t / 60);
  const matchSeconds = Math.floor(t % 60);

  // Per-launcher detail list + per-kind aggregation
  const launchers = snap.launchers || [];
  const kindMap = {};
  for (const lch of launchers) {
    const k = lch.kind;
    if (!kindMap[k]) {
      kindMap[k] = { count: 0, totalCapacity: 0, totalCurrent: 0, totalBaseCost: 0, launchers: [] };
    }
    kindMap[k].count += 1;
    kindMap[k].totalCapacity += lch.capacity ?? 0;
    kindMap[k].totalCurrent += lch.current ?? 0;
    kindMap[k].totalBaseCost += lch.base_cost_usd ?? 0;
    kindMap[k].launchers.push(lch);
  }
  // ammo fired — use backend-tracked total_fired (reliable at any speed)
  let totalFired = 0;
  for (const v of Object.values(kindMap)) {
    v.totalFired = 0;
    for (const lch of v.launchers) {
      v.totalFired += lch.total_fired ?? 0;
    }
    totalFired += v.totalFired;
  }

  // AI model names
  const blueAiName = snap.blue_ai_name || 'Rule-Based AI';
  const redAiName = snap.red_ai_name || 'Rule-Based (5 Waves)';

  return {
    spawned, intercepts, leaked, activeThreats,
    interceptRate, leakRate, activeRate,
    droneSpawned, droneInt, droneLeak, droneRate,
    missileSpawned, missileInt, missileLeak, missileRate,
    threatBreakdown,
    blueBudget, blueBudgetMax, blueSpent,
    redBudget, redBudgetMax, redSpent,
    costPerIntercept, exchangeRatio,
    sites, sitesIntact, sitesDestroyed, totalSiteHpPct, totalLeaks,
    matchMinutes, matchSeconds,
    kindMap, launchers, totalFired,
    wave: snap.wave ?? 0,
    totalWaves: snap.total_waves ?? 0,
    blueAiName, redAiName,
  };
}

// ── Post-Match Summary — targeted DOM updates ─────────────────────────
// After the initial innerHTML build, subsequent ticks patch only the
// values that change (intercepts, ammo, budget, site HP) so the
// dashboard stays live without rebuilding the full DOM tree.
function updateDashboardValues(snap) {
  const m = computeDashboardMetrics(snap);
  const $ = (id) => document.getElementById(id);

  // Intercept performance ring + stats
  const ring = document.querySelector('.pms-ring');
  if (ring) {
    const interceptPct = m.interceptRate.toFixed(1);
    const leakEnd = (m.interceptRate + m.leakRate).toFixed(1);
    ring.style.setProperty('--pms-intercept-pct', interceptPct + '%');
    ring.style.setProperty('--pms-leak-end', leakEnd + '%');
  }
  _patchText('pms-ring-val', m.interceptRate.toFixed(0) + '%');
  _patchText('pms-intercept-count', `${m.intercepts}/${m.spawned}`);
  _patchText('pms-intercept-pct', m.interceptRate.toFixed(1) + '%');
  _patchText('pms-leak-count', `${m.leaked}/${m.spawned}`);
  _patchText('pms-leak-pct', m.leakRate.toFixed(1) + '%');
  _patchText('pms-inflight-count', `${m.activeThreats}/${m.spawned}`);
  _patchText('pms-inflight-pct', m.activeRate.toFixed(1) + '%');
  _patchText('pms-missile-count', `${m.missileInt}/${m.missileSpawned}`);
  _patchText('pms-missile-pct', m.missileRate.toFixed(1) + '%');
  _patchText('pms-drone-count', `${m.droneInt}/${m.droneSpawned}`);
  _patchText('pms-drone-pct', m.droneRate.toFixed(1) + '%');
  _patchText('pms-chip-threats', `Threats: ${m.spawned}`);

  // Budget bars
  const blueSpentPct = m.blueBudgetMax > 0 ? Math.min(100, (m.blueSpent / m.blueBudgetMax) * 100) : 0;
  const redSpentPct = m.redBudgetMax > 0 ? Math.min(100, (m.redSpent / m.redBudgetMax) * 100) : 0;
  const blueBar = $('pms-blue-budget-bar');
  if (blueBar) blueBar.style.width = blueSpentPct + '%';
  _patchText('pms-blue-budget-vals', `${formatMoney(m.blueSpent)} / ${formatMoney(m.blueBudgetMax)}`);
  const redBar = $('pms-red-budget-bar');
  if (redBar) redBar.style.width = redSpentPct + '%';
  _patchText('pms-red-budget-vals', `${formatMoney(m.redSpent)} / ${formatMoney(m.redBudgetMax)}`);

  // Site HP bars
  for (const s of m.sites) {
    const hp = Math.max(0, s.hp ?? 0);
    const hpMax = Math.max(1, s.hp_max ?? 100);
    const pct = Math.min(100, (hp / hpMax) * 100);
    const dead = hp <= 0;
    const barEl = $(`pms-site-bar-${s.name}`);
    if (barEl) {
      barEl.style.width = pct + '%';
      barEl.className = 'pms-site-bar-inner' + (dead ? ' dead' : '');
    }
    const pctEl = $(`pms-site-pct-${s.name}`);
    if (pctEl) {
      pctEl.textContent = dead ? 'DEAD' : pct.toFixed(0) + '%';
      pctEl.className = 'pms-site-pct' + (dead ? ' pms-site-dead' : '');
    }
  }

  // Per-launcher ammo bars + status + fired count
  for (const lch of m.launchers) {
    const cap = lch.capacity ?? 0;
    const cur = lch.current ?? 0;
    const fired = lch.total_fired ?? 0;
    const ammoPct = cap > 0 ? Math.min(100, (cur / cap) * 100) : 0;
    const ammoBar = $(`pms-lch-bar-${lch.id}`);
    if (ammoBar) ammoBar.style.width = ammoPct + '%';
    _patchText(`pms-lch-ammo-${lch.id}`, `${cur}/${cap}`);
    _patchText(`pms-lch-fired-${lch.id}`, String(fired));
    const statusEl = $(`pms-lch-status-${lch.id}`);
    if (statusEl) {
      let label, cls;
      if (lch.reloading) {
        label = `RLD ${(lch.reload_remaining ?? 0).toFixed(0)}s`;
        cls = 'pms-lch-status reloading';
      } else if ((lch.cooldown_remaining ?? 0) > 0.05) {
        label = `CD ${lch.cooldown_remaining.toFixed(1)}s`;
        cls = 'pms-lch-status cooldown';
      } else {
        label = 'RDY';
        cls = 'pms-lch-status ready';
      }
      statusEl.textContent = label;
      statusEl.className = cls;
    }
  }

  // KPI cards
  _patchText('pms-kpi-defense', m.missileRate.toFixed(1) + '%');
  _patchText('pms-kpi-cost', m.costPerIntercept > 0 ? formatMoney(m.costPerIntercept) : '—');
  _patchText('pms-kpi-sites', `${m.sitesIntact}/${m.sites.length}`);
  _patchText('pms-kpi-exchange', m.exchangeRatio > 0 ? m.exchangeRatio.toFixed(1) + ':1' : '—');
}

function _patchText(id, text) {
  const el = document.getElementById(id);
  if (el && el.textContent !== text) el.textContent = text;
}

// ── Post-Match Summary — HTML builder ─────────────────────────────────
function buildDashboardHtml(snap, m) {
  const winner = snap.winner || 'draw';
  const text = OVERLAY_TEXT[winner] || { title: 'FINISHED', sub: '' };

  // Donut percentages (conic-gradient stops)
  const interceptPct = m.interceptRate.toFixed(1);
  const leakEnd = (m.interceptRate + m.leakRate).toFixed(1);

  // Site rows
  const siteRows = m.sites.map((s) => {
    const color = SITE_SUBTYPE_COLORS[s.subtype] || '#888';
    const hp = Math.max(0, s.hp ?? 0);
    const hpMax = Math.max(1, s.hp_max ?? 100);
    const pct = Math.min(100, (hp / hpMax) * 100);
    const dead = hp <= 0;
    const leaks = s.leaks ?? 0;
    return (
      `<div class="pms-site-row">` +
        `<span class="pms-site-dot" style="background:${color};color:${color}"></span>` +
        `<span class="pms-site-name">${escapeHtml(s.name)}</span>` +
        `<div class="pms-site-bar-outer">` +
          `<div class="pms-site-bar-inner${dead ? ' dead' : ''}" id="pms-site-bar-${s.name}" style="width:${pct}%"></div>` +
        `</div>` +
        `<span class="pms-site-pct${dead ? ' pms-site-dead' : ''}" id="pms-site-pct-${s.name}">${dead ? 'DESTROYED' : pct.toFixed(0) + '%'}</span>` +
        (leaks > 0 ? `<span class="pms-site-leaks">${leaks} hit${leaks > 1 ? 's' : ''}</span>` : '') +
      `</div>`
    );
  }).join('');

  // Budget bars
  const blueSpentPct = m.blueBudgetMax > 0 ? Math.min(100, (m.blueSpent / m.blueBudgetMax) * 100) : 0;
  const redSpentPct = m.redBudgetMax > 0 ? Math.min(100, (m.redSpent / m.redBudgetMax) * 100) : 0;
  const blueRemaining = m.blueBudgetMax - m.blueSpent;
  const redRemaining = m.redBudgetMax - m.redSpent;

  // Per-threat-kind intercept breakdown rows
  const threatRows = m.threatBreakdown.map((t) => {
    const color = THREAT_COLORS[t.kind] || '#888';
    const label = THREAT_LABELS[t.kind] || t.kind;
    const barPct = t.rate.toFixed(1);
    return (
      `<div class="pms-threat-row">` +
        `<span class="pms-threat-dot" style="background:${color}"></span>` +
        `<span class="pms-threat-label">${label}</span>` +
        `<span class="pms-threat-counts">${t.intercepted}/${t.spawned}</span>` +
        `<div class="pms-threat-bar-outer">` +
          `<div class="pms-threat-bar-inner" style="width:${barPct}%;background:${color}"></div>` +
        `</div>` +
        `<span class="pms-threat-pct">${t.rate.toFixed(0)}%</span>` +
      `</div>`
    );
  }).join('');

  // Per-weapon-system summary rows (aggregated, not per-launcher)
  const kindKeys = Object.keys(m.kindMap).sort();
  const weaponRows = kindKeys.map((k) => {
    const v = m.kindMap[k];
    const color = WEAPON_COLORS[k] || '#888';
    const name = INTERCEPTOR_NAMES[k] || k;
    const ammoUsedPct = v.totalCapacity > 0
      ? Math.min(100, (v.totalFired / v.totalCapacity) * 100) : 0;
    return (
      `<div class="pms-weapon-row">` +
        `<span class="pms-weapon-dot" style="background:${color}"></span>` +
        `<span class="pms-weapon-name">${name}</span>` +
        `<span class="pms-weapon-count">${v.count}x</span>` +
        `<span class="pms-weapon-fired">${v.totalFired} fired</span>` +
        `<div class="pms-weapon-bar-outer">` +
          `<div class="pms-weapon-bar-inner" style="width:${ammoUsedPct}%;background:${color}"></div>` +
        `</div>` +
        `<span class="pms-weapon-cost">${formatMoney(v.totalBaseCost)}</span>` +
      `</div>`
    );
  }).join('');

  // Detailed per-launcher roster table
  const rosterRows = kindKeys.map((k) => {
    const v = m.kindMap[k];
    const color = WEAPON_COLORS[k] || '#888';
    const name = INTERCEPTOR_NAMES[k] || k;
    let html = `<tr class="pms-roster-kind-header">` +
      `<td colspan="6"><span class="pms-roster-dot" style="background:${color}"></span>${escapeHtml(name)} (${v.count}) — ${v.totalFired} fired</td>` +
      `</tr>`;
    for (const lch of v.launchers) {
      const cap = lch.capacity ?? 0;
      const cur = lch.current ?? 0;
      const fired = lch.total_fired ?? 0;
      const ammoPct = cap > 0 ? Math.min(100, (cur / cap) * 100) : 0;
      let statusLabel, statusCls;
      if (lch.reloading) {
        statusLabel = `RLD ${(lch.reload_remaining ?? 0).toFixed(0)}s`;
        statusCls = 'pms-lch-status reloading';
      } else if ((lch.cooldown_remaining ?? 0) > 0.05) {
        statusLabel = `CD ${lch.cooldown_remaining.toFixed(1)}s`;
        statusCls = 'pms-lch-status cooldown';
      } else {
        statusLabel = 'RDY';
        statusCls = 'pms-lch-status ready';
      }
      html +=
        `<tr>` +
          `<td class="pms-roster-id">${escapeHtml(lch.id.slice(-4))}</td>` +
          `<td class="pms-lch-fired" id="pms-lch-fired-${lch.id}">${fired}</td>` +
          `<td id="pms-lch-ammo-${lch.id}">${cur}/${cap}</td>` +
          `<td class="pms-roster-bar-cell">` +
            `<div class="pms-roster-bar-outer">` +
              `<div class="pms-roster-bar-inner" id="pms-lch-bar-${lch.id}" style="width:${ammoPct}%"></div>` +
            `</div>` +
          `</td>` +
          `<td><span class="${statusCls}" id="pms-lch-status-${lch.id}">${statusLabel}</span></td>` +
          `<td>${formatMoney(lch.base_cost_usd ?? 0)}</td>` +
        `</tr>`;
    }
    return html;
  }).join('');

  // Build narrative summary — 3-4 sentences a presenter can read aloud
  const summaryLines = [];
  // Line 1: headline result
  if (winner === 'blue') {
    summaryLines.push(`Blue's <strong>${escapeHtml(m.blueAiName)}</strong> successfully defended against Red's <strong>${escapeHtml(m.redAiName)}</strong> in ${m.matchMinutes}m ${String(m.matchSeconds).padStart(2, '0')}s.`);
  } else if (winner === 'red') {
    summaryLines.push(`Red's <strong>${escapeHtml(m.redAiName)}</strong> overwhelmed Blue's <strong>${escapeHtml(m.blueAiName)}</strong> defense in ${m.matchMinutes}m ${String(m.matchSeconds).padStart(2, '0')}s.`);
  } else {
    summaryLines.push(`The match between <strong>${escapeHtml(m.blueAiName)}</strong> and <strong>${escapeHtml(m.redAiName)}</strong> ended in a draw after ${m.matchMinutes}m ${String(m.matchSeconds).padStart(2, '0')}s.`);
  }
  // Line 2: missile intercept performance
  summaryLines.push(`The defense intercepted <strong>${m.missileRate.toFixed(0)}%</strong> of missiles (${m.missileInt}/${m.missileSpawned}) and <strong>${m.droneRate.toFixed(0)}%</strong> of drones (${m.droneInt}/${m.droneSpawned}).`);
  // Line 3: site survival
  summaryLines.push(`<strong>${m.sitesIntact}</strong> of ${m.sites.length} sites survived with <strong>${m.totalSiteHpPct.toFixed(0)}%</strong> total HP remaining.`);
  // Line 4: cost efficiency
  const costLine = m.costPerIntercept > 0
    ? `Blue spent ${formatMoney(m.blueSpent)} (${formatMoney(m.costPerIntercept)}/intercept) against Red's ${formatMoney(m.redSpent)}.`
    : `Blue spent ${formatMoney(m.blueSpent)} against Red's ${formatMoney(m.redSpent)}.`;
  summaryLines.push(costLine);

  return (
    `<div class="pms-dashboard">` +

    // ── Header ──
    `<div class="pms-header">` +
      `<div class="pms-title mo-${winner}">${escapeHtml(text.title)}</div>` +
      `<div class="pms-subtitle">${escapeHtml(text.sub)}</div>` +
    `</div>` +

    // ── Narrative Summary ──
    `<div class="pms-summary">` +
      summaryLines.map(l => `<div class="pms-summary-line">${l}</div>`).join('') +
    `</div>` +

    // ── Match Config Banner ──
    `<div class="pms-config-banner">` +
      `<span class="pms-config-item"><span class="pms-config-key">Duration</span><span class="pms-config-val">${m.matchMinutes}m ${String(m.matchSeconds).padStart(2, '0')}s</span></span>` +
      `<span class="pms-config-sep"></span>` +
      `<span class="pms-config-item"><span class="pms-config-key">Waves</span><span class="pms-config-val">${m.wave}/${m.totalWaves}</span></span>` +
      `<span class="pms-config-sep"></span>` +
      `<span class="pms-config-item"><span class="pms-config-key">Blue AI</span><span class="pms-config-val pms-config-blue">${escapeHtml(m.blueAiName)}</span></span>` +
      `<span class="pms-config-sep"></span>` +
      `<span class="pms-config-item"><span class="pms-config-key">Red AI</span><span class="pms-config-val pms-config-red">${escapeHtml(m.redAiName)}</span></span>` +
      `<span class="pms-config-sep"></span>` +
      `<span class="pms-config-item"><span class="pms-config-key">Launchers</span><span class="pms-config-val">${m.launchers.length}</span></span>` +
      `<span class="pms-config-sep"></span>` +
      `<span class="pms-config-item" id="pms-chip-threats"><span class="pms-config-key">Threats</span><span class="pms-config-val">${m.spawned}</span></span>` +
    `</div>` +

    // ── KPI Cards (top-level, full width) ──
    `<div class="pms-kpi-strip">` +
      `<div class="pms-kpi-card">` +
        `<div class="pms-kpi-val pms-kpi-big" id="pms-kpi-defense">${m.missileRate.toFixed(1)}%</div>` +
        `<div class="pms-kpi-label">Missile Defense Rate</div>` +
      `</div>` +
      `<div class="pms-kpi-card">` +
        `<div class="pms-kpi-val" id="pms-kpi-sites">${m.sitesIntact}/${m.sites.length}</div>` +
        `<div class="pms-kpi-label">Sites Intact</div>` +
      `</div>` +
      `<div class="pms-kpi-card">` +
        `<div class="pms-kpi-val">${m.totalSiteHpPct.toFixed(0)}%</div>` +
        `<div class="pms-kpi-label">Total Site HP</div>` +
      `</div>` +
      `<div class="pms-kpi-card">` +
        `<div class="pms-kpi-val" id="pms-kpi-cost">${m.costPerIntercept > 0 ? formatMoney(m.costPerIntercept) : '—'}</div>` +
        `<div class="pms-kpi-label">Cost / Intercept</div>` +
      `</div>` +
      `<div class="pms-kpi-card">` +
        `<div class="pms-kpi-val" id="pms-kpi-exchange">${m.exchangeRatio > 0 ? m.exchangeRatio.toFixed(1) + ':1' : '—'}</div>` +
        `<div class="pms-kpi-label">Exchange Ratio</div>` +
      `</div>` +
      `<div class="pms-kpi-card">` +
        `<div class="pms-kpi-val">${m.totalFired}</div>` +
        `<div class="pms-kpi-label">Interceptors Fired</div>` +
      `</div>` +
    `</div>` +

    `<div class="pms-body">` +

    // ── 1. Intercept Performance (full width) ──
    `<div class="pms-section pms-full">` +
      `<div class="pms-section-title">Intercept Performance</div>` +
      `<div class="pms-intercept-row">` +
        `<div class="pms-ring-wrap">` +
          `<div class="pms-ring" style="--pms-intercept-pct:${interceptPct}%;--pms-leak-end:${leakEnd}%">` +
            `<div class="pms-ring-inner">` +
              `<span class="pms-ring-val" id="pms-ring-val">${m.interceptRate.toFixed(0)}%</span>` +
              `<span class="pms-ring-label">OVERALL</span>` +
            `</div>` +
          `</div>` +
        `</div>` +
        `<div class="pms-stat-rows">` +
          `<div class="pms-stat-row">` +
            `<span class="pms-stat-label">Intercepted</span>` +
            `<span><span class="pms-stat-val" id="pms-intercept-count">${m.intercepts}/${m.spawned}</span>` +
            `<span class="pms-stat-pct" id="pms-intercept-pct">${m.interceptRate.toFixed(1)}%</span></span>` +
          `</div>` +
          `<div class="pms-stat-row">` +
            `<span class="pms-stat-label">Leaked</span>` +
            `<span><span class="pms-stat-val" id="pms-leak-count">${m.leaked}/${m.spawned}</span>` +
            `<span class="pms-stat-pct" id="pms-leak-pct">${m.leakRate.toFixed(1)}%</span></span>` +
          `</div>` +
          `<div class="pms-stat-row">` +
            `<span class="pms-stat-label">In-flight</span>` +
            `<span><span class="pms-stat-val" id="pms-inflight-count">${m.activeThreats}/${m.spawned}</span>` +
            `<span class="pms-stat-pct" id="pms-inflight-pct">${m.activeRate.toFixed(1)}%</span></span>` +
          `</div>` +
        `</div>` +
      `</div>` +
    `</div>` +

    // ── 2. Per-Threat-Type Breakdown (left) ──
    `<div class="pms-section">` +
      `<div class="pms-section-title">Threat Breakdown</div>` +
      threatRows +
      `<div class="pms-threat-summary">` +
        `<span style="color:#ff6a3a">Missiles: ${m.missileInt}/${m.missileSpawned} (${m.missileRate.toFixed(0)}%)</span>` +
        `<span style="color:#8cf;margin-left:12px">Drones: ${m.droneInt}/${m.droneSpawned} (${m.droneRate.toFixed(0)}%)</span>` +
      `</div>` +
    `</div>` +

    // ── 3. Site Damage Report (right) ──
    `<div class="pms-section">` +
      `<div class="pms-section-title">Site Damage Report</div>` +
      `<div class="pms-site-summary">` +
        `<span>${m.sitesIntact} intact</span>` +
        (m.sitesDestroyed > 0 ? `<span class="pms-site-dead"> · ${m.sitesDestroyed} destroyed</span>` : '') +
        `<span> · ${m.totalLeaks} total impacts</span>` +
      `</div>` +
      siteRows +
    `</div>` +

    // ── 4. Weapon Systems (left) ──
    `<div class="pms-section">` +
      `<div class="pms-section-title">Weapon Systems</div>` +
      weaponRows +
    `</div>` +

    // ── 5. Budget Analysis (right) ──
    `<div class="pms-section">` +
      `<div class="pms-section-title">Budget Analysis</div>` +
      `<div class="pms-budget-row">` +
        `<span class="pms-budget-label blue">BLUE</span>` +
        `<div class="pms-budget-bar-outer">` +
          `<div class="pms-budget-bar-inner blue" id="pms-blue-budget-bar" style="width:${blueSpentPct}%"></div>` +
        `</div>` +
        `<span class="pms-budget-vals" id="pms-blue-budget-vals">${formatMoney(m.blueSpent)} / ${formatMoney(m.blueBudgetMax)}</span>` +
      `</div>` +
      `<div class="pms-budget-detail">Spent: ${formatMoney(m.blueSpent)} · Remaining: ${formatMoney(blueRemaining)}</div>` +
      `<div class="pms-budget-row" style="margin-top:8px">` +
        `<span class="pms-budget-label red">RED</span>` +
        `<div class="pms-budget-bar-outer">` +
          `<div class="pms-budget-bar-inner red" id="pms-red-budget-bar" style="width:${redSpentPct}%"></div>` +
        `</div>` +
        `<span class="pms-budget-vals" id="pms-red-budget-vals">${formatMoney(m.redSpent)} / ${formatMoney(m.redBudgetMax)}</span>` +
      `</div>` +
      `<div class="pms-budget-detail">Spent: ${formatMoney(m.redSpent)} · Remaining: ${formatMoney(redRemaining)}</div>` +
    `</div>` +

    // ── 6. Detailed Launcher Roster (full width) ──
    `<div class="pms-section pms-full">` +
      `<div class="pms-section-title">Detailed Launcher Roster</div>` +
      `<table class="pms-roster-table">` +
        `<tr><th>ID</th><th>Fired</th><th>Mag</th><th>Level</th><th>Status</th><th>Cost</th></tr>` +
        rosterRows +
      `</table>` +
    `</div>` +

    `</div>` + // end .pms-body

    // Footer
    `<div class="pms-footer">` +
      `<button id="pms-close" class="pms-restart" style="background:rgba(80,90,110,0.8);margin-right:8px">Close (view battlefield)</button>` +
      `<button id="pms-restart" class="pms-restart">Restart</button>` +
    `</div>` +

    `</div>` // end .pms-dashboard
  );
}

// Centre-screen match overlay — reused for FINISHED only (SETUP → ribbon
// now, PAUSED → no overlay, see Subtasks C+D). RUNNING hides the overlay
// entirely. Only Restart is surfaced in FINISHED.
function renderPhaseOverlay(phase, winner, snap) {
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
    if (_dashboardDismissed) {
      // Operator clicked Close — keep overlay hidden so the battle-
      // scarred map is visible. Still patch live values silently in
      // case the dashboard is re-opened mid-frame via Show Summary.
      el.classList.add('hidden');
      if (_dashboardRendered && snap) updateDashboardValues(snap);
      return;
    }
    if (_dashboardRendered) {
      // Dashboard already built — patch only the live values so ammo,
      // intercepts, and site HP stay current without a full rebuild.
      if (snap) updateDashboardValues(snap);
      el.classList.remove('hidden');
      return;
    }
    // Save original .mo-inner content for restoration on reset
    const moInner = el.querySelector('.mo-inner');
    if (moInner && _originalMoInnerHtml === null) {
      _originalMoInnerHtml = moInner.innerHTML;
    }
    // Compute metrics + render dashboard into .mo-inner
    if (moInner && snap) {
      const metrics = computeDashboardMetrics(snap);
      moInner.innerHTML = buildDashboardHtml(snap, metrics);
      // Override .mo-inner padding for the dashboard
      moInner.style.padding = '0';
    }
    el.classList.remove('hidden');
    _dashboardRendered = true;
    return;
  }
  // Unknown phase — hide overlay so the HUD isn't locked.
  el.classList.add('hidden');
}

// Called by main.js on websocket reset so Reset button clears banner
// state and re-triggers for next game.
export function resetHudEventTracking() {
  document.getElementById('match-overlay')?.classList.add('hidden');
  // Restore original .mo-inner content after dashboard replacement
  if (_originalMoInnerHtml !== null) {
    const moInner = document.querySelector('.mo-inner');
    if (moInner) {
      moInner.innerHTML = _originalMoInnerHtml;
      moInner.style.padding = '';
    }
    _originalMoInnerHtml = null;
  }
  _dashboardRendered = false;
  // Clear operator-dismissed flag + hide the floating Show Summary
  // button so the next match's FINISHED screen still auto-pops.
  _dashboardDismissed = false;
  const showBtn = document.getElementById('btn-show-summary');
  if (showBtn) showBtn.style.display = 'none';
  // Ribbon re-shows on the next SETUP snapshot; hiding it here avoids a
  // stale-visible flash between Reset click and the first snapshot.
  document.getElementById('setup-ribbon')?.classList.add('hidden');
  // Reset accumulated state for next game
  _lastIntercepts = 0;
  // Clear kill-feed
  const kf = document.getElementById('kill-feed');
  if (kf) kf.innerHTML = '';
  _killFeedQueue.length = 0;
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

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

// ── Live Battle Dashboards ───────────────────────────────────────────
// Replace the old text logs with at-a-glance visual summaries.

const THREAT_LABELS = { drone: 'Drone', cruise_sub: 'Cruise', ballistic: 'Ballistic', hgv: 'HGV' };
const THREAT_COLORS = { drone: '#8cf', cruise_sub: '#f9a825', ballistic: '#ff5252', hgv: '#e040fb' };
const INTERCEPTOR_LABELS = {
  ciws: 'CIWS', rbs_70: 'RBS-70', iris_t_sls: 'IRIS-T SLS',
  iris_t_slm: 'IRIS-T SLM', pac_2: 'PAC-2', pac_3: 'PAC-3',
};

function renderBlueDashboard(snap) {
  const el = document.getElementById('blue-dashboard');
  if (!el) return;
  const stats = snap.stats || {};
  const intercepts = stats.intercepts ?? 0;
  const leaked = stats.leaked ?? 0;

  const MISSILE_KINDS = ['cruise_sub', 'ballistic', 'hgv'];
  const intByKind = stats.intercepts_by_kind || {};
  const leakByKind = stats.leaked_by_kind || {};
  const mInt = MISSILE_KINDS.reduce((a, k) => a + (intByKind[k] ?? 0), 0);
  const mLeak = MISSILE_KINDS.reduce((a, k) => a + (leakByKind[k] ?? 0), 0);
  const mTotal = mInt + mLeak;
  const mRate = mTotal > 0 ? Math.round((mInt / mTotal) * 100) : 0;
  const dInt = intByKind.drone ?? 0;
  const dLeak = leakByKind.drone ?? 0;
  const dTotal = dInt + dLeak;
  const dRate = dTotal > 0 ? Math.round((dInt / dTotal) * 100) : 0;

  const launchers = snap.launchers || [];
  const ready = launchers.filter(l => (l.current ?? 0) > 0).length;
  const aiName = snap.blue_ai_name || 'Rule-Based AI';

  el.innerHTML =
    `<div class="dash-row"><span class="dash-label">Model</span>` +
    `<span class="dash-value dash-ai-tag">${aiName}</span></div>` +
    `<div class="dash-sep"></div>` +
    `<div class="dash-row"><span class="dash-label">Missile intercept</span>` +
    `<span class="dash-value dash-highlight">${mRate}%</span></div>` +
    `<div class="dash-bar-outer"><div class="dash-bar-fill dash-bar-blue" style="width:${mRate}%"></div></div>` +
    `<div class="dash-row"><span class="dash-label">Drone intercept</span>` +
    `<span class="dash-value">${dRate}%</span></div>` +
    `<div class="dash-bar-outer"><div class="dash-bar-fill dash-bar-blue" style="width:${dRate}%;opacity:0.5"></div></div>` +
    `<div class="dash-row"><span class="dash-label">Kills / Leaked</span>` +
    `<span class="dash-value">${intercepts} / ${leaked}</span></div>` +
    `<div class="dash-row"><span class="dash-label">Launchers ready</span>` +
    `<span class="dash-value">${ready} / ${launchers.length}</span></div>`;
}

function renderRedDashboard(snap) {
  const el = document.getElementById('red-dashboard-left');
  if (!el) return;
  const stats = snap.stats || {};
  const ents = snap.entities || [];

  const threatByKind = {};
  let totalActive = 0;
  for (const e of ents) {
    if (e.team === 'red' && e.alive) {
      threatByKind[e.kind] = (threatByKind[e.kind] || 0) + 1;
      totalActive++;
    }
  }
  const spawned = stats.spawned ?? 0;
  const wave = snap.wave ?? 0;
  const totalWaves = snap.total_waves ?? 0;
  const redAi = snap.red_ai_name || 'Rule-Based';

  let html =
    `<div class="dash-row"><span class="dash-label">Model</span>` +
    `<span class="dash-value dash-ai-tag">${redAi}</span></div>` +
    `<div class="dash-sep"></div>` +
    `<div class="dash-row"><span class="dash-label">Active threats</span>` +
    `<span class="dash-value dash-highlight-red">${totalActive}</span></div>` +
    `<div class="dash-row"><span class="dash-label">Spawned</span>` +
    `<span class="dash-value">${spawned} · Wave ${wave}/${totalWaves}</span></div>`;

  const threatKinds = ['drone', 'cruise_sub', 'ballistic', 'hgv'];
  for (const k of threatKinds) {
    const n = threatByKind[k] || 0;
    if (n > 0) {
      const label = THREAT_LABELS[k];
      const color = THREAT_COLORS[k];
      html += `<div class="dash-row"><span class="dash-dot" style="background:${color}"></span>` +
        `<span class="dash-label">${label}</span>` +
        `<span class="dash-value">${n} active</span></div>`;
    }
  }

  el.innerHTML = html;
}

// ── Kill-Feed Overlay ────────────────────────────────────────────────
// Shows recent intercept events as stacked cards at the top center.
let _lastIntercepts = 0;
const _killFeedQueue = [];
const MAX_KILL_FEED = 4;

function pushKillFeed(text) {
  const el = document.getElementById('kill-feed');
  if (!el) return;
  const card = document.createElement('div');
  card.className = 'kill-feed-entry';
  card.textContent = text;
  el.prepend(card);
  _killFeedQueue.push(card);
  // Trim to max
  while (_killFeedQueue.length > MAX_KILL_FEED) {
    const old = _killFeedQueue.shift();
    old.remove();
  }
  // Auto-remove after 3s
  setTimeout(() => {
    card.classList.add('kill-feed-fade');
    setTimeout(() => {
      card.remove();
      const idx = _killFeedQueue.indexOf(card);
      if (idx >= 0) _killFeedQueue.splice(idx, 1);
    }, 500);
  }, 3000);
}

// ── Sim Clock Progress Bar ───────────────────────────────────────────
function updateSimClock(t, maxSimTime) {
  const fill = document.getElementById('sim-clock-fill');
  if (!fill) return;
  if (!maxSimTime || maxSimTime <= 0) {
    fill.style.width = '0%';
    return;
  }
  const pct = Math.min(100, Math.max(0, (t / maxSimTime) * 100));
  fill.style.width = `${pct}%`;
}
