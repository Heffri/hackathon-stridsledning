#!/usr/bin/env bash
# Launch a Red trainee stage in tmux, then start the convergence runner.
#
# Usage: launch_stage.sh STAGE HARD_CAP [WARMSTART_PATH] [BLUE_POLICY_PATH]
#   STAGE        — e.g. R1b
#   HARD_CAP     — total-steps, e.g. 1000000
#   WARMSTART_PATH — optional; absolute path to .zip warmstart (use "" for cold)
#   BLUE_POLICY_PATH — optional; absolute path to learned Blue .zip (use "" for rule)
set -euo pipefail

STAGE="$1"
HARD_CAP="$2"
WARMSTART="${3:-}"
BLUE_POLICY="${4:-}"

cd /home/chen/hackathon-stridsledning-red/team-missile-intercept/backend
RED_RUN_DIR="rl/runs/red_local/red_trainee_parallel"
mkdir -p "${RED_RUN_DIR}/stages"

# Build training command.
EXTRA_ARGS=""
if [ -n "$WARMSTART" ]; then
  EXTRA_ARGS+=" --warmstart $WARMSTART"
fi
if [ -n "$BLUE_POLICY" ]; then
  EXTRA_ARGS+=" --blue-opponent $BLUE_POLICY"
fi

LOG="${RED_RUN_DIR}/${STAGE}_training.log"
LAUNCH_CMD="cd /home/chen/hackathon-stridsledning-red/team-missile-intercept/backend && \
source .venv/bin/activate && \
BLUE_BUDGET_START_OVERRIDE=200000000 RED_BUDGET_START_OVERRIDE=150000000 \
python -u -m rl.red_train \
  --total-steps $HARD_CAP \
  --n-envs 48 \
  --n-steps 1024 \
  --batch-size 256 \
  --n-epochs 4 \
  --lr 3e-4 \
  --gamma 0.995 \
  --gae-lambda 0.95 \
  --ent-coef 0.01 \
  --clip-range 0.2 \
  --episode-time-limit 5000.0 \
  --device cpu \
  --save-every 200000 \
  --run-name red_local/red_trainee_parallel/${STAGE} \
  $EXTRA_ARGS \
  > ${LOG} 2>&1"

# Save the launch command for transparency
cat > ${RED_RUN_DIR}/${STAGE}_launch_cmd.txt <<EOF
$LAUNCH_CMD
EOF

# Spawn in a fresh tmux session so it survives.
SESSION="red_train_${STAGE}"
tmux kill-session -t "$SESSION" 2>/dev/null || true
tmux new-session -d -s "$SESSION" "bash -c '$LAUNCH_CMD'"

echo "[${STAGE}] launched in tmux ${SESSION}; hard cap=${HARD_CAP}"
echo "[${STAGE}] log: ${LOG}"

# Wait a moment for python to spawn (the bash wrapper takes time to init).
for _ in $(seq 1 20); do
  PARENT=$(pgrep -f "bash -c.*red_train.*${STAGE}" | head -1)
  if [ -n "$PARENT" ]; then
    PYPID=$(pgrep --parent "$PARENT" | head -1)
    if [ -n "$PYPID" ]; then
      break
    fi
  fi
  sleep 1
done

if [ -z "${PYPID:-}" ]; then
  echo "[${STAGE}] FAILED to find python PID after spawn" >&2
  exit 1
fi

echo "[${STAGE}] python PID: ${PYPID}"

# Spawn the convergence runner. Logs to ${STAGE}_runner.log so we can audit.
nohup /home/chen/hackathon-stridsledning-red/team-missile-intercept/backend/scripts/stage_runner.sh \
  ${STAGE} ${PYPID} \
  ${RED_RUN_DIR}/${STAGE}_training.log \
  ${RED_RUN_DIR}/${STAGE} \
  ${RED_RUN_DIR}/stages \
  > ${RED_RUN_DIR}/${STAGE}_runner.log 2>&1 &

disown
echo "[${STAGE}] runner started; expect ${RED_RUN_DIR}/stages/${STAGE}_final.zip when done"
