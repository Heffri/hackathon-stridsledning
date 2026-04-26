"""Blue megamodel curriculum driver (cap 72/32/128).

Sequential stages S1 → S2 → S3 → S4. ONE train.py invocation per stage,
sized to HARD_CAP. A watchdog thread polls the training log; when
convergence is detected, it sends SIGINT to train.py — train.py catches
KeyboardInterrupt, saves model.zip, and exits cleanly. After the stage,
model copied to ``stages/<STAGE>_final.zip`` and pushed to GitHub.

Why single-train-per-stage rather than 200k increments:
  Each train.py call spawns fresh SubprocVecEnv workers. With
  episode_time_limit=5000s + n_envs=48, episodes run ~10000 decisions
  while each fresh increment of 200k transitions only gives 4166
  decisions per env. Episodes never finish within an increment and the
  Monitor never logs ep_rew_mean. By running ONE process for the entire
  stage, env state persists across rollouts and episodes do finish.

Run from backend/ root:

    python -m scripts.run_megamodel             # full pipeline
    python -m scripts.run_megamodel --stages S1 # one stage only
    python -m scripts.run_megamodel --resume    # skip stages whose final.zip exists
    python -m scripts.run_megamodel --no-push   # don't push between stages

Wall budget: 8 h total. Phase-2 (Red trainee) is launched separately by
``run_red_trainee.py``.
"""
from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional, Sequence

REPO_BACKEND = Path(__file__).resolve().parent.parent          # .../backend
RUN_BASE = REPO_BACKEND / "rl" / "runs" / "blue_local" / "blue_megamodel"
STAGES_DIR = RUN_BASE / "stages"
SCRIPTS_DIR = REPO_BACKEND / "scripts"
CHECK_CONV = SCRIPTS_DIR / "check_convergence.py"
PYTHON = sys.executable

# Common training flags (per spec).
COMMON_FLAGS = dict(
    n_envs=48,
    n_steps=1024,
    batch_size=256,
    n_epochs=4,
    lr=3e-4,
    gamma=0.995,
    gae_lambda=0.95,
    ent_coef=0.01,
    clip_range=0.2,
    episode_time_limit=5000.0,
    blue_budget=200_000_000,
    red_budget=150_000_000,
    device="cpu",
    save_every=200_000,
)

LAYOUTS_POOL_PATH = REPO_BACKEND / "rl" / "top3_layouts_CD.json"

# Convergence watchdog config.
WATCHDOG_POLL_S = 60      # how often to check the log for convergence
WATCHDOG_MIN_WALL_S = 300  # wait at least 5 min before allowing convergence
                           # (long enough that the first ep_rew_mean entries
                           # are in the log; check_convergence requires 3
                           # entries before considering)

# Stage definitions.
# `red_pool` values must be subset of {scripted, rule, default} — train.py rejects 'learned'.
STAGE_PLANS = [
    dict(
        stage="S1",
        hard_cap=2_000_000,
        layouts_pool_slots=("C",),
        red_mode_pool=("scripted",),
        warmstart_from=None,
    ),
    dict(
        stage="S2",
        hard_cap=2_000_000,
        layouts_pool_slots=("C", "D"),
        red_mode_pool=("scripted",),
        warmstart_from="S1",
    ),
    dict(
        stage="S3",
        hard_cap=2_000_000,
        layouts_pool_slots=("C", "D"),
        # 2026-04-26: dropped "rule" from the pool. The first attempt at
        # ('scripted','scripted','rule') saturated the box because rule
        # RedAI spawns all 28 demo waves within the first 145s sim, so
        # the world ends up holding many simultaneous threats — each
        # env step becomes heavy. Combined with the parallel Red-trainee
        # job already running on the box (in ~/hackathon-stridsledning-red/,
        # also at n_envs=48), contention dropped fps from 400 → 36 and
        # iter 2 took 45 min. Scripted-only matches the S2 setup so the
        # warmstart chain stays consistent. Layouts C+D still differ
        # from S2 by sampling — already 50/50.
        red_mode_pool=("scripted",),
        warmstart_from="S2",
    ),
    dict(
        stage="S4",
        hard_cap=1_000_000,
        layouts_pool_slots=("C", "C", "D", "D", "E"),
        # Same scripted-only fallback as S3.
        red_mode_pool=("scripted",),
        warmstart_from="S3",
    ),
]


