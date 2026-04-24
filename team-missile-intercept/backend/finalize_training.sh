#!/usr/bin/env bash
# End-of-run wrapper invoked once `blue_aoe_long` training has
# produced enough checkpoints. Does the Phase 5 + Phase 6 deliverable
# choreography so it's one command to run after stopping training.
#
# 1. Pick the latest ckpt and copy it to
#    rl/runs/blue_local/blue_aoe_long/model.zip (worktree).
# 2. Copy that model.zip to the MAIN tree at the same relative path.
# 3. Run per_layout_eval with 3 matches per (layout, red)-cell.
# 4. Move eval outputs to the canonical name in backend/.
# 5. Print summary.
set -euo pipefail

cd "$(dirname "$0")"

SRC_DIR="rl/runs/blue_aoe_long/ckpt"
DST_DIR_WORKTREE="rl/runs/blue_local/blue_aoe_long"
DST_DIR_MAIN="C:/Users/xingy/Documents/github/hackathon-stridsledning/team-missile-intercept/backend/rl/runs/blue_local/blue_aoe_long"

LATEST="$(ls -t "$SRC_DIR"/blue_ppo_*_steps.zip | head -1)"
if [ -z "$LATEST" ]; then
  echo "[finalize] no checkpoint in $SRC_DIR" >&2
  exit 2
fi
echo "[finalize] using $LATEST"

mkdir -p "$DST_DIR_WORKTREE" "$DST_DIR_MAIN"
cp "$LATEST" "$DST_DIR_WORKTREE/model.zip"
cp "$LATEST" "$DST_DIR_MAIN/model.zip"
echo "[finalize] copied to $DST_DIR_WORKTREE/model.zip and $DST_DIR_MAIN/model.zip"

# Run eval. 3 matches x 3 layouts x 2 reds = 18 matches.
python -u -m rl.per_layout_eval \
  --blue "$DST_DIR_WORKTREE/model.zip" \
  --red scripted default \
  --layouts C D current \
  --matches 3 \
  --episode-time-limit 2400 \
  --blue-budget 200000000 \
  --red-budget 150000000 \
  --output blue_aoe_long_final_eval

echo "[finalize] done."
ls -la blue_aoe_long_final_eval.{json,md} 2>&1 | head
