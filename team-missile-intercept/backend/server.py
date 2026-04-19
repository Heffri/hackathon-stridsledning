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

from sim import config
from sim.scenarios import build_default_scenario
from sim.types import MatchPhase


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
        self.scenario = build_default_scenario(auto_start=False)

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

    def handle_command(self, cmd: dict) -> None:
        """Translate a WebSocket command into a phase transition or a
        scalar setting. Illegal transitions are silently ignored here;
        Subtask C wires up the explicit `error` response path.
        """
        kind = cmd.get("cmd")
        if kind == "start":
            # SETUP → RUNNING. No-op if already running or in an illegal
            # phase; Subtask C reports the error to the client.
            self.scenario.world.transition(MatchPhase.RUNNING)
        elif kind == "pause":
            # RUNNING → PAUSED.
            self.scenario.world.transition(MatchPhase.PAUSED)
        elif kind == "reset":
            self.reset()
        elif kind == "speed":
            try:
                v = float(cmd.get("value", 1.0))
                if 0.1 <= v <= 20.0:
                    self.speed = v
            except (TypeError, ValueError):
                pass


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
            runner.handle_command(cmd)
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
