#!/bin/bash
#SBATCH -A m4292
#SBATCH -q premium
#SBATCH -C gpu
#SBATCH -N 1
#SBATCH --gpus-per-node=4
#SBATCH --ntasks-per-node=1
#SBATCH -c 128
#SBATCH -t 01:00:00
#SBATCH -J uma_npt
#SBATCH -o uma_npt_%j.out
# One NPT run of one density-benchmark system, 100 ps, UMA uma-s-1p2p1-ft-d4rev (UMA Nitro)
# at 1 bar and 300 K, on one node, starting from the box relax_boxes_nitro.sbatch relaxed.
# Run that first. Then submit every relaxed system once, from the folder that holds
# relaxed/ and md_npt_nitro.py, $SCRATCH/SolvationNet/electrolyte_toolkit/uma_nitro/perlmutter
# (submit_npt_all.sh does the same):
#     for f in relaxed/*.xyz; do sbatch npt_density_nitro.sbatch "$(basename "$f" .xyz)"; done
# Each 1 hour chunk queues the next one for its system as soon as it starts, runs MD
# until 5 minutes before its time limit, checkpoints and exits; the next chunk carries
# on. A system's chain ends by itself when its run reaches PS ps or fails to relax, or
# after two chunks in a row make no progress. Output: replicas/<system>/rep00/. Stop everything with:
#     scancel -n uma_npt
# To go longer, raise PS (e.g. to 500) and submit again; runs continue from ckpt.npz.
# If a replica's run.log says it ran out of GPU memory, change -C gpu above to
# -C "gpu&hbm80g" (80 GB A100s). With fewer nodes than replicas (-N 5, say) the
# replicas simply run in waves.

SYS=${1:?usage: sbatch npt_density_nitro.sbatch <system, e.g. 079_DME-neat>}
NREP=1       # replicas per system
PS=100       # ps per replica
GPUS=4       # GPUs per replica (one node); 1 runs the single-GPU nitro preset instead of multigpu
MARGIN=300   # seconds before the job's end at which every replica checkpoints and stops
CKPT=/global/homes/d/dchrist2/.cache/fairchem/models--facebook--UMA/snapshots/1f43bb7ff24084b72e8253f9e16fbac19320adae/checkpoints/uma-s-1p2p1-ft-d4rev.pt
EXTRA=()                    # extra md_npt_nitro.py flags
EXTRA+=(--temp 300)         # every system at 300 K instead of each file's run_T_K
EXTRA+=(--no-minimize)      # relaxed/ boxes are already minimized by relax_boxes_nitro.sbatch

cd "$SLURM_SUBMIT_DIR" || exit 1
# The solvationnet env from deep-shell/perlmutter/setup_env.sh. `source activate` rather than
# `conda activate`, which needs a shell hook that batch jobs do not get.
module load python cudatoolkit
source activate solvationnet || { echo "could not activate the solvationnet env"; exit 1; }
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=8
export HF_HUB_OFFLINE=1  # read the model cache without the Hugging Face file lock, which fails on compute nodes
OUT=replicas/$SYS
mkdir -p "$OUT"
[ -f "relaxed/$SYS.xyz" ] || { echo "no relaxed/$SYS.xyz; run relax_boxes_nitro.sbatch first"; exit 1; }

# A replica is done when its DONE file records at least PS ps (1 fs steps), so raising PS
# and resubmitting carries finished runs on from their checkpoints.
rep_done() {
    local f=$OUT/$(printf 'rep%02d' "$1")/DONE n
    [ -f "$f" ] && read -r n _ < "$f" && (( n >= PS * 1000 ))
}
# A replica whose minimization hit the step cap without relaxing is never run.
rep_failed() {
    [ -f "$OUT/$(printf 'rep%02d' "$1")/FAILED_RELAX" ]
}

todo=()
for (( r = 0; r < NREP; r++ )); do
    if rep_failed "$r"; then
        echo "$SYS failed to relax, skipped"
    elif ! rep_done "$r"; then
        todo+=("$r")
    fi
