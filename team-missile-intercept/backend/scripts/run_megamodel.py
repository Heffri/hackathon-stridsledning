"""Blue megamodel curriculum driver (cap 72/32/128).

Sequential stages S1 → S2 → S3 → S4. Each stage trains in 200k-step
increments, checking convergence between increments. Stage advances on
convergence or HARD_CAP. After every stage, model copied to
``stages/<STAGE>_final.zip`` and pushed to GitHub.

Run from backend/ root:

    python -m scripts.run_megamodel             # full pipeline
    python -m scripts.run_megamodel --stages S1 # one stage only
    python -m scripts.run_megamodel --resume    # skip stages whose final.zip exists
    python -m scripts.run_megamodel --no-push   # don't push between stages

Wall budget: 8 h. Phase-2 (Red trainee) is launched separately by run_red_trainee.py.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Sequence

REPO_BACKEND = Path(__file__).resolve().parent.parent          # .../backend
RUN_BASE = REPO_BACKEND / "rl" / "runs" / "blue_local" / "blue_megamodel"
STAGES_DIR = RUN_BASE / "stages"
SCRIPTS_DIR = REPO_BACKEND / "scripts"
CHECK_CONV = SCRIPTS_DIR / "check_convergence.py"
PYTHON = sys.executable

# Common training flags shared across stages (per spec).
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

INCREMENT = 200_000  # train this many steps per chunk
LAYOUTS_POOL_PATH = REPO_BACKEND / "rl" / "top3_layouts_CD.json"

# Stage definitions.
# `red_pool` values must be subset of {scripted, rule, default} — train.py rejects 'learned'.
# Note: we deliberately fall back to scripted+rule for S3 (no learned-Red opp)
# because train.py's --red-mode-pool argparse choices don't include 'learned'
# and the prompt forbids editing train.py.
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
        # Fallback per prompt: scripted scripted rule (drop learned).
        red_mode_pool=("scripted", "scripted", "rule"),
        warmstart_from="S2",
    ),
    dict(
        stage="S4",
        hard_cap=1_000_000,
        layouts_pool_slots=("C", "C", "D", "D", "E"),
        red_mode_pool=("scripted", "scripted", "rule"),
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
        PYTHON, "-m", "rl.train",
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
    sys.stdout.write(res.stdout)
    sys.stderr.write(res.stderr)
    if res.returncode == 0:
        return "converged"
    if res.returncode == 1:
        return "continue"
    return "no_data"


def _run_increment(
    *,
    stage: str,
    inc_idx: int,
    accumulated_steps_before: int,
    warmstart: Optional[Path],
    layouts_pool_slots: Sequence[str],
    red_mode_pool: Sequence[str],
    consolidated_log: Path,
) -> Path:
    """Train a single 200k increment. Returns path to its model.zip."""
    run_name = f"blue_megamodel_{stage}_inc_{accumulated_steps_before}"
    run_dir = REPO_BACKEND / "rl" / "runs" / run_name
    cli = _build_train_cli(
        run_name=run_name,
        total_steps=INCREMENT,
        warmstart=warmstart,
        layouts_pool_slots=layouts_pool_slots,
        red_mode_pool=red_mode_pool,
    )
    print(f"\n[{stage}/inc{inc_idx}] launching: {' '.join(cli)}", flush=True)
    print(f"[{stage}/inc{inc_idx}] log -> {consolidated_log}", flush=True)

    consolidated_log.parent.mkdir(parents=True, exist_ok=True)
    with open(consolidated_log, "ab", buffering=0) as logf:
        sep = (
            f"\n{'='*78}\n"
            f"=== STAGE {stage} INCREMENT {inc_idx} "
            f"(accumulated_before={accumulated_steps_before}) ===\n"
            f"=== run_name={run_name} warmstart={warmstart} ===\n"
            f"{'='*78}\n"
        ).encode()
        logf.write(sep)
        proc = subprocess.Popen(
            cli, cwd=str(REPO_BACKEND), stdout=logf, stderr=subprocess.STDOUT
        )
        rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"train.py exited with code {rc}; see {consolidated_log}")

    model = run_dir / "model.zip"
    if not model.exists():
        raise RuntimeError(f"expected {model} after train.py; not found")
    return model


def _git_push(message: str, push: bool) -> None:
    print(f"\n[git] commit + push: {message[:60]}...", flush=True)
    subprocess.run(
        ["git", "add",
         "team-missile-intercept/backend/rl/runs/blue_local/blue_megamodel/",
         "team-missile-intercept/backend/rl/env.py",
         "team-missile-intercept/backend/scripts/check_convergence.py",
         "team-missile-intercept/backend/scripts/run_megamodel.py",
         ],
        cwd=str(REPO_BACKEND.parent.parent), check=False,
    )
    rc = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=str(REPO_BACKEND.parent.parent), check=False,
    ).returncode
    if rc != 0:
        print("[git] commit returned non-zero (likely 'nothing to commit')")
        return
    if push:
        subprocess.run(
            ["git", "push", "origin", "train-megamodel-cap72"],
            cwd=str(REPO_BACKEND.parent.parent), check=False,
        )


def run_stage(plan: dict, *, push: bool, resume: bool) -> dict:
    stage = plan["stage"]
    final_path = STAGES_DIR / f"{stage}_final.zip"
    consolidated_log = STAGES_DIR / f"{stage}_training.log"
    consolidated_log.parent.mkdir(parents=True, exist_ok=True)

    if resume and final_path.exists():
        print(f"[{stage}] final exists → skipping (resume mode)")
        return dict(stage=stage, accumulated=None, converged="skip")

    # Resolve warmstart path
    if plan["warmstart_from"] is None:
        warmstart = None
    else:
        warmstart = STAGES_DIR / f"{plan['warmstart_from']}_final.zip"
        if not warmstart.exists():
            raise RuntimeError(f"missing warmstart {warmstart} for stage {stage}")

    accumulated = 0
    inc_idx = 0
    converged = False
    last_model = warmstart
    t_stage_start = time.time()

    while accumulated < plan["hard_cap"]:
        last_model = _run_increment(
            stage=stage,
            inc_idx=inc_idx,
            accumulated_steps_before=accumulated,
            warmstart=last_model,
            layouts_pool_slots=plan["layouts_pool_slots"],
            red_mode_pool=plan["red_mode_pool"],
            consolidated_log=consolidated_log,
        )
        accumulated += INCREMENT
        inc_idx += 1
        elapsed = (time.time() - t_stage_start) / 60.0
        print(f"[{stage}] +{INCREMENT} steps → accumulated={accumulated}; "
              f"stage wall {elapsed:.1f} min", flush=True)

        verdict = _check_convergence(consolidated_log)
        if verdict == "converged":
            converged = True
            print(f"[{stage}] CONVERGED at {accumulated} steps", flush=True)
            break
        elif verdict == "no_data":
            print(f"[{stage}] convergence checker had no parsable data — continuing")

    if not converged:
        print(f"[{stage}] HARD_CAP reached ({accumulated} steps) without convergence")

    shutil.copy(last_model, final_path)
    print(f"[{stage}] final model → {final_path}", flush=True)
    if last_model != final_path:
        # Save a small fingerprint so we know which increment was last
        try:
            (STAGES_DIR / f"{stage}_final.source.txt").write_text(
                f"last_increment_model: {last_model}\n"
                f"accumulated_steps: {accumulated}\n"
                f"converged: {converged}\n"
            )
        except Exception:
            pass

    msg = (
        f"feat(rl): megamodel {stage} "
        f"{'converged' if converged else 'hardcap'} at {accumulated} steps"
    )
    _git_push(msg, push)
    return dict(stage=stage, accumulated=accumulated, converged=converged)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", nargs="*", default=None,
                    help="Subset of stages to run (e.g. --stages S1 S2). Default = all.")
    ap.add_argument("--resume", action="store_true",
                    help="Skip stages whose final.zip already exists")
    ap.add_argument("--no-push", action="store_true",
                    help="Don't git push between stages (still commits locally)")
    args = ap.parse_args()

    STAGES_DIR.mkdir(parents=True, exist_ok=True)

    selected = STAGE_PLANS
    if args.stages:
        wanted = {s.upper() for s in args.stages}
        selected = [p for p in STAGE_PLANS if p["stage"] in wanted]
        if not selected:
            print(f"no stages matched {args.stages}; valid: {[p['stage'] for p in STAGE_PLANS]}")
            return 2

    t0 = time.time()
    results = []
    for plan in selected:
        # 8h budget gate
        elapsed = time.time() - t0
        budget_remaining = 8 * 3600 - elapsed
        # S4 has special skip rule per spec: skip if < 1.5h remaining
        if plan["stage"] == "S4" and budget_remaining < 5400:
            print(f"[S4] skipped — only {budget_remaining/60:.1f} min remaining; want ≥ 90")
            # Promote S3 final to be the megamodel final.
            s3_final = STAGES_DIR / "S3_final.zip"
            mega_final = RUN_BASE / "model.zip"
            if s3_final.exists():
                shutil.copy(s3_final, mega_final)
                print(f"[finalize] copied S3 to {mega_final}")
            results.append(dict(stage="S4", skipped="time"))
            break

        res = run_stage(plan, push=not args.no_push, resume=args.resume)
        results.append(res)

    # Promote last stage's final to model.zip
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