def _build_train_cli(
    *,
    run_name: str,
    total_steps: int,
    warmstart: Optional[Path],
    layouts_pool_slots: Sequence[str],
    red_mode_pool: Sequence[str],
) -> list:
    cli = [
        PYTHON, "-u", "-m", "rl.train",
        "--total-steps", str(total_steps),
        "--n-envs", str(COMMON_FLAGS["n_envs"]),
        "--n-steps", str(COMMON_FLAGS["n_steps"]),
        "--batch-size", str(COMMON_FLAGS["batch_size"]),
        "--n-epochs", str(COMMON_FLAGS["n_epochs"]),
        "--lr", str(COMMON_FLAGS["lr"]),
        "--gamma", str(COMMON_FLAGS["gamma"]),
        "--gae-lambda", str(COMMON_FLAGS["gae_lambda"]),
        "--ent-coef", str(COMMON_FLAGS["ent_coef"]),
        "--clip-range", str(COMMON_FLAGS["clip_range"]),
        "--episode-time-limit", str(COMMON_FLAGS["episode_time_limit"]),
        "--blue-budget", str(COMMON_FLAGS["blue_budget"]),
        "--red-budget", str(COMMON_FLAGS["red_budget"]),
        "--device", COMMON_FLAGS["device"],
        "--save-every", str(COMMON_FLAGS["save_every"]),
        "--run-name", run_name,
        "--layouts-pool", str(LAYOUTS_POOL_PATH),
        "--layouts-pool-slots", *layouts_pool_slots,
        "--red-mode-pool", *red_mode_pool,
    ]
    if warmstart is not None:
        cli += ["--warmstart", str(warmstart)]
    return cli


def _check_convergence(log_path: Path) -> str:
    """Returns 'converged' | 'continue' | 'no_data'."""
    if not log_path.exists():
        return "no_data"
    res = subprocess.run(
        [PYTHON, str(CHECK_CONV), str(log_path)],
        cwd=str(REPO_BACKEND),
        capture_output=True,
        text=True,
    )
    if res.returncode == 0:
        return "converged"
    if res.returncode == 1:
        return "continue"
    return "no_data"


def _convergence_watchdog(
    proc: subprocess.Popen,
    log_path: Path,
    stage: str,
    *,
    poll_s: int = WATCHDOG_POLL_S,
    min_wall_s: int = WATCHDOG_MIN_WALL_S,
    stop_evt: threading.Event,
) -> None:
    """Watchdog thread: poll log, SIGINT train.py on convergence.

    Holds off for `min_wall_s` to avoid premature triggering before any
    ep_rew_mean entries have appeared.
    """
    started = time.time()
    last_count = 0
    while not stop_evt.is_set():
        if proc.poll() is not None:
            return
        time.sleep(poll_s)
        if proc.poll() is not None:
            return
        elapsed = time.time() - started
        if elapsed < min_wall_s:
            continue
        # Status report
        try:
            with log_path.open("rb") as f:
                count = f.read().count(b"ep_rew_mean")
        except FileNotFoundError:
            count = 0
        if count > last_count:
            print(f"[watchdog/{stage}] ep_rew_mean count={count} (wall={elapsed/60:.1f} min)",
                  flush=True)
            last_count = count
        verdict = _check_convergence(log_path)
        if verdict == "converged":
            print(f"[watchdog/{stage}] CONVERGED at wall={elapsed/60:.1f} min, "
                  f"sending SIGINT to train.py (pid={proc.pid})", flush=True)
            try:
                proc.send_signal(signal.SIGINT)
            except ProcessLookupError:
                pass
            return


