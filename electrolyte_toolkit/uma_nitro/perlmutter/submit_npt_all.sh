#!/bin/bash
for f in relaxed/*.xyz; do sbatch npt_density_nitro.sbatch "$(basename "$f" .xyz)"; done
