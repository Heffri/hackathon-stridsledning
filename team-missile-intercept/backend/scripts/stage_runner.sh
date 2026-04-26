#!/usr/bin/env bash
# Stage runner: launches the training process from the supplied command
# (already running externally is the assumed shape — this script doesn't
# launch). It polls the supplied log for convergence at CHECK_INTERVAL,
# sends SIGINT when convergence detected, then copies the final ckpt to
# the stages dir and exits.
#
# Usage: stage_runner.sh STAGE PID LOG_PATH RUN_DIR STAGES_DIR
#   STAGE=R1a, PID=12345, LOG_PATH=...R1a_training.log,
#   RUN_DIR=...red_local/red_trainee_parallel/R1a,
#   STAGES_DIR=...red_local/red_trainee_parallel/stages
set -uo pipefail

STAGE="$1"
PID="$2"
LOG="$3"
RUN_DIR="$4"
STAGES_DIR="$5"

CHECK_INTERVAL="${CHECK_INTERVAL:-60}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONV_SCRIPT="${SCRIPT_DIR}/check_convergence.py"

CONVERGED=0
LAST_REW_COUNT=0
SAW_FIRST=""
START_TS=$(date +%s)

echo "[${STAGE}] watcher started; PID=${PID} log=${LOG}"

while kill -0 "$PID" 2>/dev/null; do
  sleep "$CHECK_INTERVAL"

  # Brief progress signal: count of ep_rew_mean lines so far.
  n_ep=$(grep -c "ep_rew_mean" "$LOG" 2>/dev/null || echo 0)
  if [ "$n_ep" != "$LAST_REW_COUNT" ]; then
    last_val=$(grep "ep_rew_mean" "$LOG" | tail -1 | sed -E 's/.*ep_rew_mean *\| *([-0-9.eE+]+).*/\1/' || echo "?")
    elapsed=$(( $(date +%s) - START_TS ))
    echo "[${STAGE}] elapsed=${elapsed}s ep_rew_count=${n_ep} last=${last_val}"
    LAST_REW_COUNT="$n_ep"
    SAW_FIRST=1
  fi

  if [ -n "$SAW_FIRST" ] && [ "$n_ep" -ge 3 ]; then
    if python3 "$CONV_SCRIPT" "$LOG"; then
      echo "[${STAGE}] convergence detected; sending SIGINT to PID ${PID}"
      kill -SIGINT "$PID"
      # Wait up to 120s for SB3 to save & exit cleanly
      for _ in $(seq 1 60); do
        if ! kill -0 "$PID" 2>/dev/null; then break; fi
        sleep 2
      done
      CONVERGED=1
      break
    fi
  fi
done

# Process exited (either we SIGINT'd or it hit HARD_CAP / errored).
# Locate the latest checkpoint to use as the stage final.
LATEST_CKPT=""
if [ -f "${RUN_DIR}/model.zip" ]; then
  LATEST_CKPT="${RUN_DIR}/model.zip"
fi
# Fall back to most-recent ckpt if model.zip missing or older than ckpts.
LATEST_FROM_CKPT=$(find "${RUN_DIR}/ckpt" -name "*.zip" 2>/dev/null \
                   | xargs -I{} stat -c '%Y {}' {} 2>/dev/null \
                   | sort -nr | head -1 | awk '{print $2}')
if [ -n "$LATEST_FROM_CKPT" ] && [ -f "$LATEST_FROM_CKPT" ]; then
  if [ -z "$LATEST_CKPT" ] || [ "$LATEST_FROM_CKPT" -nt "$LATEST_CKPT" ]; then
    LATEST_CKPT="$LATEST_FROM_CKPT"
  fi
fi

if [ -z "$LATEST_CKPT" ] || [ ! -f "$LATEST_CKPT" ]; then
  echo "[${STAGE}] FAILED to locate any saved ckpt" >&2
  exit 1
fi

mkdir -p "$STAGES_DIR"
DST="${STAGES_DIR}/${STAGE}_final.zip"
cp "$LATEST_CKPT" "$DST"
echo "[${STAGE}] saved final ckpt: ${DST} (from ${LATEST_CKPT}, converged=${CONVERGED})"

# Mark convergence status in a sidecar so subsequent stages can read it.
echo "$CONVERGED" > "${STAGES_DIR}/${STAGE}_converged.txt"

exit 0
