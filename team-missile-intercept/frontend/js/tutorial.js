// tutorial.js — Intro + Setup-phase instruction popups.
// Two modals:
//   1. Intro (shown once on page load) — explains AI vs AI concept, objective, roles.
//   2. Setup tips (shown once per session when SETUP phase is entered) — what to do.

// ── Intro modal ──────────────────────────────────────────────────────────────

const INTRO_HTML = `
<div id="tutorial-backdrop" class="tut-backdrop">
  <div class="tut-card tut-card-intro">
    <div class="tut-header">
      <div class="tut-title">SMART STRIDSLEDNING</div>
      <div class="tut-subtitle">AI vs AI Missile Defence — Saab Hackathon 2026</div>
    </div>

    <div class="tut-factions">
      <div class="tut-faction tut-faction-red">
        <div class="tut-faction-label">⬤ RED FORCE — Attacker (AI)</div>
        <div class="tut-faction-desc">
          Launches scripted waves of threats from the north: drones, subsonic cruise missiles,
          ballistic missiles, and Mach-17 hypersonic gliders. Each wave escalates in speed and
          difficulty. Red has a finite budget — every threat costs resources.
        </div>
      </div>
      <div class="tut-faction tut-faction-blue">
        <div class="tut-faction-label">⬤ BLUE FORCE — Defender (AI)</div>
        <div class="tut-faction-desc">
          A layered air-defence network intercepts threats autonomously using a cost-exchange
          ladder: CIWS point-defence → RBS-70 NG → IRIS-T SLS/SLM → PAC-2 GEM+ → PAC-3 MSE.
          Blue AI chooses weapon-target pairings in real time based on threat type, range, and
          remaining ammunition.
        </div>
      </div>
    </div>

    <div class="tut-section">
      <div class="tut-section-title">🎖 YOUR ROLE — Commander</div>
      <div class="tut-section-body">
        You control the <strong>SETUP phase</strong> before each match.
        Position Blue launchers on the map, adjust the roster (add / remove weapon systems
        within your $120M budget), or click <em>AI Auto</em> to use the balanced default.
        Once you press <strong>Start Match</strong>, both AIs take over — sit back and watch
        the battle unfold.
      </div>
    </div>

    <div class="tut-objectives">
      <div class="tut-obj tut-obj-blue">
        <span class="tut-obj-icon">🔵</span>
        <span><strong>Blue wins</strong> if all Red waves are defeated with at least one defended site still standing.</span>
      </div>
      <div class="tut-obj tut-obj-red">
        <span class="tut-obj-icon">🔴</span>
        <span><strong>Red wins</strong> if any Blue site (airbase, city, capital) reaches 0 HP.</span>
      </div>
    </div>

    <button id="tut-intro-close" class="tut-btn">Got it — let's set up</button>
  </div>
</div>
`;

// ── Setup tips card ───────────────────────────────────────────────────────────

const SETUP_TIPS_HTML = `
<div id="tutorial-setup" class="tut-setup-card">
  <button id="tut-setup-close" class="tut-setup-close" title="Dismiss">✕</button>
  <div class="tut-setup-title">⚙ SETUP PHASE</div>
  <ul class="tut-setup-list">
    <li><span class="tut-key">Drag</span> launcher boxes on the 3D map to reposition them — only valid on southern land.</li>
    <li><span class="tut-key">+ Add</span> spawns a new launcher at the base; drag it to final position.</li>
    <li><span class="tut-key">− Remove</span> sells the selected launcher back (refunds its base cost).</li>
    <li><span class="tut-key">AI Auto</span> resets to the balanced default roster and positions.</li>
    <li><span class="tut-key">Start Match</span> locks the deployment and begins the Red attack.</li>
  </ul>
  <div class="tut-setup-tip">Tip: click any launcher to inspect its range, ammo, and cost in the right panel.</div>
</div>
`;

// ── Public API ────────────────────────────────────────────────────────────────

let _introShown = false;
let _setupTipShown = false;

/** Inject the intro modal into the DOM and return a Promise that resolves when the user dismisses it. */
export function showIntro() {
  if (_introShown) return Promise.resolve();
  _introShown = true;
  return new Promise((resolve) => {
    const host = document.createElement('div');
    host.innerHTML = INTRO_HTML;
    document.body.appendChild(host.firstElementChild);
    document.getElementById('tut-intro-close').addEventListener('click', () => {
      const backdrop = document.getElementById('tutorial-backdrop');
      if (backdrop) {
        backdrop.classList.add('tut-fade-out');
        backdrop.addEventListener('animationend', () => backdrop.remove(), { once: true });
      }
      resolve();
    });
  });
}

/** Show the one-shot setup tips card (call whenever phase transitions to 'setup', idempotent). */
export function showSetupTip() {
  if (_setupTipShown) return;
  if (document.getElementById('tutorial-setup')) return;
  _setupTipShown = true;
  const host = document.createElement('div');
  host.innerHTML = SETUP_TIPS_HTML;
  const card = host.firstElementChild;
  document.body.appendChild(card);
  document.getElementById('tut-setup-close').addEventListener('click', () => {
    card.classList.add('tut-setup-fade-out');
    card.addEventListener('animationend', () => card.remove(), { once: true });
  });
  // Auto-dismiss after 18 s so it doesn't block experienced users.
  setTimeout(() => {
    if (card.isConnected) {
      card.classList.add('tut-setup-fade-out');
      card.addEventListener('animationend', () => card.remove(), { once: true });
    }
  }, 18000);
}
