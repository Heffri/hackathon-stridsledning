"""Phase 2: train one Red trainee against the just-trained Blue megamodel.

Conditional — only run if ≥ 1.5h of the 8h budget remains. Saves to
``rl/runs/red_local/red_trainee_megamodel/`` and pushes a commit.

Usage from backend/:

    python -m scripts.run_red_trainee --total-steps 5000000

Reads the Blue opponent from ``rl/runs/blue_local/blue_megamodel/model.zip``.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_BACKEND = Path(__file__).resolve().parent.parent
BLUE_MEGAMODEL = REPO_BACKEND / "rl/runs/blue_local/blue_megamodel/model.zip"
RED_RUN_DIR = REPO_BACKEND / "rl/runs/red_local/red_trainee_megamodel"
PYTHON = sys.executable


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--total-steps", type=int, default=5_000_000)
    ap.add_argument("--n-envs", type=int, default=48)
    ap.add_argument("--push", action="store_true",
                    help="git push after training")
    args = ap.parse_args()

    if not BLUE_MEGAMODEL.exists():
        print(f"missing Blue megamodel at {BLUE_MEGAMODEL}", file=sys.stderr)
        return 2

    RED_RUN_DIR.mkdir(parents=True, exist_ok=True)
    log_path = RED_RUN_DIR / "training.log"

    cli = [
        PYTHON, "-u", "-m", "rl.red_train",
        "--total-steps", str(args.total_steps),
        "--n-envs", str(args.n_envs),
        "--n-steps", "1024",
        "--batch-size", "256",
        "--n-epochs", "4",
        "--lr", "3e-4",
        "--gamma", "0.995",
        "--gae-lambda", "0.95",
        "--ent-coef", "0.01",
        "--clip-range", "0.2",
        "--episode-time-limit", "5000.0",
        "--device", "cpu",
        "--save-every", "500000",
        "--run-name", "red_trainee_megamodel",
        "--blue-opponent", str(BLUE_MEGAMODEL),
    ]
    print("[red] launching:", " ".join(cli))
    print(f"[red] log -> {log_path}")
    with open(log_path, "ab", buffering=0) as logf:
        proc = subprocess.Popen(
            cli, cwd=str(REPO_BACKEND), stdout=logf, stderr=subprocess.STDOUT,
        )
        rc = proc.wait()
    print(f"[red] train exited with code {rc}")

    # Promote the run-dir model into the canonical red_trainee_megamodel slot.
    train_run_dir = REPO_BACKEND / "rl/runs/red_trainee_megamodel"
    src = train_run_dir / "model.zip"
    dst = RED_RUN_DIR / "model.zip"
    if src.exists():
        shutil.copy(src, dst)
        print(f"[red] copied {src} -> {dst}")
    else:
        print(f"[red] WARNING: no model.zip at {src}; trainee may have failed")
        return rc or 2

    if args.push:
        subprocess.run(
            ["git", "add", "team-missile-intercept/backend/rl/runs/red_local/red_trainee_megamodel/"],
            cwd=str(REPO_BACKEND.parent.parent), check=False,
        )
        subprocess.run(
            ["git", "commit", "-m",
             f"feat(rl): red trainee trained against blue megamodel ({args.total_steps} steps)"],
            cwd=str(REPO_BACKEND.parent.parent), check=False,
        )
        subprocess.run(
            ["git", "push", "origin", "train-megamodel-cap72"],
            cwd=str(REPO_BACKEND.parent.parent), check=False,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
