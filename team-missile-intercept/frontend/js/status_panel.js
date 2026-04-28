// Click-to-inspect per-entity status panel.
//
// Attaches a Raycaster to the canvas. When the user clicks an entity mesh,
// identify it via mesh.userData.entityId (set by EntityRegistry) and render
// a glass-morphism panel in the bottom-right showing realtime stats:
// kind name, team, speed + Mach, G-load (client-side dv/dt), HP bar, thrust
// status, fuel remaining, altitude, target, range to target, unit cost.
import * as THREE from 'three';

const INTERCEPTOR_NAMES = {
  ciws: 'Lvkv 90',
  rbs_70: 'RBS 70 NG',
  iris_t_sls: 'IRIS-T SLS (RBS 98)',
  iris_t_slm: 'IRIS-T SLM',
  pac_2: 'Patriot PAC-2 GEM+',
  pac_3: 'Patriot PAC-3 MSE',
};

const THREAT_NAMES = {
  drone: 'Shahed-class drone',
  cruise_sub: 'Kalibr-class cruise missile',
  ballistic: 'Iskander-class RV',
  hgv: 'Kinzhal/DF-ZF HGV',
};

// Verbatim fuel_s table copied from backend/sim/types.py InterceptorSpec.
const FUEL_S = {
  ciws: 4,
  rbs_70: 13,
  iris_t_sls: 30,
  iris_t_slm: 39,
  pac_2: 41,
  pac_3: 35,
};

// Verbatim unit USD cost table from WEAPON_SPECS.md / types.py.
const USD_COST = {
  ciws: 2000,
  rbs_70: 175000,
  iris_t_sls: 500000,
  iris_t_slm: 1000000,
  pac_2: 3000000,
  pac_3: 4000000,
};

const THREAT_USD = {
  drone: 30_000,
  cruise_sub: 1_500_000,
  ballistic: 3_000_000,
  hgv: 10_000_000,
};

const MACH_1 = 343; // m/s at sea level

let selectedId = null;
// Last seen velocity vector per id, used for client-side G-load estimation.
// Stored as [vx, vy, vz, t, gLoad] where t is snap.t at sample time and
// gLoad is the last computed value (reused on render frames where snap.t
// has not advanced — otherwise the stable `latestSnap` being re-read at
// 60 fps would overwrite prev with identical values and pin G-load to 0).
const prevVel = new Map();
// When the selected entity dies, show DESTROYED briefly before auto-closing.
let destroyedAt = null;
const DESTROYED_LINGER_S = 1.0;

export function initStatusPanel(canvas, camera, registry) {
  const raycaster = new THREE.Raycaster();
  const mouse = new THREE.Vector2();

  canvas.addEventListener('click', (ev) => {
    // Normalized device coordinates for the raycaster.
    const rect = canvas.getBoundingClientRect();
    mouse.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(mouse, camera);

    // Gather all EntityMesh group roots so we can raycast them. Each
    // EntityMesh's mesh Group has userData.entityId set at construction.
    const candidates = [];
    for (const em of registry.byId.values()) {
      if (em.mesh) candidates.push(em.mesh);
    }
    // Recursive=true because meshes are Groups of child Meshes.
    const hits = raycaster.intersectObjects(candidates, true);
    if (hits.length === 0) {
      clearSelection();
      return;
    }
    // Walk up parent chain on the nearest hit until we find entityId.
    let o = hits[0].object;
    while (o && o.userData.entityId === undefined) {
      o = o.parent;
    }
    if (o && o.userData.entityId !== undefined) {
      selectedId = o.userData.entityId;
      destroyedAt = null;
      show();
    } else {
      clearSelection();
    }
  });

  const closeBtn = document.getElementById('status-panel-close');
  if (closeBtn) closeBtn.addEventListener('click', clearSelection);
}

function clearSelection() {
  selectedId = null;
  destroyedAt = null;
  const panel = document.getElementById('status-panel');
  if (panel) panel.classList.add('hidden');
}

function show() {
  const panel = document.getElementById('status-panel');
  if (panel) panel.classList.remove('hidden');
}

