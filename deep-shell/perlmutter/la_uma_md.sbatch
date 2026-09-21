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

# Charged to m4292, not m4292_g, per PI instruction. Note that m4292_g is the
# repo that has exhausted its GPU hours (15746 of 15746 charged as of
# 2026-09-21), while m4292 still has ~30 node-hours of its 100 left. If Slurm
# rejects this with an invalid account/partition error, that is NERSC insisting
# GPU jobs charge the _g repo, and it is a question to take back to the PI
# rather than something to fix here.
#
# All five anion systems at once on four A100s, round-robin, so PO4 ends up
# sharing GPU 0 with F. A 390-atom molecule barely dents an 80 GB card and
# sharing one costs far less than leaving a system to never start at all.
#
# 10 ns at 1 fs is 10M UMA calls per system. That will not finish in a single
# 24 h allocation, so resubmit this until all five say DONE. Everything
# checkpoints and resumes. Running them concurrently is what keeps them
# advancing together across resubmissions.
#
# Submit from $SCRATCH/solvationnet/deep-shell/:
#   sbatch perlmutter/la_uma_md.sbatch

set -uo pipefail

module load python
module load cudatoolkit

# Created once by perlmutter/setup_env.sh. `source activate` rather than
# `conda activate`, which needs a shell hook that batch jobs do not get.
source activate solvationnet || { echo "ERROR: could not activate 'solvationnet'"; exit 1; }
python -c "import fairchem, torch; assert torch.cuda.is_available()" \
    || { echo "ERROR: fairchem/CUDA unavailable in this environment"; exit 1; }

WORK="${SLURM_SUBMIT_DIR:-$SCRATCH/solvationnet/deep-shell}"
cd "$WORK" || exit 1

echo "=== La³⁺ solvation MD ==="
echo "Job:  $SLURM_JOB_ID"
echo "Node: $(hostname)"
echo "Date: $(date)"
echo "Dir:  $(pwd)"
echo ""
nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader
echo ""

SYSTEMS=(F OH NO3 CO3 PO4)
NGPU=4

mkdir -p results
for sys in "${SYSTEMS[@]}"; do
    mkdir -p "results/La3+_${sys}"
done

echo "Launching ${#SYSTEMS[@]} systems across $NGPU GPUs"
PIDS=()
NAMES=()
for i in "${!SYSTEMS[@]}"; do
    sys="${SYSTEMS[$i]}"
    gpu=$(( i % NGPU ))
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
for sys in "${SYSTEMS[@]}"; do
    dir="results/La3+_${sys}"
    if [ -f "$dir/final.xyz" ]; then
        echo "  La3+_${sys}:  DONE (final.xyz exists)"
    elif [ -f "$dir/checkpoint.pkl" ]; then
        step=$(tail -n 1 "$dir/md.log" 2>/dev/null | awk '{print $1}')
        echo "  La3+_${sys}:  PARTIAL (last logged step: ${step:-unknown}) — resubmit to continue"
        INCOMPLETE=$((INCOMPLETE + 1))
    else
        echo "  La3+_${sys}:  FAILED (no output; see $dir/slurm.log)"
        INCOMPLETE=$((INCOMPLETE + 1))
    fi
done

if [ "$INCOMPLETE" -gt 0 ]; then
    echo ""
    echo "$INCOMPLETE system(s) incomplete — resubmit: sbatch perlmutter/la_uma_md.sbatch"
fi

echo ""
echo "Finished: $(date)"

# To benchmark instead of running production, swap the launch loop for a single
# short run and read st/s off the step=20,000 progress line:
#   python run_uma_md.py droplets/La3+_F_droplet.xyz -o bench_F/ --steps 20000

# clamped, since FAIL + a child status can wrap past 255 and read as success
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
