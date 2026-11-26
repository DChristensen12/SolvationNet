#!/bin/bash
for f in inputs/*.xyz; do sbatch run_replicas.sbatch "$(basename "$f" .xyz)"; done
