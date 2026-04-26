#!/usr/bin/env bash
# Drives the Red trainee curriculum end-to-end:
#   R1a (cold, rule Blue, 1.5M)
# → R1b (warmstart R1a, B_shaped, 1M)
# → R1c (warmstart R1b, V4, 1M)
# → R1d (warmstart R1c, Boyu V2a, 1M)
# → R1e (warmstart R1d, megamodel S3, 0.5M)  if S3 ready
#
# After each stage's runner finishes (creates stages/${STAGE}_final.zip),
# this script commits + pushes, then launches the next stage. If the
# orchestrator (Claude session) dies, this script keeps going.
#
# Usage: nohup ./scripts/curriculum_driver.sh start_from R1a >curriculum.log 2>&1 &
set -uo pipefail

RED_REPO=/home/chen/hackathon-stridsledning-red
RED_BACKEND=$RED_REPO/team-missile-intercept/backend
RED_RUN_DIR=$RED_BACKEND/rl/runs/red_local/red_trainee_parallel
SCRIPTS=$RED_BACKEND/scripts
BLUE_REPO=/home/chen/hackathon-stridsledning
BLUE_BACKEND=$BLUE_REPO/team-missile-intercept/backend

# Blue model paths (all under the Red worktree as they're tracked).
B_SHAPED=$RED_BACKEND/rl/runs/blue_local/blue_aoe_aggressive_B_shaped/model.zip
B_V4=$RED_BACKEND/rl/runs/blue_reward_v4_finetune/model.zip
B_BOYU_V2A=$RED_BACKEND/rl/runs/boyu_modedlV2a/model.zip
# Megamodel S3 lives in Blue's worktree (not yet pushed when we start).
B_MEGA_S3=$BLUE_BACKEND/rl/runs/blue_local/blue_megamodel/stages/S3_final.zip

START_FROM="${1:-R1a}"

cd "$RED_REPO"

wait_for_runner() {
  local STAGE=$1
  local final="${RED_RUN_DIR}/stages/${STAGE}_final.zip"
  echo "[curriculum] waiting for ${final}"
  # Loop until file exists or stage runner exits with no file.
  while true; do
    if [ -f "$final" ]; then
      echo "[curriculum] ${final} found"
      return 0
    fi
    # If runner.log shows FAILED, abort.
    if grep -q "FAILED to locate any saved ckpt" "${RED_RUN_DIR}/${STAGE}_runner.log" 2>/dev/null; then
      echo "[curriculum] ${STAGE} FAILED — see runner log" >&2
      return 1
    fi
    sleep 30
  done
}

commit_and_push() {
  local STAGE=$1
  local CONVERGED=0
  if [ -f "${RED_RUN_DIR}/stages/${STAGE}_converged.txt" ]; then
    CONVERGED=$(cat "${RED_RUN_DIR}/stages/${STAGE}_converged.txt")
  fi
  cd "$RED_REPO"
  git add team-missile-intercept/backend/rl/runs/red_local/red_trainee_parallel/stages/${STAGE}_final.zip \
          team-missile-intercept/backend/rl/runs/red_local/red_trainee_parallel/stages/${STAGE}_converged.txt \
          team-missile-intercept/backend/rl/runs/red_local/red_trainee_parallel/${STAGE}_training.log \
          team-missile-intercept/backend/rl/runs/red_local/red_trainee_parallel/${STAGE}_runner.log \
          team-missile-intercept/backend/rl/runs/red_local/red_trainee_parallel/${STAGE}_launch_cmd.txt \
          2>/dev/null || true
  if git diff --staged --quiet; then
    echo "[curriculum] no changes to commit for ${STAGE}"
    return 0
  fi
  git commit -m "feat(rl): red trainee ${STAGE} done (converged=${CONVERGED})

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
  git push origin train-red-trainee-parallel || \
    echo "[curriculum] push failed for ${STAGE}; keep going" >&2
}

run_stage() {
  local STAGE=$1
  local CAP=$2
  local WARM=$3
  local BLUE=$4
  echo "[curriculum] launching ${STAGE} cap=${CAP} warm=${WARM:-(cold)} blue=${BLUE:-(rule)}"
  $SCRIPTS/launch_stage.sh "$STAGE" "$CAP" "$WARM" "$BLUE"
  wait_for_runner "$STAGE" || return 1
  commit_and_push "$STAGE"
}

# Stage list — only stages from START_FROM onward are run.
declare -a STAGES_ORDER=(R1a R1b R1c R1d R1e)
SKIP=1
for STAGE in "${STAGES_ORDER[@]}"; do
  if [ "$STAGE" = "$START_FROM" ]; then SKIP=0; fi
  if [ "$SKIP" = "1" ]; then continue; fi

  case "$STAGE" in
    R1a)
      # Skip launch if R1a already running OR R1a_final.zip exists.
      if [ -f "${RED_RUN_DIR}/stages/R1a_final.zip" ]; then
        echo "[curriculum] R1a already done"
      elif pgrep -f "rl.red_train.*R1a" > /dev/null 2>&1; then
        echo "[curriculum] R1a already in flight — waiting"
        wait_for_runner R1a || exit 1
        commit_and_push R1a
      else
        run_stage R1a 1500000 "" "" || exit 1
      fi
      ;;
    R1b)
      run_stage R1b 1000000 "${RED_RUN_DIR}/stages/R1a_final.zip" "$B_SHAPED" || exit 1
      ;;
    R1c)
      run_stage R1c 1000000 "${RED_RUN_DIR}/stages/R1b_final.zip" "$B_V4" || exit 1
      ;;
    R1d)
      run_stage R1d 1000000 "${RED_RUN_DIR}/stages/R1c_final.zip" "$B_BOYU_V2A" || exit 1
      ;;
    R1e)
      if [ -f "$B_MEGA_S3" ]; then
        run_stage R1e 500000 "${RED_RUN_DIR}/stages/R1d_final.zip" "$B_MEGA_S3" || exit 1
      else
        echo "[curriculum] megamodel S3 not ready (${B_MEGA_S3}) — skipping R1e"
      fi
      ;;
  esac
done

# Finalize: pick the last stage that produced a final, copy to model.zip.
LAST=""
for STAGE in R1e R1d R1c R1b R1a; do
  if [ -f "${RED_RUN_DIR}/stages/${STAGE}_final.zip" ]; then
    LAST=$STAGE
    break
  fi
done
if [ -n "$LAST" ]; then
  cp "${RED_RUN_DIR}/stages/${LAST}_final.zip" "${RED_RUN_DIR}/model.zip"
  echo "[curriculum] finalized ${LAST} → ${RED_RUN_DIR}/model.zip"
  cd "$RED_REPO"
  git add team-missile-intercept/backend/rl/runs/red_local/red_trainee_parallel/model.zip
  git diff --staged --quiet || git commit -m "feat(rl): red trainee final cumulative model (${LAST})

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
  git push origin train-red-trainee-parallel || \
    echo "[curriculum] final push failed" >&2
fi

echo "[curriculum] done"