def run_stage(plan: dict, *, push: bool, resume: bool) -> dict:
    stage = plan["stage"]
    final_path = STAGES_DIR / f"{stage}_final.zip"
    log_path = STAGES_DIR / f"{stage}_training.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    if resume and final_path.exists():
        print(f"[{stage}] final exists → skipping (resume mode)")
        return dict(stage=stage, accumulated=None, converged="skip")

    if plan["warmstart_from"] is None:
        warmstart = None
    else:
        warmstart = STAGES_DIR / f"{plan['warmstart_from']}_final.zip"
        if not warmstart.exists():
            raise RuntimeError(f"missing warmstart {warmstart} for stage {stage}")

    run_name = f"blue_megamodel_{stage}"
    run_dir = REPO_BACKEND / "rl" / "runs" / run_name
    cli = _build_train_cli(
        run_name=run_name,
        total_steps=plan["hard_cap"],
        warmstart=warmstart,
        layouts_pool_slots=plan["layouts_pool_slots"],
        red_mode_pool=plan["red_mode_pool"],
    )

    print(f"\n[{stage}] launching: {' '.join(cli)}", flush=True)
    print(f"[{stage}] log -> {log_path}", flush=True)
    print(f"[{stage}] hard_cap={plan['hard_cap']:,} steps", flush=True)

    t_stage_start = time.time()
    stop_evt = threading.Event()
    with open(log_path, "ab", buffering=0) as logf:
        sep = (
            f"\n{'='*78}\n"
            f"=== STAGE {stage}\n"
            f"=== run_name={run_name} warmstart={warmstart}\n"
            f"=== hard_cap={plan['hard_cap']}\n"
            f"=== started at {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n"
            f"{'='*78}\n"
        ).encode()
        logf.write(sep)
        proc = subprocess.Popen(
            cli, cwd=str(REPO_BACKEND), stdout=logf, stderr=subprocess.STDOUT
        )

        # Start watchdog thread
        watchdog = threading.Thread(
            target=_convergence_watchdog,
            args=(proc, log_path, stage),
            kwargs=dict(stop_evt=stop_evt),
            daemon=True,
        )
        watchdog.start()

        try:
            rc = proc.wait()
        except KeyboardInterrupt:
            print(f"[{stage}] driver received KeyboardInterrupt — propagating",
                  flush=True)
            proc.send_signal(signal.SIGINT)
            try:
                rc = proc.wait(timeout=300)
            except subprocess.TimeoutExpired:
                proc.kill()
                rc = -9
            stop_evt.set()
            raise

        stop_evt.set()
        watchdog.join(timeout=10)

    if rc not in (0, -2, 130):
        # 0 = clean exit; -2/130 = SIGINT (graceful shutdown via train.py)
        raise RuntimeError(f"train.py exited with code {rc}; see {log_path}")

    elapsed_min = (time.time() - t_stage_start) / 60.0
    src_model = run_dir / "model.zip"
    if not src_model.exists():
        raise RuntimeError(f"expected {src_model} after train.py; not found")
    shutil.copy(src_model, final_path)
    print(f"[{stage}] final → {final_path} (wall {elapsed_min:.1f} min)", flush=True)

    # Detect convergence vs hard-cap
    verdict = _check_convergence(log_path)
    converged = (verdict == "converged")

    msg = (
        f"feat(rl): megamodel {stage} "
        f"{'converged' if converged else 'hardcap'} "
        f"(wall={elapsed_min:.0f} min)"
    )
    _git_push(msg, push)

    return dict(
        stage=stage,
        wall_min=elapsed_min,
        converged=converged,
        final=str(final_path),
    )


def _git_push(message: str, push: bool) -> None:
    print(f"\n[git] commit + push: {message}", flush=True)
    repo_root = REPO_BACKEND.parent.parent
    subprocess.run(
        ["git", "add",
         "team-missile-intercept/backend/rl/runs/blue_local/blue_megamodel/",
         "team-missile-intercept/backend/rl/env.py",
         "team-missile-intercept/backend/scripts/check_convergence.py",
         "team-missile-intercept/backend/scripts/run_megamodel.py",
         "team-missile-intercept/backend/scripts/run_red_trainee.py",
         "team-missile-intercept/progress/TRAIN_MEGAMODEL_REPORT.md",
         ],
        cwd=str(repo_root), check=False,
    )
    rc = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=str(repo_root), check=False,
    ).returncode
    if rc != 0:
        print("[git] commit returned non-zero (likely 'nothing to commit')")
        return
    if push:
        subprocess.run(
            ["git", "push", "origin", "train-megamodel-cap72"],
            cwd=str(repo_root), check=False,
        )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", nargs="*", default=None)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--no-push", action="store_true")
    args = ap.parse_args()

    STAGES_DIR.mkdir(parents=True, exist_ok=True)

    selected = STAGE_PLANS
    if args.stages:
        wanted = {s.upper() for s in args.stages}
        selected = [p for p in STAGE_PLANS if p["stage"] in wanted]
        if not selected:
            valid = [p["stage"] for p in STAGE_PLANS]
            print(f"no stages matched {args.stages}; valid: {valid}")
            return 2

    t0 = time.time()
    results = []
    for plan in selected:
        elapsed = time.time() - t0
        budget_remaining = 8 * 3600 - elapsed
        if plan["stage"] == "S4" and budget_remaining < 5400:
            print(f"[S4] skipped — only {budget_remaining/60:.1f} min remaining; want ≥ 90")
            s3_final = STAGES_DIR / "S3_final.zip"
            mega_final = RUN_BASE / "model.zip"
            if s3_final.exists():
                shutil.copy(s3_final, mega_final)
                print(f"[finalize] copied S3 → {mega_final}")
            results.append(dict(stage="S4", skipped="time"))
            break

        res = run_stage(plan, push=not args.no_push, resume=args.resume)
        results.append(res)

    final_stage_zip = None
    for plan in reversed(selected):
        candidate = STAGES_DIR / f"{plan['stage']}_final.zip"
        if candidate.exists():
            final_stage_zip = candidate
            break
    if final_stage_zip is not None:
        mega_final = RUN_BASE / "model.zip"
        shutil.copy(final_stage_zip, mega_final)
        print(f"\n[finalize] {final_stage_zip.name} → {mega_final}")

    print("\n=== megamodel summary ===")
    for r in results:
        print(f"  {r}")
    print(f"total wall: {(time.time()-t0)/60:.1f} min")
    return 0


if __name__ == "__main__":
    sys.exit(main())
