#!/bin/bash
#SBATCH -A m3278
#SBATCH -C gpu
#SBATCH -q regular
#SBATCH -t 48:00:00
#SBATCH -N 1
#SBATCH --ntasks-per-node=1
#SBATCH --gpus-per-node=1
#SBATCH --cpus-per-task=32
#SBATCH -J mace_polar_npt
#SBATCH -o mace_polar_npt_%j.out
#SBATCH -e mace_polar_npt_%j.err

module load python
module load cudatoolkit

# Activate your conda env (create once with setup_env.sh)
source activate mace-polar

# Run the simulation
# Fresh start:
python run_mace_polar_npt.py \
    --input npt_run.xyz \
    --output-dir ./output_2 \
    --model polar-1-s \
    --steps 1000000 \
    --timestep 1.0 \
    --temperature 300.0 \
    --traj-interval 20

# To restart from a previous run, use:
# python run_mace_polar_npt.py \
#     --input npt_run.xyz \
#     --output-dir ./output \
#     --model polar-1-s \
#     --steps 100000 \
#     --restart
