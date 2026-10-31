#!/bin/bash
#SBATCH --job-name=la_uma_md
#SBATCH --account=m4292
#SBATCH --constraint=gpu
#SBATCH --qos=regular
#SBATCH --time=24:00:00
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --gpus-per-node=4
#SBATCH --cpus-per-task=64
#SBATCH --output=la_uma_md_%j.out
#SBATCH --error=la_uma_md_%j.err

# Submit from $SCRATCH/SolvationNet/deep-shell/
#
#   sbatch -A m4292 -q overrun --requeue -t 06:00:00 perlmutter/la_uma_md.sbatch
#
# QOS stays regular. The gpu_* names in `sacctmgr show assoc` (gpu_regular,
# gpu_debug) are internal, derived by NERSC's submit filter from regular plus
# --constraint=gpu. Requesting one by name is rejected with "Job request does
# not match any supported policy".
#
# The m4292_g GPU allocation is spent, 15746 of 15746 node-hours as of
# 2026-09-21. A GPU job charges that allocation whichever repo it names, so
# normal submission bounces with "your balance is 0.00 node hours". The overrun
# queue runs at zero charge instead, at lowest priority and preemptible. The
# --resume flag below and 10,000 step checkpoints make that survivable.
#
# Keep the walltime short. A 24 h request pended 17 days and never started,
# while every 30 min job reached a node within hours. At 13.9 steps/s a 6 h job
# covers 300,000 steps and loses at most 12 min to preemption.
#
# 10 ns at 1 fs is 10M UMA calls per system, about 200 GPU-hours measured on job
# 60508816. Resubmit until all five systems report DONE.

set -uo pipefail

module load python
module load cudatoolkit

# Created once by perlmutter/setup_env.sh. `source activate` rather than
# `conda activate`, which needs a shell hook that batch jobs do not get.
source activate solvationnet || { echo "ERROR: could not activate 'solvationnet'"; exit 1; }
python -c "import fairchem, torch; assert torch.cuda.is_available()" \
    || { echo "ERROR: fairchem/CUDA unavailable in this environment"; exit 1; }
HF_HUB_OFFLINE=1 python -c "
from fairchem.core import pretrained_mlip
p = pretrained_mlip.get_predict_unit('uma-s-1p2', device='cpu')
assert hasattr(p.model, 'module')
" || { echo "ERROR: cannot load uma-s-1p2 from cache with HF_HUB_OFFLINE=1"; exit 1; }

WORK="${SLURM_SUBMIT_DIR:-$SCRATCH/SolvationNet/deep-shell}"
cd "$WORK" || exit 1

echo "=== La³⁺ solvation MD ==="
echo "Job:  $SLURM_JOB_ID"
echo "Node: $(hostname)"
echo "Date: $(date)"
echo "Dir:  $(pwd)"
echo ""
nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader
echo ""

ALL_SYSTEMS=(F OH NO3 CO3 PO4)
NGPU=4

mkdir -p results
for sys in "${ALL_SYSTEMS[@]}"; do
    mkdir -p "results/La3+_${sys}"
done

# One system per GPU, never two. Measured on job 60508816, a system with a GPU
# to itself ran at 13.9 steps/s, 22,000 steps in 30 min, while F and PO4 sharing
# GPU 0 managed about 5 steps/s each. Sharing works, but one card serving two
# systems gives about 10 steps/s against 13.9 dedicated, so four systems on four
# GPUs beats five: 55.6 steps/s aggregate against 51.7.
#
# Five systems do not fit on four GPUs, so each job takes the NGPU systems that
# are furthest behind. Resubmitting repeatedly advances all five evenly, because
# whichever sat out last time is now the laggard.
PENDING=()
for sys in "${ALL_SYSTEMS[@]}"; do
    [ -f "results/La3+_${sys}/final.xyz" ] && continue      # already finished
    step=$(tail -n 1 "results/La3+_${sys}/md.log" 2>/dev/null | awk '{print $1+0}')
    PENDING+=("${step:-0} $sys")
done

SYSTEMS=()
while read -r _ sys; do
    [ -n "$sys" ] && SYSTEMS+=("$sys")
done < <(printf '%s\n' "${PENDING[@]}" | sort -n | head -n "$NGPU")

if [ "${#SYSTEMS[@]}" -eq 0 ]; then
    echo "All systems report final.xyz, nothing to run."
    exit 0
fi
echo "Least-advanced systems this pass: ${SYSTEMS[*]}"

# The UMA weights are already cached under ~/.cache/fairchem, but
# hf_hub_download still takes an flock on that directory before it will hand
# back a path, and flock is unsupported on global homes from the compute nodes:
#   OSError: [Errno 524] Unknown error 524
# Five processes grabbing that lock at once is what killed job 60059899 after
# 1m57s, before a single model had loaded. Offline mode reads the cache
# directly and never reaches the locking path.
export HF_HUB_OFFLINE=1

echo "Launching ${#SYSTEMS[@]} systems across $NGPU GPUs"
PIDS=()
NAMES=()
for i in "${!SYSTEMS[@]}"; do
    sys="${SYSTEMS[$i]}"
    gpu=$i                     # one system per GPU; SYSTEMS is capped at NGPU
    echo "  GPU $gpu → La3+_${sys}"
    CUDA_VISIBLE_DEVICES=$gpu python run_uma_md.py \
        "droplets/La3+_${sys}_droplet.xyz" \
        -o "results/La3+_${sys}/" \
        --steps 10000000 \
        --dt 1.0 \
        --temp 300.0 \
        --traj-interval 1000 \
        --resume \
        > "results/La3+_${sys}/slurm.log" 2>&1 &
    PIDS+=($!)
    NAMES+=("$sys")
    sleep 5   # don't let five processes read the same cache files in lockstep
done
echo ""

FAIL=0
for i in "${!PIDS[@]}"; do
    if ! wait "${PIDS[$i]}"; then
        echo "  La3+_${NAMES[$i]}: exited non-zero"
        FAIL=$((FAIL + 1))
    fi
done
echo "All runs returned ($(date)), failures: $FAIL"

echo ""
echo "=== Summary ==="
INCOMPLETE=0
for sys in "${ALL_SYSTEMS[@]}"; do
    dir="results/La3+_${sys}"
    if [ -f "$dir/final.xyz" ]; then
        echo "  La3+_${sys}:  DONE (final.xyz exists)"
    elif [ -f "$dir/checkpoint.pkl" ]; then
        step=$(tail -n 1 "$dir/md.log" 2>/dev/null | awk '{print $1}')
        echo "  La3+_${sys}:  PARTIAL (last logged step: ${step:-unknown}), resubmit to continue"
        INCOMPLETE=$((INCOMPLETE + 1))
    else
        echo "  La3+_${sys}:  FAILED (no output; see $dir/slurm.log)"
        INCOMPLETE=$((INCOMPLETE + 1))
    fi
done

if [ "$INCOMPLETE" -gt 0 ]; then
    echo ""
    echo "$INCOMPLETE system(s) incomplete. Resubmit: sbatch perlmutter/la_uma_md.sbatch"
fi

echo ""
echo "Finished: $(date)"

# To benchmark rather than spend an allocation, submit this script to the debug
# queue. Thirty minutes on four GPUs clears torch.compile warmup and prints
# throughput for every system:
#   sbatch -q debug -t 00:30:00 perlmutter/la_uma_md.sbatch
#   grep st/s results/La3+_*/slurm.log
# Then GPU-hours per system = 10000000 / st/s / 3600.

# clamped, since FAIL + a child status can wrap past 255 and read as success
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
