#!/usr/bin/env bash
# One-shot wrapper for Phase 5 eval: 3 matches per (layout, red)-cell,
# 2400 s cap. Picks the latest `blue_ppo_*_steps.zip` in
# rl/runs/blue_aoe_long/ckpt/ automatically. Writes outputs to the
# backend cwd as `blue_aoe_long_final_eval.{json,md}`.
set -euo pipefail

cd "$(dirname "$0")"

LATEST="$(ls -t rl/runs/blue_aoe_long/ckpt/blue_ppo_*_steps.zip | head -1)"
if [ -z "$LATEST" ]; then
  echo "No checkpoint found in rl/runs/blue_aoe_long/ckpt/" >&2
  exit 2
fi

echo "[run_final_eval] using $LATEST"

python -u -m rl.per_layout_eval \
  --blue "$LATEST" \
  --red scripted default \
  --layouts C D current \
  --matches 3 \
  --episode-time-limit 2400 \
  --blue-budget 200000000 \
  --red-budget 150000000 \
  --output blue_aoe_long_final_eval