done
if (( ${#todo[@]} == 0 )); then
    echo "every replica of $SYS has reached $PS ps or failed to relax; nothing to do"
    exit 0
fi
owner=$(cat "$OUT/owner" 2>/dev/null)
if [ -n "$owner" ] && [ "$owner" != "$SLURM_JOB_ID" ] && [ "$(squeue -h -j "$owner" -o %A 2>/dev/null)" = "$owner" ]; then
    echo "job $owner is already running $SYS; this one exits without touching it"
    exit 0
fi
echo "$SLURM_JOB_ID" > "$OUT/owner"
if [ -f "$OUT/.chunk_start" ] && ! find "$OUT" \( -name ckpt.npz -o -name relax.npz \) -newer "$OUT/.chunk_start" | grep -q .; then
    fails=$(( $(cat "$OUT/.noprogress" 2>/dev/null || echo 0) + 1 ))
    echo "$fails" > "$OUT/.noprogress"
    if (( fails >= 2 )); then
        echo "two chunks in a row made no progress for $SYS, so its chain stops here: read $OUT/rep*/run.log"
        exit 1
    fi
    echo "the previous chunk for $SYS made no progress; trying once more"
else
    rm -f "$OUT/.noprogress"
fi
touch "$OUT/.chunk_start"

# Stop MARGIN seconds before this job's end time (from Slurm; one hour from now if unknown).
now=$(date +%s)
end=${SLURM_JOB_END_TIME:-0}
(( end > now )) || end=$(date -d "$(squeue -h -j "$SLURM_JOB_ID" -o %e 2>/dev/null)" +%s 2>/dev/null || echo 0)
(( end > now )) || end=$(( now + 3600 ))
STOP_AT=$(( end - MARGIN ))

# Queue this system's next chunk now: same node count, or fewer if fewer replicas are left.
nn=${SLURM_JOB_NUM_NODES:-${#todo[@]}}
(( ${#todo[@]} < nn )) && nn=${#todo[@]}
next=$(sbatch --parsable -N "$nn" --dependency=afterany:"$SLURM_JOB_ID" npt_density_nitro.sbatch "$SYS")
mapfile -t NODES < <(scontrol show hostnames "$SLURM_JOB_NODELIST")
running=("${todo[@]:0:${#NODES[@]}}")
echo "job $SLURM_JOB_ID: $SYS replicas ${running[*]} on ${#NODES[@]} nodes, $GPUS GPUs each," \
     "checkpoint at $(date -d "@$STOP_AT" '+%T'), next chunk ${next%%;*}"

for (( k = 0; k < ${#todo[@]} && k < ${#NODES[@]}; k++ )); do
    r=${todo[$k]}
    dir=$OUT/$(printf 'rep%02d' "$r")
    mkdir -p "$dir"
    srun -N 1 -n 1 -c 128 --cpu-bind=none --gpus-per-node=4 --gpu-bind=none --kill-on-bad-exit=0 \
        --nodelist="${NODES[$k]}" \
        python md_npt_nitro.py --ckpt "$CKPT" --replica "$r" --ps "$PS" --gpus "$GPUS" --stop-at "$STOP_AT" \
        "${EXTRA[@]}" "relaxed/$SYS.xyz" >> "$dir/run.log" 2>&1 &
done
wait

echo "== where each replica stands"
for (( r = 0; r < NREP; r++ )); do
    log=$OUT/$(printf 'rep%02d' "$r")/run.log
    [ -f "$log" ] && grep "$SYS rep" "$log" | tail -n 1
done
left=0
for (( r = 0; r < NREP; r++ )); do rep_done "$r" || rep_failed "$r" || left=$(( left + 1 )); done
if (( left == 0 )); then
    scancel "${next%%;*}"
    echo "every replica of $SYS has reached $PS ps or failed to relax; cancelled the queued chunk ${next%%;*}"
fi
