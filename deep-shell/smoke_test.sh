#!/bin/bash
# Run the MD driver for a handful of steps on CPU before submitting anything to
# Perlmutter. Catches what the queue takes days to tell you: a broken
# calculator, a fairchem API change, a force call that throws.
#
#   bash deep-shell/smoke_test.sh [steps] [system]
#
# Needs the CPU test env (ase + fairchem-core 2.22.0, matching Perlmutter):
#   conda activate solvnet-cpu
#
# The very first run has to populate the weight cache, so let it reach the hub:
#   HF_HUB_OFFLINE=0 bash deep-shell/smoke_test.sh
# Every run after that defaults to offline, which also proves the cache is
# readable without the hub -- the failure mode that killed job 60059899.
#
# Two real bugs would have been caught here in under a minute rather than after
# two queue cycles: rebinding predictor.model so fairchem lost .module, and
# anything that breaks the first get_forces().

set -uo pipefail

STEPS="${1:-3}"
SYS="${2:-F}"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
OUT="$(mktemp -d)"

DROPLET="$ROOT/data/La3+_Droplets/La3+_${SYS}_droplet.xyz"
[ -f "$DROPLET" ] || { echo "FAIL: no droplet at $DROPLET"; exit 1; }

echo "=== CPU smoke test ==="
echo "system: La3+_${SYS}   steps: $STEPS"
echo "out:    $OUT"
echo ""

# Weights are gated; offline mode also proves the cache is usable, which is the
# other thing that has bitten us on the compute nodes.
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"

echo "--- 1. cold run ---"
python "$HERE/run_uma_md.py" "$DROPLET" \
    -o "$OUT" --steps "$STEPS" --log-interval 1 --traj-interval 1 \
    --ckpt-interval 1 || { echo "FAIL: cold run exited non-zero"; exit 1; }

rows=$(grep -vc '^#' "$OUT/md.log" 2>/dev/null || echo 0)
[ "$rows" -ge 1 ] || { echo "FAIL: md.log has no data rows"; exit 1; }
echo "ok: md.log has $rows row(s)"

[ -f "$OUT/checkpoint.pkl" ] || { echo "FAIL: no checkpoint written"; exit 1; }
echo "ok: checkpoint written"

echo ""
echo "--- 2. resume run ---"
python "$HERE/run_uma_md.py" "$DROPLET" \
    -o "$OUT" --steps "$((STEPS * 2))" --log-interval 1 --traj-interval 1 \
    --ckpt-interval 1 --resume || { echo "FAIL: resume exited non-zero"; exit 1; }

rows2=$(grep -vc '^#' "$OUT/md.log" 2>/dev/null || echo 0)
[ "$rows2" -gt "$rows" ] || { echo "FAIL: resume added no new rows ($rows -> $rows2)"; exit 1; }
echo "ok: resume advanced the log ($rows -> $rows2 rows)"

echo ""
echo "--- 3. temperature sanity ---"
tail -n 3 "$OUT/md.log"

echo ""
echo "=== PASS ==="
echo "Clean up with: rm -rf $OUT"
