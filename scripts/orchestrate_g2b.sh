#!/usr/bin/env bash
# Wait for SS + WTQ base_traj to finish, then kick off:
#   1) tiny SS g2b pilot (N_ITER=1, N_TRAIN=4) to verify e2e
#   2) if pilot OK, full SS g2b run (10 iter, K=4)
#   3) tiny WTQ g2b pilot
#   4) if pilot OK, full WTQ g2b run
#
# Runs in background; final sentinel: results/orchestrator_done.flag
# Logs progress to logs/orchestrator.log

set -euo pipefail
cd /Users/unique/auto_research/Project/G2B-Skill
mkdir -p logs
exec >> logs/orchestrator.log 2>&1

echo "=== orchestrator started $(date) ==="

# Wait for both base_traj processes (poll for failure_ids.json + 'completed' line)
wait_for_base_traj() {
    local bench=$1
    local fid=results/base_trajectories/master_0_heldout_42/${bench}/failure_ids.json
    while [ ! -f "$fid" ]; do
        sleep 30
        echo "[$(date '+%H:%M:%S')] waiting for $bench base_traj..."
    done
    echo "[$(date '+%H:%M:%S')] $bench base_traj done"
}

wait_for_base_traj spreadsheet
wait_for_base_traj wtq

echo
echo "=== both base_traj complete; starting SS pilot $(date) ==="
N_ITER=1 N_TRAIN=4 BATCH_SIZE=4 K=4 BENCH=spreadsheet \
    bash scripts/g2b_train.sh > logs/g2b_pilot_ss.log 2>&1 || {
    echo "SS pilot failed; check logs/g2b_pilot_ss.log"; exit 1;
}
echo "[$(date '+%H:%M:%S')] SS pilot complete"

echo
echo "=== starting full SS run $(date) ==="
K=4 BENCH=spreadsheet \
    bash scripts/g2b_train.sh > logs/g2b_full_ss.log 2>&1 || {
    echo "SS full failed; check logs/g2b_full_ss.log";
}
echo "[$(date '+%H:%M:%S')] SS full complete"

echo
echo "=== starting WTQ pilot $(date) ==="
N_ITER=1 N_TRAIN=4 BATCH_SIZE=4 K=4 BENCH=wtq \
    bash scripts/g2b_train.sh > logs/g2b_pilot_wtq.log 2>&1 || {
    echo "WTQ pilot failed; check logs/g2b_pilot_wtq.log";
}
echo "[$(date '+%H:%M:%S')] WTQ pilot complete"

echo
echo "=== starting full WTQ run $(date) ==="
K=4 BENCH=wtq \
    bash scripts/g2b_train.sh > logs/g2b_full_wtq.log 2>&1 || {
    echo "WTQ full failed; check logs/g2b_full_wtq.log";
}
echo "[$(date '+%H:%M:%S')] WTQ full complete"

touch results/orchestrator_done.flag
echo "=== orchestrator done $(date) ==="
