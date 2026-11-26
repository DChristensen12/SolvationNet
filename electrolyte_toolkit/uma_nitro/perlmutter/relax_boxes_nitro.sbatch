#!/bin/bash
#SBATCH -A m4292
#SBATCH -q premium
#SBATCH -C gpu
#SBATCH -N 1
#SBATCH --gpus-per-node=4
#SBATCH --ntasks-per-node=1
#SBATCH -c 128
#SBATCH -t 01:00:00
#SBATCH -J uma_relax
#SBATCH -o uma_relax_%j.out
# Relaxes all 101 raw boxes in inputs/ with UMA uma-s-1p2p1-ft-d4rev (UMA Nitro) before NPT:
# FIRE at fixed cell to fmax 0.05 eV/A, at most 5000 steps per box. Four boxes at a time,
# one per A100, on the single-GPU nitro preset. Submit once, from the folder that holds
# inputs/ and relax_boxes.py, $SCRATCH/SolvationNet/electrolyte_toolkit/uma_nitro/perlmutter:
#     sbatch relax_boxes_nitro.sbatch
# Each 1 hour chunk queues the next one as soon as it starts, relaxes boxes until 5 minutes
# before its time limit, saves any box in progress and exits; the next chunk carries on. The
# chain ends by itself when every box is relaxed or failed, or after two chunks in a row
# make no progress. Output: relaxed/<system>.xyz, relaxed/FAILED/<system>.txt and
# relax_report.csv; check them before submitting NPT with submit_npt_all.sh. Stop with:
#     scancel -n uma_relax
# If a worker log says a box ran out of GPU memory, change -C gpu above to -C "gpu&hbm80g".

NWORK=4      # boxes relaxed at once, one per GPU
MARGIN=300   # seconds before the job's end at which every worker saves and stops
CKPT=REPLACE_WITH_NITRO_CKPT_PATH

cd "$SLURM_SUBMIT_DIR" || exit 1
# The solvationnet env from deep-shell/perlmutter/setup_env.sh. `source activate` rather than
# `conda activate`, which needs a shell hook that batch jobs do not get.
module load python cudatoolkit
source activate solvationnet || { echo "could not activate the solvationnet env"; exit 1; }
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=8
export HF_HUB_OFFLINE=1  # read the model cache without the Hugging Face file lock, which fails on compute nodes
mkdir -p relaxed/FAILED relax_work
ls inputs/*.xyz > /dev/null 2>&1 || { echo "no inputs/*.xyz"; exit 1; }

left_boxes() {  # boxes neither relaxed nor failed
    local n=0 f s
    for f in inputs/*.xyz; do
        s=$(basename "$f" .xyz)
        [ -f "relaxed/$s.xyz" ] || [ -f "relaxed/FAILED/$s.txt" ] || n=$(( n + 1 ))
    done
    echo "$n"
}

if (( $(left_boxes) == 0 )); then
    python relax_boxes.py --report
    echo "every box is relaxed or failed; nothing to do"
    exit 0
fi
owner=$(cat relax_work/owner 2>/dev/null)
if [ -n "$owner" ] && [ "$owner" != "$SLURM_JOB_ID" ] && [ "$(squeue -h -j "$owner" -o %A 2>/dev/null)" = "$owner" ]; then
    echo "job $owner is already relaxing the boxes; this one exits without touching them"
    exit 0
fi
echo "$SLURM_JOB_ID" > relax_work/owner
if [ -f relax_work/.chunk_start ] && ! find relaxed relax_work \( -name '*.xyz' -o -name '*.txt' -o -name '*.npz' \) \
        -newer relax_work/.chunk_start | grep -q .; then
    fails=$(( $(cat relax_work/.noprogress 2>/dev/null || echo 0) + 1 ))
    echo "$fails" > relax_work/.noprogress
    if (( fails >= 2 )); then
        echo "two chunks in a row made no progress, so the chain stops here: read relax_work/worker*.log"
        exit 1
    fi
    echo "the previous chunk made no progress; trying once more"
else
    rm -f relax_work/.noprogress
fi
touch relax_work/.chunk_start
rm -rf relax_work/*.claim  # claims from the previous chunk; this job owns the folder now

# Stop MARGIN seconds before this job's end time (from Slurm; one hour from now if unknown).
now=$(date +%s)
end=${SLURM_JOB_END_TIME:-0}
(( end > now )) || end=$(date -d "$(squeue -h -j "$SLURM_JOB_ID" -o %e 2>/dev/null)" +%s 2>/dev/null || echo 0)
(( end > now )) || end=$(( now + 3600 ))
STOP_AT=$(( end - MARGIN ))

next=$(sbatch --parsable --dependency=afterany:"$SLURM_JOB_ID" relax_boxes_nitro.sbatch)
echo "job $SLURM_JOB_ID: $(left_boxes) boxes left, $NWORK workers, stop at $(date -d "@$STOP_AT" '+%T')," \
     "next chunk ${next%%;*}"

for (( k = 0; k < NWORK; k++ )); do
    CUDA_VISIBLE_DEVICES=$k python relax_boxes.py --ckpt "$CKPT" --stop-at "$STOP_AT" \
        >> "relax_work/worker$k.log" 2>&1 &
done
wait

python relax_boxes.py --report
if (( $(left_boxes) == 0 )); then
    scancel "${next%%;*}"
    echo "every box is relaxed or failed; cancelled the queued chunk ${next%%;*}"
fi