export function updateStatusPanel(snap) {
  if (selectedId === null) return;
  const panel = document.getElementById('status-panel');
  if (!panel) return;

  const entities = snap.entities || [];
  const ent = entities.find((e) => e.id === selectedId);
  if (!ent || !ent.alive) {
    // Linger on DESTROYED for ~1 s after death so the operator sees the fate.
    if (destroyedAt === null) destroyedAt = performance.now() / 1000;
    renderDestroyed();
    if (performance.now() / 1000 - destroyedAt > DESTROYED_LINGER_S) {
      clearSelection();
    }
    return;
  }

  // Maintain per-id previous velocity for G-load estimate. Only resample
  // when snap.t actually advanced: the render loop calls this at 60 fps
  // while the WebSocket stream is 15 Hz, so most invocations see an
  // unchanged snapshot. Resampling on every call would overwrite prev
  // with identical velocities and pin the computed G-load to 0.
  const vx = ent.vel[0], vy = ent.vel[1], vz = ent.vel[2];
  const t = snap.t ?? 0;
  const prev = prevVel.get(ent.id);
  let gLoad = 0;
  if (!prev) {
    prevVel.set(ent.id, [vx, vy, vz, t, 0]);
  } else if (t > prev[3] + 1e-4) {
    const dt = t - prev[3];
    const dvx = vx - prev[0], dvy = vy - prev[1], dvz = vz - prev[2];
    const dvMag = Math.sqrt(dvx * dvx + dvy * dvy + dvz * dvz);
    gLoad = dvMag / dt / 9.81;
    prevVel.set(ent.id, [vx, vy, vz, t, gLoad]);
  } else {
    gLoad = prev[4] ?? 0;
  }

  const speed = Math.sqrt(vx * vx + vy * vy + vz * vz);
  const isInterceptor = ent.team === 'blue';
  const realName = isInterceptor
    ? (INTERCEPTOR_NAMES[ent.kind] || ent.kind)
    : (THREAT_NAMES[ent.kind] || ent.kind);

  const altM = ent.pos[2];
  const altStr = altM > 1000
    ? `${altM.toFixed(0)} m (${(altM / 1000).toFixed(1)} km)`
    : `${altM.toFixed(0)} m`;

  // Fuel remaining (interceptors only).
  let fuelStr = '—';
  if (isInterceptor && FUEL_S[ent.kind] !== undefined) {
    const spent = t - (ent.spawn_t ?? 0);
    const remaining = Math.max(0, FUEL_S[ent.kind] - spent);
    fuelStr = `${remaining.toFixed(1)} s`;
  }

  // Thrust indicator.
  let thrustHtml;
  if (!isInterceptor) {
    thrustHtml = `<span class="sp-dot sp-dot-off"></span><span class="sp-muted">Inertial</span>`;
  } else if (ent.thrust_active) {
    thrustHtml = `<span class="sp-dot sp-dot-on"></span>Motor burning`;
  } else {
    thrustHtml = `<span class="sp-dot sp-dot-off"></span><span class="sp-muted">Coasting</span>`;
  }

  // Target ID + kind.
  let targetStr = '—';
  let rangeStr = '—';
  if (ent.target_id !== null && ent.target_id !== undefined) {
    const tgt = entities.find((e) => e.id === ent.target_id && e.alive);
    if (tgt) {
      const tKind = THREAT_NAMES[tgt.kind] || INTERCEPTOR_NAMES[tgt.kind] || tgt.kind;
      targetStr = `#${tgt.id} · ${tKind}`;
      const dx = tgt.pos[0] - ent.pos[0];
      const dy = tgt.pos[1] - ent.pos[1];
      const dz = tgt.pos[2] - ent.pos[2];
      const r = Math.sqrt(dx * dx + dy * dy + dz * dz);
      rangeStr = r > 1000
        ? `${(r / 1000).toFixed(1)} km`
        : `${r.toFixed(0)} m`;
    } else {
      targetStr = `#${ent.target_id} (lost)`;
    }
  }

  // USD cost.
  let costStr = '—';
  if (isInterceptor && USD_COST[ent.kind] !== undefined) {
    costStr = fmtUsd(USD_COST[ent.kind]);
  } else if (!isInterceptor && THREAT_USD[ent.kind] !== undefined) {
    costStr = fmtUsd(THREAT_USD[ent.kind]);
  }

  // HP bar.
  const hpMax = ent.hp_max || 0;
  const hpCur = ent.hp || 0;
  const hpRatio = hpMax > 0 ? Math.max(0, Math.min(1, hpCur / hpMax)) : 0;
  const hpHtml = hpMax > 0
    ? `<div class="sp-row"><span class="sp-label">HP</span><span class="sp-val">${hpCur} / ${hpMax}</span></div>
       <div class="sp-hpbar-outer"><div class="sp-hpbar-inner" style="width:${(hpRatio * 100).toFixed(0)}%"></div></div>`
    : '';

  const teamClass = ent.team === 'red' ? 'sp-team-red' : 'sp-team-blue';
  const teamLabel = ent.team === 'red' ? 'RED' : 'BLUE';

  panel.innerHTML = `
    <button id="status-panel-close" class="sp-close" aria-label="Close">&times;</button>
    <div class="sp-title">
      <span class="sp-kind">${escapeHtml(realName)}</span>
      <span class="sp-team ${teamClass}">${teamLabel}</span>
    </div>
    <div class="sp-id">Entity #${ent.id}</div>
    <div class="sp-row"><span class="sp-label">Speed</span><span class="sp-val">${speed.toFixed(0)} m/s <span class="sp-mach">Mach ${(speed / MACH_1).toFixed(1)}</span></span></div>
    <div class="sp-row"><span class="sp-label">G-load</span><span class="sp-val">${gLoad.toFixed(1)} g</span></div>
    <div class="sp-row"><span class="sp-label">Altitude</span><span class="sp-val">${altStr}</span></div>
    ${hpHtml}
    <div class="sp-row"><span class="sp-label">Motor</span><span class="sp-val">${thrustHtml}</span></div>
    <div class="sp-row"><span class="sp-label">Fuel</span><span class="sp-val">${fuelStr}</span></div>
    <div class="sp-row"><span class="sp-label">Target</span><span class="sp-val">${escapeHtml(targetStr)}</span></div>
    <div class="sp-row"><span class="sp-label">Range</span><span class="sp-val">${rangeStr}</span></div>
    <div class="sp-row"><span class="sp-label">Unit cost</span><span class="sp-val">${costStr}</span></div>
  `;
  // Rebind close button — innerHTML wiped the old listener.
  const closeBtn = document.getElementById('status-panel-close');
  if (closeBtn) closeBtn.addEventListener('click', clearSelection);
}

function renderDestroyed() {
  const panel = document.getElementById('status-panel');
  if (!panel) return;
  panel.innerHTML = `
    <button id="status-panel-close" class="sp-close" aria-label="Close">&times;</button>
    <div class="sp-title"><span class="sp-destroyed">DESTROYED</span></div>
    <div class="sp-id">Entity #${selectedId}</div>
  `;
  const closeBtn = document.getElementById('status-panel-close');
  if (closeBtn) closeBtn.addEventListener('click', clearSelection);
}

function fmtUsd(n) {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}k`;
  return `$${n}`;
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

export function clearStatusSelection() {
  clearSelection();
}
