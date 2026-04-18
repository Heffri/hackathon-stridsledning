// minimap.js — 2-D Boreal Passage tactical overlay, driven by WS snapshots.
//
// Coordinate chain (all exact — verified against scene.js saabToScene()):
//   Backend world: X=east 0..150 000 m,  Y=north 0..250 000 m,  Z=up
//   Saab CSV:      x_km 0..1667 east,     y_km 0..1300 south-positive
//   Scene crops Saab Y window [280..1080 km] and stretches to the arena.
//   SVG viewBox:   0..1000 px (east),      0..780 px (south)
//
//   worldToMapSvg(wx_m, wy_m):
//     saab_x = wx * (1667/150000)
//     saab_y = 280 + (1 − wy/250000) * 800   // yn=0 → south(1080), yn=1 → north(280)
//     svg_x  = saab_x * (1000/1667)
//     svg_y  = saab_y  * (780/1300)
//
//   Anchor check: base(75000,5000) → SVG(500,638)  ✓ south coast
//                 north(75000,245000) → SVG(500,178) ✓ north coast

const SVG_NS    = 'http://www.w3.org/2000/svg';
const TRAIL_MAX = 50;   // trail history per entity (more visible fullscreen)

// Fullscreen: viewBox 1000×780 fills ~1920×1080 so 1 vb-unit ≈ 1.9 px.
// Dot/trail sizes are in viewBox units — no changes needed for scaling,
// but we use slightly larger values than the old minimap for readability.

let entityLayer = null;
let expLayer    = null;
const trails    = new Map();   // entityId → [{x,y}, ...]
const explosionDots = [];      // {cx,cy,born_t,el}

// ── coord transform ──────────────────────────────────────────────────────────
export function worldToMapSvg(wx, wy) {
  const saab_x = wx * (1667 / 150_000);
  const saab_y = 280 + (1 - wy / 250_000) * 800;
  return [saab_x * (1000 / 1667), saab_y * (780 / 1300)];
}

// ── init ─────────────────────────────────────────────────────────────────────
export function initMinimap() {
  const svg = document.getElementById('minimap-svg');
  if (!svg) return;

  expLayer = document.createElementNS(SVG_NS, 'g');
  expLayer.id = 'mm-explosions';
  svg.appendChild(expLayer);

  entityLayer = document.createElementNS(SVG_NS, 'g');
  entityLayer.id = 'mm-entities';
  svg.appendChild(entityLayer);
}

// ── helpers ───────────────────────────────────────────────────────────────────
function el(tag, attrs) {
  const e = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  return e;
}

// ── update (called every animation frame) ─────────────────────────────────────
export function updateMinimap(snap) {
  if (!entityLayer) return;

  // Clear entity layer
  entityLayer.replaceChildren();

  const aliveEntities = snap.entities.filter(e => e.alive);
  const aliveIds = new Set(aliveEntities.map(e => e.id));

  // ── draw entities ────────────────────────────────────────────────────────
  for (const e of aliveEntities) {
    const [sx, sy] = worldToMapSvg(e.pos[0], e.pos[1]);
    const isRed = e.team === 'red';
    const color = isRed ? '#ff4444' : '#3fc1ff';
    const glowColor = isRed ? 'rgba(255,60,60,0.35)' : 'rgba(60,200,255,0.35)';

    // trail
    if (!trails.has(e.id)) trails.set(e.id, []);
    const trail = trails.get(e.id);
    trail.push({ x: sx, y: sy });
    if (trail.length > TRAIL_MAX) trail.shift();

    if (trail.length > 1) {
      const pts = trail.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
      entityLayer.appendChild(el('polyline', {
        points: pts,
        stroke: isRed ? 'rgba(255,80,60,0.55)' : 'rgba(60,200,255,0.50)',
        'stroke-width': 2.5,
        fill: 'none',
        'stroke-linecap': 'round',
        'stroke-linejoin': 'round',
      }));
    }

    // glow halo
    const alt_km = e.pos[2] / 1000;
    const r = Math.min(3.5 + alt_km * 0.10, 10);
    entityLayer.appendChild(el('circle', {
      cx: sx.toFixed(1), cy: sy.toFixed(1),
      r: (r + 4).toFixed(1),
      fill: glowColor,
    }));
    // dot
    entityLayer.appendChild(el('circle', {
      cx: sx.toFixed(1), cy: sy.toFixed(1),
      r: r.toFixed(1),
      fill: color,
      stroke: '#000',
      'stroke-width': 0.8,
    }));
  }

  // trim stale trails
  for (const id of trails.keys()) {
    if (!aliveIds.has(id)) trails.delete(id);
  }

  // ── explosions ────────────────────────────────────────────────────────────
  for (const ev of (snap.events || [])) {
    if (ev.pos) {
      const [ex, ey] = worldToMapSvg(ev.pos[0], ev.pos[1]);
      const ring = el('circle', {
        cx: ex.toFixed(1), cy: ey.toFixed(1),
        r: 6,
        fill: 'rgba(255,200,60,0.75)',
        stroke: '#ffaa00',
        'stroke-width': 1,
      });
      expLayer.appendChild(ring);
      explosionDots.push({ el: ring, born: snap.t });
    }
  }
  // fade old explosions
  const now = snap.t;
  for (let i = explosionDots.length - 1; i >= 0; i--) {
    const d = explosionDots[i];
    const age = now - d.born;
    if (age > 2.5) {
      expLayer.removeChild(d.el);
      explosionDots.splice(i, 1);
    } else {
      d.el.setAttribute('opacity', (1 - age / 2.5).toFixed(2));
      d.el.setAttribute('r', (6 + age * 4).toFixed(1));
    }
  }
}
