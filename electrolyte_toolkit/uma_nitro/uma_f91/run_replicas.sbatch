#!/bin/bash
#SBATCH -A gen0039
#SBATCH -q premium
#SBATCH -C gpu
#SBATCH -N 10
#SBATCH --gpus-per-node=4
#SBATCH --ntasks-per-node=1
#SBATCH -c 128
#SBATCH -t 01:00:00
#SBATCH -J uma_rep
#SBATCH -o uma_rep_%j.out
# Ten replicas of one F91 system, 100 ps each, UMA uma-s-1p2p1 in turbo mode, one replica
# per node spread over its four A100s. Submit all four systems once, from the folder
# that holds inputs/ and md_turbo.py:
#     for s in F91_26FA F91_DFMB F91_TFMB F91_TTE; do sbatch run_replicas.sbatch $s; done
# Each 1 hour chunk queues the next one for its system as soon as it starts, runs MD
# until 5 minutes before its time limit, checkpoints and exits; the next chunk carries
# on. A system's chain ends by itself when all its replicas reach 100 ps, or after two
# chunks in a row make no progress. Output: replicas/<system>/repNN/. Stop everything
# with:  scancel -n uma_rep
# If a replica's run.log says turbo ran out of GPU memory, change -C gpu above to
# -C "gpu&hbm80g" (80 GB A100s). With fewer nodes than replicas (-N 5, say) the
# replicas simply run in waves.

SYS=${1:?usage: sbatch run_replicas.sbatch <system, e.g. F91_TTE>}
NREP=10      # replicas per system
PS=100       # ps per replica
GPUS=4       # GPUs per replica (one node)
MARGIN=300   # seconds before the job's end at which every replica checkpoints and stops
CKPT=/global/homes/n/nitesh/.cache/fairchem/models--facebook--UMA/snapshots/1f43bb7ff24084b72e8253f9e16fbac19320adae/checkpoints/uma-s-1p2p1.pt

cd "$SLURM_SUBMIT_DIR" || exit 1
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=8
OUT=replicas/$SYS
mkdir -p "$OUT"
[ -f "inputs/$SYS.xyz" ] || { echo "no inputs/$SYS.xyz"; exit 1; }

todo=()
for (( r = 0; r < NREP; r++ )); do
    [ -f "$OUT/$(printf 'rep%02d' "$r")/DONE" ] || todo+=("$r")
done
if (( ${#todo[@]} == 0 )); then
    echo "all $NREP replicas of $SYS have reached $PS ps; nothing to do"
    exit 0
fi
owner=$(cat "$OUT/owner" 2>/dev/null)
if [ -n "$owner" ] && [ "$owner" != "$SLURM_JOB_ID" ] && [ "$(squeue -h -j "$owner" -o %A 2>/dev/null)" = "$owner" ]; then
    echo "job $owner is already running $SYS; this one exits without touching it"
    exit 0
fi
echo "$SLURM_JOB_ID" > "$OUT/owner"
if [ -f "$OUT/.chunk_start" ] && ! find "$OUT" -name ckpt.npz -newer "$OUT/.chunk_start" | grep -q .; then
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
next=$(sbatch --parsable -N "$nn" --dependency=afterany:"$SLURM_JOB_ID" run_replicas.sbatch "$SYS")
mapfile -t NODES < <(scontrol show hostnames "$SLURM_JOB_NODELIST")
running=("${todo[@]:0:${#NODES[@]}}")
echo "job $SLURM_JOB_ID: $SYS replicas ${running[*]} on ${#NODES[@]} nodes, turbo on $GPUS GPUs each," \
     "checkpoint at $(date -d "@$STOP_AT" '+%T'), next chunk ${next%%;*}"

for (( k = 0; k < ${#todo[@]} && k < ${#NODES[@]}; k++ )); do
    r=${todo[$k]}
    dir=$OUT/$(printf 'rep%02d' "$r")
    mkdir -p "$dir"
    srun -N 1 -n 1 -c 128 --cpu-bind=none --gpus-per-node=4 --gpu-bind=none --kill-on-bad-exit=0 \
        --nodelist="${NODES[$k]}" \
        python md_turbo.py --ckpt "$CKPT" --replica "$r" --ps "$PS" --gpus "$GPUS" --stop-at "$STOP_AT" \
        "inputs/$SYS.xyz" >> "$dir/run.log" 2>&1 &
done
wait

echo "== where each replica stands"
for (( r = 0; r < NREP; r++ )); do
    log=$OUT/$(printf 'rep%02d' "$r")/run.log
    [ -f "$log" ] && grep "$SYS rep" "$log" | tail -n 1
done
left=0
for (( r = 0; r < NREP; r++ )); do [ -f "$OUT/$(printf 'rep%02d' "$r")/DONE" ] || left=$(( left + 1 )); done
if (( left == 0 )); then
    scancel "${next%%;*}"
    echo "all $NREP replicas of $SYS have reached $PS ps; cancelled the queued chunk ${next%%;*}"
fi
