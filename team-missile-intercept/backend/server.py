"""FastAPI + WebSocket server. Runs one Scenario in a background task,
broadcasts snapshots at config.STREAM_HZ, accepts control commands.

Run:
    cd backend
    pip install -r requirements.txt
    python server.py
then open http://localhost:8000/
"""
import asyncio
import json
import os
import time
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from sim import config, terrain
from sim.launcher import LAUNCHER_TEMPLATES, Launcher
from sim.scenarios import build_default_scenario
from sim.types import InterceptorType, MatchPhase

# Available Blue AI models — order matches the frontend dropdown.
# Each entry: (slot_id, display_name, model_path_or_None).
# None = rule-based BlueAI (no learned policy).
BLUE_AI_MODELS = [
    ("rule", "Heuristic", None),
    ("blue1", "RL Cautious (2x leak penalty)", "rl/models/blue_ai_1m_2xpenalty/model.zip"),
    ("blue2", "RL Balanced (1x leak penalty)", "rl/models/blue_ai_1m_1xpenalty/model.zip"),
    ("aoe", "RL Aggressive (AOE shaped)", "rl/runs/blue_local/blue_aoe_aggressive_B_shaped/model.zip"),
    ("v3", "RL Site-Priority (weighted)", "rl/runs/blue_reward_v2_finetune/model.zip"),
    ("v4", "RL CIWS Active (v4)", "rl/runs/blue_reward_v4_finetune/model.zip"),
    ("boyu_v2", "RL Boyu V2", "rl/runs/boyu_model_v2/model.zip"),
    ("boyu_v2a", "RL Boyu V2a", "rl/runs/boyu_modedlV2a/model.zip"),
    ("cap120", "RL 120-cap (scratch, 2.5M)", "rl/runs/blue_local/blue_120_v4_path2_scratch/model.zip"),
    ("megamodel", "RL Megamodel S4 final (curriculum)", "rl/runs/blue_local/blue_megamodel/model.zip"),
    ("megamodel_s1", "RL Megamodel S1 (Layout C only)", "rl/runs/blue_local/blue_megamodel/stages/S1_final.zip"),
    ("megamodel_s2", "RL Megamodel S2 (Layout C+D)", "rl/runs/blue_local/blue_megamodel/stages/S2_final.zip"),
    ("megamodel_s3", "RL Megamodel S3 (C+D + Red mix)", "rl/runs/blue_local/blue_megamodel/stages/S3_final.zip"),
    ("s1_retrain", "RL S1 Retrain (anti-PAC-spam, V4-style reward)", "rl/runs/blue_s1_retrain/model.zip"),
]

# Available Red AI models — order matches the frontend dropdown.
# "rule" = wave-based RedAI, "scripted" = ScriptedRedAI, others = learned.
RED_AI_MODELS = [
    ("rule", "5-Wave Heuristic", None),
    ("scripted", "Scripted 3-Chain", "scripted"),
    ("red1", "RL Learned v1", "rl/runs/red_20260421_205051/model.zip"),
    ("red2", "RL Learned v2", "rl/runs/red_20260421_234425/model.zip"),
    ("red_trainee_v2", "RL Red Trainee v2 (cost-aware + HGV evasion)", "rl/runs/red_local/red_trainee_parallel/model.zip"),
]


# Live-demo hook: learned-policy paths read from env vars at import time.
# Unset → scenario uses the rule-based RedAI / BlueAI as before (zero
# regression). Both vars are independent; either can be set alone.
_RED_POLICY_PATH = os.environ.get("RED_POLICY_PATH")
_BLUE_POLICY_PATH = os.environ.get("BLUE_POLICY_PATH")

# Alternative Red driver: `RED_WAVE_MODE=scripted` swaps rule-based RedAI
# for the event-driven `ScriptedRedAI` (3 parallel per-site chains with
# drone / cruise / ballistic / HGV overlap). Only consulted when no
# RED_POLICY_PATH is set — a learned Red policy always wins over the
# scripted alternative since both replace the same `scenario.red` slot.
_RED_WAVE_MODE = os.environ.get("RED_WAVE_MODE", "default").lower()


ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT.parent / "frontend"


