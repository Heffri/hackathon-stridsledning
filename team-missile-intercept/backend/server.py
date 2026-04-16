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


ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT.parent / "frontend"


class SimRunner:
    """Owns the Scenario and the sim loop. Broadcasts via .subscribe()."""

    def __init__(self):
        self.scenario = build_default_scenario()
        self.running: bool = False
        self.speed: float = 1.0   # time multiplier
        self._subscribers: set[asyncio.Queue] = set()
        self._task: asyncio.Task | None = None

    def reset(self):
        self.scenario = build_default_scenario()
        self.running = False

    async def _loop(self):
        dt = config.DT
        stream_period = 1.0 / config.STREAM_HZ
        last_stream = 0.0
        sim_steps_per_stream = int(round(stream_period / dt))
        if sim_steps_per_stream < 1:
            sim_steps_per_stream = 1

        while True:
            t0 = time.perf_counter()
            if self.running:
                # advance N sim steps per wall-clock stream period, modulated by speed
                n = max(1, int(sim_steps_per_stream * self.speed))
                for _ in range(n):
                    self.scenario.step(dt)
                    if self.scenario.world.t > config.MAX_SIM_TIME:
                        self.running = False
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
        kind = cmd.get("cmd")
        if kind == "start":
            self.running = True
        elif kind == "pause":
            self.running = False
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
    return {"ok": True, "t": runner.scenario.world.t, "running": runner.running}


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

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