class SimRunner:
    """Owns the Scenario and the sim loop. Broadcasts via .subscribe().

    M-TIER2-PHASE: the sim loop is phase-gated — `Scenario.step` is a
    no-op when `world.phase` is not RUNNING. The server no longer
    carries a separate `running` boolean; phase is the single source of
    truth. Snapshots still publish a legacy `running` bool for any
    older client code, derived from the phase.
    """

    def __init__(self):
        # Server flow starts in SETUP (auto_start=False) so the client
        # walks through the real start → running transition, giving the
        # Milestone J deployment UI a stable hook point. Headless tests
        # keep the old auto_start=True default when they call
        # build_default_scenario() themselves.
        self.scenario = build_default_scenario(auto_start=False)
        self._blue_ai_slot: str = "rule"
        self._blue_ai_name: str = "Rule-Based AI"
        self._red_ai_slot: str = "rule"
        self._red_ai_name: str = "Rule-Based (5 Waves)"
        self._apply_learned_policies()
        self.speed: float = 1.0   # time multiplier
        self._subscribers: set[asyncio.Queue] = set()
        self._task: asyncio.Task | None = None

    @property
    def running(self) -> bool:
        """Legacy `running` bool derived from phase. True iff the sim
        loop is actively advancing (`phase == RUNNING`)."""
        return self.scenario.world.phase == MatchPhase.RUNNING

    def reset(self):
        # Rebuild the scenario and leave it in SETUP — the end-of-match
        # Restart flow pairs this with a follow-up `start` command so
        # the operator gets the same one-click UX as before, but via the
        # real Match Phase FSM instead of a hidden auto-start bool.
        # Speed is preserved across resets — operators demoing at 20x
        # keep their pace between matches.
        # Preserve custom budgets and Blue AI selection across resets.
        old_red = self.scenario.world.red_budget_max
        old_blue = self.scenario.world.blue_budget_max
        old_layout_cost = self.scenario._layout_base_cost
        old_blue_ai_slot = self._blue_ai_slot
        old_red_ai_slot = self._red_ai_slot
        self.scenario = build_default_scenario(auto_start=False)
        self._apply_learned_policies()
        # Restore layout cost tracking — config.BLUE_LAUNCHER_POSITIONS
        # was mutated in-place by set_layout, so the new Scenario already
        # built the fleet from the layout's positions, but _layout_base_cost
        # reset to 0. Restore it so set_initial_budgets re-deducts properly.
        self.scenario._layout_base_cost = old_layout_cost
        self.scenario.set_initial_budgets(old_red, old_blue)
        # Always re-apply the operator's AI selections after reset.
        # build_default_scenario creates default RedAI/BlueAI ("rule").
        # _apply_learned_policies may override from env vars, but the
        # user's dropdown selection must take precedence. Skip only when
        # both the old slot and current slot are "rule" (default already
        # correct and no env-var override happened).
        if old_blue_ai_slot != "rule" or old_blue_ai_slot != self._blue_ai_slot:
            self._set_blue_ai_cmd({"slot": old_blue_ai_slot})
        if old_red_ai_slot != "rule" or old_red_ai_slot != self._red_ai_slot:
            self._set_red_ai_cmd({"slot": old_red_ai_slot})

    def _apply_learned_policies(self) -> None:
        """Live-demo hook. If ``RED_POLICY_PATH`` / ``BLUE_POLICY_PATH`` env
        vars are set, replace ``scenario.red`` / ``scenario.blue`` with
        learned-policy wrappers from ``rl.live_ai``. Either is independent;
        unset vars leave the rule-based AI unchanged. Called from
        ``__init__`` + ``reset`` so a fresh match always re-installs the
        wrappers (each learned match starts from zero round-robin /
        launcher state, matching the rule-based Restart UX).
        Fails fast — load errors propagate so demo-prep surfaces bugs
        instead of silently falling back to rule-based.
        """
        if _RED_POLICY_PATH:
            from rl.live_ai import LearnedRedAI
            self.scenario.red = LearnedRedAI(_RED_POLICY_PATH, self.scenario)
            for slot, name, path in RED_AI_MODELS:
                if path and _RED_POLICY_PATH.endswith(path):
                    self._red_ai_slot = slot
                    self._red_ai_name = name
                    break
            else:
                self._red_ai_slot = "custom"
                self._red_ai_name = _RED_POLICY_PATH
            print(
                f"[server] Loaded learned Red policy: {_RED_POLICY_PATH}",
                flush=True,
            )
        elif _RED_WAVE_MODE == "scripted":
            from sim.red_ai import ScriptedRedAI
            self.scenario.red = ScriptedRedAI(self.scenario)
            self._red_ai_slot = "scripted"
            self._red_ai_name = "Scripted (3 Chains)"
            print(
                "[server] Red wave mode: scripted "
                "(3 parallel chains per military site)",
                flush=True,
            )
        if _BLUE_POLICY_PATH:
            from rl.live_ai import LearnedBlueAI
            self.scenario.blue = LearnedBlueAI(
                _BLUE_POLICY_PATH, self.scenario
            )
            # Match env-var path to a known slot for the dropdown
            for slot, name, path in BLUE_AI_MODELS:
                if path and _BLUE_POLICY_PATH.endswith(path):
                    self._blue_ai_slot = slot
                    self._blue_ai_name = name
                    break
            else:
                self._blue_ai_slot = "custom"
                self._blue_ai_name = _BLUE_POLICY_PATH
            print(
                f"[server] Loaded learned Blue policy: {_BLUE_POLICY_PATH}",
                flush=True,
            )

    async def _loop(self):
        dt = config.DT
        stream_period = 1.0 / config.STREAM_HZ
        last_stream = 0.0
        sim_steps_per_stream = int(round(stream_period / dt))
        if sim_steps_per_stream < 1:
            sim_steps_per_stream = 1

        while True:
            t0 = time.perf_counter()
            # Phase-gated advancement (M-TIER2-PHASE). Scenario.step is
            # a no-op in SETUP / PAUSED / FINISHED; we only loop through
            # the speed-scaled tick count when we're actually RUNNING.
            # This keeps CPU down during a long demo-pause and makes the
            # fact that sim-time is frozen in non-running phases
            # structurally obvious from the loop shape.
            if self.scenario.world.phase == MatchPhase.RUNNING:
                n = max(1, int(sim_steps_per_stream * self.speed))
                for _ in range(n):
                    self.scenario.step(dt)
                    # Scenario.step auto-transitions RUNNING → FINISHED
                    # when the winner resolves; break so we don't burn
                    # the rest of the speed-scaled loop on a done match.
                    if self.scenario.world.phase == MatchPhase.FINISHED:
                        break
            snap = self.scenario.snapshot()
            snap["running"] = self.running
            snap["speed"] = self.speed
            snap["blue_ai_slot"] = self._blue_ai_slot
            snap["blue_ai_name"] = self._blue_ai_name
            snap["red_ai_slot"] = self._red_ai_slot
            snap["red_ai_name"] = self._red_ai_name
            msg = json.dumps(snap)
            for q in list(self._subscribers):
                try:
                    q.put_nowait(msg)
                except asyncio.QueueFull:
                    pass
            # sleep remainder of stream period
            elapsed = time.perf_counter() - t0
            sleep_for = max(0.0, stream_period - elapsed)
            await asyncio.sleep(sleep_for)

    def ensure_task(self):
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=8)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    def handle_command(self, cmd: dict) -> "dict | None":
        """Translate a WebSocket command into a phase transition or a
        scalar setting. Returns an acknowledgment or error dict that the
        caller (`_consume`) forwards to the sending socket; returns None
        for commands with no response (speed).

        Success responses:  {"type": "phase_change", "phase": "<new>"}
        Error responses:    {"type": "error", "reason":
                             "illegal_transition", "from": "<p>",
                             "to": "<p>"}
        """
        kind = cmd.get("cmd")
        if kind == "start":
            return self._phase_cmd(MatchPhase.RUNNING)
        if kind == "pause":
            return self._phase_cmd(MatchPhase.PAUSED)
        if kind == "resume":
            return self._phase_cmd(MatchPhase.RUNNING)
        if kind == "reset":
            # Reset short-circuits the FSM (rebuilds the World, which
            # naturally starts in SETUP) — any current phase is allowed
            # as the starting state, so this never reports an illegal-
            # transition error. The frontend Restart button pairs this
            # with a follow-up `start` to land in RUNNING.
            self.reset()
            return {"type": "phase_change", "phase": MatchPhase.SETUP.value}
        if kind == "speed":
            try:
                v = float(cmd.get("value", 1.0))
                if 0.1 <= v <= 50.0:
                    self.speed = v
            except (TypeError, ValueError):
                pass
            return None
        if kind == "place_launcher":
            return self._place_launcher_cmd(cmd)
        if kind == "add_launcher":
            return self._add_launcher_cmd(cmd)
        if kind == "remove_launcher":
            return self._remove_launcher_cmd(cmd)
        if kind == "ai_auto":
            return self._ai_auto_cmd()
        if kind == "set_layout":
            return self._set_layout_cmd(cmd)
        if kind == "set_budget":
            return self._set_budget_cmd(cmd)
        if kind == "set_blue_ai":
            return self._set_blue_ai_cmd(cmd)
        if kind == "set_red_ai":
            return self._set_red_ai_cmd(cmd)
        return None

    def _set_budget_cmd(self, cmd: dict) -> "dict | None":
        """Handle `{cmd: 'set_budget', red_budget_usd, blue_budget_usd}`.

        Only legal during SETUP. Both values must sit in [$10M, $1B]. On
        success, `Scenario.set_initial_budgets` rewrites both the current
        balance and the `_max` HUD denominator so the next snapshot shows
        the new values; no ack is returned (operator sees the change on
        the HUD budget bars within one tick).
        """
        phase = self.scenario.world.phase
        if phase != MatchPhase.SETUP:
            return {
                "type": "error",
                "reason": "illegal_budget_edit",
                "detail": f"phase is {phase.value}, must be setup",
            }
        try:
            red_usd = int(cmd.get("red_budget_usd"))
            blue_usd = int(cmd.get("blue_budget_usd"))
        except (TypeError, ValueError):
            return {
                "type": "error",
                "reason": "illegal_budget_edit",
                "detail": "red_budget_usd / blue_budget_usd must be integers",
            }
        # $10M .. $1B. Tight enough that a mis-typed 0 or a runaway
        # 10**12 surfaces as an error rather than silently producing a
        # match with no budget or effectively-infinite budget.
        MIN_BUDGET = 10_000_000
        MAX_BUDGET = 1_000_000_000
        if not (MIN_BUDGET <= red_usd <= MAX_BUDGET):
            return {
                "type": "error",
                "reason": "illegal_budget_edit",
                "detail": (
                    f"red_budget_usd {red_usd} out of range "
                    f"[{MIN_BUDGET}, {MAX_BUDGET}]"
                ),
            }
        if not (MIN_BUDGET <= blue_usd <= MAX_BUDGET):
            return {
                "type": "error",
                "reason": "illegal_budget_edit",
                "detail": (
                    f"blue_budget_usd {blue_usd} out of range "
                    f"[{MIN_BUDGET}, {MAX_BUDGET}]"
                ),
            }
        try:
            self.scenario.set_initial_budgets(red_usd, blue_usd)
        except ValueError as e:
            return {
                "type": "error",
                "reason": "illegal_budget_edit",
                "detail": str(e),
            }
        return None

    def _set_blue_ai_cmd(self, cmd: dict) -> "dict | None":
        """Handle `{cmd: 'set_blue_ai', slot}`. Switches the Blue AI
        between rule-based and learned policy models. SETUP only."""
        phase = self.scenario.world.phase
        if phase != MatchPhase.SETUP:
            return {
                "type": "error",
                "reason": "illegal_ai_switch",
                "detail": f"phase is {phase.value}, must be setup",
            }
        slot = cmd.get("slot")
        match = next(
            (m for m in BLUE_AI_MODELS if m[0] == slot), None
        )
        if match is None:
            return {
                "type": "error",
                "reason": "illegal_ai_switch",
                "detail": f"unknown slot {slot!r}",
            }
        _, name, path = match
        if path is None:
            # Rule-based
            from sim.blue_ai import BlueAI
            self.scenario.blue = BlueAI()
            # Rebuild fleet from current config positions
            self.scenario.blue.launchers = self.scenario.blue.launchers
        else:
            try:
                from rl.live_ai import LearnedBlueAI
                self.scenario.blue = LearnedBlueAI(path, self.scenario)
            except Exception as e:
                return {
                    "type": "error",
                    "reason": "illegal_ai_switch",
                    "detail": f"failed to load {name}: {e}",
                }
        self._blue_ai_slot = slot
        self._blue_ai_name = name
        print(f"[server] Blue AI switched: {name}", flush=True)
        return {
            "type": "blue_ai_changed",
            "slot": slot,
            "name": name,
        }

    def _set_red_ai_cmd(self, cmd: dict) -> "dict | None":
        """Handle `{cmd: 'set_red_ai', slot}`. Switches the Red AI
        between rule-based, scripted, and learned policy models. SETUP only."""
        phase = self.scenario.world.phase
        if phase != MatchPhase.SETUP:
            return {
                "type": "error",
                "reason": "illegal_ai_switch",
                "detail": f"phase is {phase.value}, must be setup",
            }
        slot = cmd.get("slot")
        match = next(
            (m for m in RED_AI_MODELS if m[0] == slot), None
        )
        if match is None:
            return {
                "type": "error",
                "reason": "illegal_ai_switch",
                "detail": f"unknown slot {slot!r}",
            }
        _, name, path = match
        if path is None:
            # Rule-based waves
            from sim.red_ai import RedAI, build_demo_waves
            self.scenario.red = RedAI(build_demo_waves())
        elif path == "scripted":
            from sim.red_ai import ScriptedRedAI
            self.scenario.red = ScriptedRedAI(self.scenario)
        else:
            try:
                from rl.live_ai import LearnedRedAI
                self.scenario.red = LearnedRedAI(path, self.scenario)
            except Exception as e:
                return {
                    "type": "error",
                    "reason": "illegal_ai_switch",
                    "detail": f"failed to load {name}: {e}",
                }
        self._red_ai_slot = slot
        self._red_ai_name = name
        print(f"[server] Red AI switched: {name}", flush=True)
        return {
            "type": "red_ai_changed",
            "slot": slot,
            "name": name,
        }

    # --- W16: live-demo defensive-layout selector (backed by
    # team-missile-intercept/game-core/CANDIDATE_LAYOUTS_2026-04-22.json).
    _LAYOUTS_JSON_PATH = (
        ROOT.parent / "game-core" / "CANDIDATE_LAYOUTS_2026-04-22.json"
    )

    def _set_layout_cmd(self, cmd: dict) -> dict:
        """Handle `{cmd: 'set_layout', slot}`. Reads the candidate
        layouts JSON, matches `slot` case-insensitively against the
        `layouts[*].slot` field, and calls `Scenario.set_layout` with
        the matching roster. A `slot` value of 'current' is a no-op —
        returned as an explicit ack so the frontend can report that
        nothing changed. Only legal in SETUP phase (enforced again
        inside `Scenario.set_layout`)."""
        slot = cmd.get("slot")
        if not isinstance(slot, str) or not slot:
            return {
                "type": "error",
                "reason": "illegal_layout",
                "detail": "missing or empty slot",
            }
        if slot.lower() == "current":
            return {
                "type": "layout_applied",
                "slot": "current",
                "name": "Current (from config)",
                "launcher_count": sum(
                    len(v) for v in config.BLUE_LAUNCHER_POSITIONS.values()
                ),
            }
        try:
            with open(self._LAYOUTS_JSON_PATH, "r", encoding="utf-8") as f:
                layouts_data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            return {
                "type": "error",
                "reason": "illegal_layout",
                "detail": f"cannot read layouts JSON: {e}",
            }
        match = next(
            (
                l for l in layouts_data.get("layouts", [])
                if str(l.get("slot", "")).upper() == slot.upper()
            ),
            None,
        )
        if match is None:
            return {
                "type": "error",
                "reason": "illegal_layout",
                "detail": f"unknown slot {slot!r}",
            }
        roster = {
            kind: [tuple(pos) for pos in positions]
            for kind, positions in match.get("roster", {}).items()
        }
        try:
            self.scenario.set_layout(roster)
        except (RuntimeError, ValueError) as e:
            return {
                "type": "error",
                "reason": "illegal_layout",
                "detail": str(e),
            }
        print(
            f"[server] layout applied: {match.get('slot')} "
            f"({match.get('launcher_count', 0)} launchers)",
            flush=True,
        )
        return {
            "type": "layout_applied",
            "slot": match.get("slot"),
            "name": match.get("name", match.get("slot")),
            "launcher_count": match.get("launcher_count", 0),
            "base_cost_usd": match.get("base_cost_usd", 0),
        }

    # --- M-TIER2-J Part 1: deployment-phase placement API ---
    def _place_launcher_cmd(self, cmd: dict) -> dict:
        """Handle `{cmd: 'place_launcher', launcher_id, pos: [x, y]}`.

        Only legal during SETUP. Position must satisfy
        `terrain.point_on_south_land`. Success updates the launcher's
        position in-place; the next snapshot carries the new value. No
        ack is emitted on success (client reads the authoritative
        position from the next snapshot).

        Error responses are typed frames consumed by the W6-audit-E
        typed-frame router on the frontend → red phase-chip flash with
        the reason as tooltip.
        """
        phase = self.scenario.world.phase
        if phase != MatchPhase.SETUP:
            return {
                "type": "error",
                "reason": "illegal_placement",
                "detail": f"phase is {phase.value}, must be setup",
            }
        launcher_id = cmd.get("launcher_id")
        pos = cmd.get("pos")
        if not isinstance(launcher_id, str) or not launcher_id:
            return {
                "type": "error",
                "reason": "illegal_placement",
                "detail": "missing or empty launcher_id",
            }
        if (
            not isinstance(pos, (list, tuple))
            or len(pos) != 2
        ):
            return {
                "type": "error",
                "reason": "illegal_placement",
                "detail": "pos must be [x, y]",
            }
        try:
            x = float(pos[0])
            y = float(pos[1])
        except (TypeError, ValueError):
            return {
                "type": "error",
                "reason": "illegal_placement",
                "detail": "pos components must be numeric",
            }
        lch = self._find_launcher(launcher_id)
        if lch is None:
            return {
                "type": "error",
                "reason": "illegal_placement",
                "detail": f"unknown launcher_id {launcher_id!r}",
            }
        if not terrain.point_on_south_land(x, y):
            return {
                "type": "error",
                "reason": "illegal_placement",
                "detail": "position not on south land",
            }
        lch.pos = (x, y)
        return None

    def _ai_auto_cmd(self) -> dict:
        """Handle `{cmd: 'ai_auto'}`. M-TIER2-J Part 2 extended this
        beyond Part 1's position-only reset: now restores the full
        config-default roster AND positions. Implementation: remove
        every current launcher (refunding base_cost), then add one
        launcher per `BLUE_LAUNCHER_POSITIONS` entry (deducting
        base_cost).

        Clamp policy: individual `remove_launcher` clamps refunds at
        `BLUE_BUDGET_START` to prevent abuse (remove-for-money above
        start). `ai_auto` is a single atomic operation — clamping in
        the middle of its internal refund step would leave the net
        balance off by the default-roster total, turning a "revert"
        click on a pristine default layout into a $41.5 M budget
        loss. So refunds inside ai_auto are *uncapped*, and we only
        clamp the final budget at `BLUE_BUDGET_START` so the operator
        can never end above the starting budget (e.g. after a weird
        sequence of illegal but phase-accepted states).

        Net effect: from a pristine default state, ai_auto is exactly
        net-zero (budget unchanged, roster identical). From an
        arbitrary state where operator added $X of extras and has
        $Y spent on interceptors (Y=0 in SETUP since sim is frozen),
        ai_auto restores the default roster and returns budget to
        `BLUE_BUDGET_START - Y` (the operator's non-refundable sunk
        cost).

        A real placement AI (Oskar) is still deferred; the button's
        purpose is to surface the hook point + one-click roster
        revert.
        """
        phase = self.scenario.world.phase
        if phase != MatchPhase.SETUP:
            return {
                "type": "error",
                "reason": "illegal_placement",
                "detail": f"phase is {phase.value}, must be setup",
            }
        world = self.scenario.world
        fleet = self.scenario.blue.launchers
        # Step 1: remove every current launcher, refunding base_cost.
        # No per-step clamp here — see clamp policy note above.
        for lch in list(fleet.launchers):
            cost = config.LAUNCHER_BASE_COSTS.get(lch.kind.value, 0)
            world.blue_budget += cost
        fleet.launchers.clear()
        # Step 2: add one launcher per config default entry. Use the
        # same construction the LauncherFleet __init__ uses so ids +
        # templates stay consistent.
        for kind_str, pos_list in config.BLUE_LAUNCHER_POSITIONS.items():
            try:
                kind = InterceptorType(kind_str)
            except ValueError:
                continue
            tmpl = LAUNCHER_TEMPLATES.get(kind)
            if tmpl is None:
                continue
            base_cost = config.LAUNCHER_BASE_COSTS.get(kind_str, 0)
            for idx, (x, y) in enumerate(pos_list):
                lid = f"{kind.value}_{idx}"
                fleet.launchers.append(
                    Launcher(
                        kind=kind,
                        pos=(float(x), float(y)),
                        id=lid,
                        **tmpl,
                    )
                )
                world.blue_budget -= base_cost
        # Final clamp at BLUE_BUDGET_START: operator should never end
        # above the starting budget even under unusual entry paths.
        world.blue_budget = min(
            config.BLUE_BUDGET_START, world.blue_budget
        )
        return None

    # --- M-TIER2-J Part 2: buy-vehicle / roster add+remove ---
    def _add_launcher_cmd(self, cmd: dict) -> "dict | None":
        """Handle `{cmd: 'add_launcher', kind, pos: [x, y]}`. Only
        legal during SETUP. Validates kind, position (south-land), and
        budget. On success constructs a new `Launcher` (full magazine,
        default reload state) with a unique id of the form
        `f"{kind}_{next_idx}"` where next_idx is one past the current
        max within-kind index. Deducts `LAUNCHER_BASE_COSTS[kind]` from
        `world.blue_budget`.
        """
        phase = self.scenario.world.phase
        if phase != MatchPhase.SETUP:
            return {
                "type": "error",
                "reason": "illegal_placement",
                "detail": f"phase is {phase.value}, must be setup",
            }
        kind_str = cmd.get("kind")
        if not isinstance(kind_str, str) or not kind_str:
            return {
                "type": "error",
                "reason": "illegal_placement",
                "detail": "missing or empty kind",
            }
        try:
            kind = InterceptorType(kind_str)
        except ValueError:
            return {
                "type": "error",
                "reason": "illegal_placement",
                "detail": f"unknown launcher kind {kind_str!r}",
            }
        tmpl = LAUNCHER_TEMPLATES.get(kind)
        if tmpl is None:
            # Every enum value has a template today, but keep the guard
            # so a future enum addition without a template doesn't
            # silently create an un-fireable launcher.
            return {
                "type": "error",
                "reason": "illegal_placement",
                "detail": f"no template for kind {kind_str!r}",
            }
        pos = cmd.get("pos")
        if not isinstance(pos, (list, tuple)) or len(pos) != 2:
            return {
                "type": "error",
                "reason": "illegal_placement",
                "detail": "pos must be [x, y]",
            }
        try:
            x = float(pos[0])
            y = float(pos[1])
        except (TypeError, ValueError):
            return {
                "type": "error",
                "reason": "illegal_placement",
                "detail": "pos components must be numeric",
            }
        if not terrain.point_on_south_land(x, y):
            return {
                "type": "error",
                "reason": "illegal_placement",
                "detail": "position not on south land",
            }
        world = self.scenario.world
        base_cost = config.LAUNCHER_BASE_COSTS.get(kind_str, 0)
        if world.blue_budget < base_cost:
            return {
                "type": "error",
                "reason": "insufficient_budget",
                "detail": (
                    f"need ${base_cost}, have ${world.blue_budget}"
                ),
            }
        # Next within-kind id: one past the max existing idx for this
        # kind (parsing the trailing _N off the id string). A fresh
        # kind with no existing launchers starts at 0.
        next_idx = 0
        for existing in self.scenario.blue.launchers.launchers:
            if existing.kind != kind:
                continue
            suffix = existing.id[len(kind.value) + 1:]
            try:
                idx = int(suffix)
            except ValueError:
                continue
            if idx >= next_idx:
                next_idx = idx + 1
        lid = f"{kind.value}_{next_idx}"
        new_lch = Launcher(
            kind=kind,
            pos=(x, y),
            id=lid,
            **tmpl,
        )
        self.scenario.blue.launchers.launchers.append(new_lch)
        world.blue_budget -= base_cost
        return None

    def _remove_launcher_cmd(self, cmd: dict) -> "dict | None":
        """Handle `{cmd: 'remove_launcher', launcher_id}`. Only legal
        during SETUP. Removes the launcher from the fleet and refunds
        its base_cost to `world.blue_budget` (clamped at
        BLUE_BUDGET_START so refunds never exceed the starting budget
        — protects against repeated add/remove cycles after mid-setup
        spend from producing a virtual surplus).
        """
        phase = self.scenario.world.phase
        if phase != MatchPhase.SETUP:
            return {
                "type": "error",
                "reason": "illegal_placement",
                "detail": f"phase is {phase.value}, must be setup",
            }
        launcher_id = cmd.get("launcher_id")
        if not isinstance(launcher_id, str) or not launcher_id:
            return {
                "type": "error",
                "reason": "illegal_placement",
                "detail": "missing or empty launcher_id",
            }
        lch = self._find_launcher(launcher_id)
        if lch is None:
            return {
                "type": "error",
                "reason": "illegal_placement",
                "detail": f"unknown launcher_id {launcher_id!r}",
            }
        world = self.scenario.world
        base_cost = config.LAUNCHER_BASE_COSTS.get(lch.kind.value, 0)
        self._refund_budget(world, base_cost)
        self.scenario.blue.launchers.launchers.remove(lch)
        return None

    @staticmethod
    def _refund_budget(world, amount: int) -> None:
        """Refund `amount` to `world.blue_budget`, clamped at
        `config.BLUE_BUDGET_START` so the operator never accumulates
        more than the starting budget via refund cycles. Extracted so
        both `_remove_launcher_cmd` and the `_ai_auto_cmd` roster
        reset share the identical clamp."""
        world.blue_budget = min(
            config.BLUE_BUDGET_START, world.blue_budget + amount
        )

    def _find_launcher(self, launcher_id: str):
        for lch in self.scenario.blue.launchers.launchers:
            if lch.id == launcher_id:
                return lch
        return None

    def _phase_cmd(self, to: MatchPhase) -> dict:
        prev = self.scenario.world.phase
        if self.scenario.world.transition(to):
            return {"type": "phase_change", "phase": to.value}
        return {
            "type": "error",
            "reason": "illegal_transition",
            "from": prev.value,
            "to": to.value,
        }


runner = SimRunner()

app = FastAPI(title="Missile Intercept Demo")


@app.on_event("startup")
async def on_startup():
    runner.ensure_task()


@app.get("/")
async def index():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/healthz")
async def healthz():
    return {
        "ok": True,
        "t": runner.scenario.world.t,
        "running": runner.running,
        "phase": runner.scenario.world.phase.value,
    }


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    q = runner.subscribe()
    try:
        producer = asyncio.create_task(_pump(ws, q))
        consumer = asyncio.create_task(_consume(ws))
        done, pending = await asyncio.wait(
            {producer, consumer}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
    except WebSocketDisconnect:
        pass
    finally:
        runner.unsubscribe(q)


async def _pump(ws: WebSocket, q: asyncio.Queue):
    try:
        while True:
            msg = await q.get()
            await ws.send_text(msg)
    except (WebSocketDisconnect, RuntimeError):
        return


async def _consume(ws: WebSocket):
    try:
        while True:
            text = await ws.receive_text()
            try:
                cmd = json.loads(text)
            except json.JSONDecodeError:
                continue
            response = runner.handle_command(cmd)
            # Sender-only ack / error (M-TIER2-PHASE). Broadcasting to
            # every subscriber would cause observer clients to briefly
            # think they triggered the transition; keeping it
            # sender-only also scopes illegal-transition errors to the
            # client that sent the bad command.
            if response is not None:
                try:
                    await ws.send_text(json.dumps(response))
                except (WebSocketDisconnect, RuntimeError):
                    return
    except WebSocketDisconnect:
        return


# Static assets (frontend/js/, frontend/style.css). Must come after routes.
if FRONTEND_DIR.exists():
    app.mount(
        "/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static"
    )


if __name__ == "__main__":
    import uvicorn

    # Port 8000 is frequently reserved by Windows (Hyper-V/WSL2/Docker
    # Desktop excluded port ranges include 8000/8080/8088), causing
    # WinError 10013 on bind. 5147 lands outside the typical reserved
    # ranges on both hackathon laptops. Override with the PORT env var
    # if needed (`set PORT=xxxx` in cmd, `PORT=xxxx py ...` in bash).
    port = int(os.environ.get("PORT", "5174"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
