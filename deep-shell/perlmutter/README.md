# La³⁺ Solvation MD on Perlmutter

10 ns unconstrained NVT MD on La³⁺ + anion + 128 H₂O droplets using
FAIRChem UMA-s-1.2 (OMol25 task head) on NERSC Perlmutter A100 GPUs.

## Systems

| File | Composition | Atoms | Net Charge | Spin |
|------|-------------|-------|------------|------|
| La3+_F_droplet.xyz | 1 La³⁺ + 3 F⁻ + 128 H₂O | 388 | 0 | 1 (singlet) |
| La3+_OH_droplet.xyz | 1 La³⁺ + 3 OH⁻ + 128 H₂O | 391 | 0 | 1 |
| La3+_NO3_droplet.xyz | 1 La³⁺ + 3 NO₃⁻ + 128 H₂O | 397 | 0 | 1 |
| La3+_CO3_droplet.xyz | 1 La³⁺ + 2 CO₃²⁻ + 128 H₂O | 393 | **−1** | 1 |
| La3+_PO4_droplet.xyz | 1 La³⁺ + 1 PO₄³⁻ + 128 H₂O | 390 | 0 | 1 |

La³⁺ is [Xe]4f⁰, closed-shell, no unpaired electrons; F⁻, OH⁻, NO₃⁻,
CO₃²⁻ and PO₄³⁻ are all closed-shell too, so every system is a singlet
(multiplicity 1). `charge` and `spin` in `atoms.info` are read by the
FAIRChem omol task head.

**CO₃ is not neutral.** 3+ cannot be balanced by an integer number of
divalent anions, so this system carries a net −1 and its electrostatics
are not strictly comparable to the other four. The clean fix is
2 La³⁺ + 3 CO₃²⁻, i.e. step 2 of the scale-up plan.

### Starting structures

The La³⁺ first shell is seeded as a **tricapped trigonal prism, CN = 9**,
with anions on the capping sites and water on the remaining vertices, mean La–X of 2.48–2.55 Å against an experimental 2.54–2.56 Å
(Persson et al., *Chem. Eur. J.* **2008**, 14, 3056; D'Angelo et al.,
*Inorg. Chem.* **2011**, 50, 4572). First-shell water dipoles point away
from the cation (La···H ≥ 3.2 Å). Bulk water fills a ~9.5 Å sphere at
0.93–1.07× bulk density, and no intermolecular contact is shorter than
2.17 Å, so the droplets run at 1 fs without a minimization pass.

Relaxation out of the seeded geometry is not small. A 150 step test on CPU
released about 28 eV of potential energy and reached 623 K before the
thermostat recovered it. Temperatures measured on GPU had settled to 259 to
306 K by 10 to 20 ps. The structure takes longer.

Rebuild them with:

```bash
python build_droplet.py -o droplets/
```

Anions start **inner-sphere and monodentate**. Nitrate and carbonate are
usually bidentate on La³⁺ in the solid state, so expect the first tens of
ps of each trajectory to be a re-coordination transient, not equilibrium.

## Quick start

```bash
# From SolvationNet repo root, deploy everything to Perlmutter:
bash deep-shell/perlmutter/deploy.sh <your_nersc_username>

# Then on Perlmutter:
cd $SCRATCH/SolvationNet/deep-shell
bash perlmutter/setup_env.sh           # one-time
sbatch -A m4292 -q overrun --requeue -t 06:00:00 perlmutter/la_uma_md.sbatch
```

## Setup (one-time, on Perlmutter)

```bash
bash perlmutter/setup_env.sh

# UMA weights are gated, log in once:
python -c "from huggingface_hub import login; login()"
```

## Manual deploy (without deploy.sh)

```bash
# From local machine:
scp deep-shell/run_uma_md.py \
    user@perlmutter.nersc.gov:\$SCRATCH/SolvationNet/deep-shell/

scp deep-shell/perlmutter/* \
    user@perlmutter.nersc.gov:\$SCRATCH/SolvationNet/deep-shell/perlmutter/

scp droplets/La3+_*_droplet.xyz \
    user@perlmutter.nersc.gov:\$SCRATCH/SolvationNet/deep-shell/droplets/
```

## Monitor

```bash
squeue -u $USER                          # job status
tail -f results/La3+_F/slurm.log         # live output for one system
tail -f la_uma_md_<jobid>.out            # SLURM wrapper output
```

## Retrieve results

```bash
# From local machine:
scp -r user@perlmutter.nersc.gov:\$SCRATCH/SolvationNet/deep-shell/results/ .
```

## MD parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| Model | UMA-s-1.2 (FAIRChem) | OMol25 task head, TF32 on, torch.compile off |
| Ensemble | NVT (Langevin) | Weak friction 0.01/fs |
| Temperature | 300 K | Room temperature |
| Timestep | 1 fs | No bond constraints (MLIP handles H vibrations) |
| Duration | 10 ns | 10,000,000 steps |
| Trajectory | every 1 ps | ~10,000 frames |
| Checkpoints | every 10 ps | Resume-safe on timeout or preemption |
| Hardware | 1 node, 4× A100-40GB | 4 systems per pass, one per GPU |
| Wall time | 6 hours or less | Long requests do not schedule on overrun, see below |
| Account and QOS | m4292, overrun | Zero charge, lowest priority, preemptible |

## Inference settings

`get_uma_calculator` passes fairchem an `InferenceSettings` object with
`tf32=True` and `activation_checkpointing=False`. Both have to go through that
object. A module-level `torch.set_float32_matmul_precision("high")` does not
reach the compiled graph, and job 60508816 ran with tensor cores idle because
of it.

`torch.compile` is off unless `--compile` is passed. The neighbour list changes
size every step, so dynamo re-traces repeatedly, and the speedup was never
measured. Rebinding `predictor.model` to the compiled wrapper also breaks
fairchem, which reads `self.model.module` at predict time.

## Runtime expectations

10 ns at a 1 fs timestep is 10,000,000 UMA force calls per system. We measured
**13.9 steps/s** on job 60508816 with one system per GPU, which is 200 GPU-hours
per system, or about 250 node-hours for all five systems run four at a time.
That measurement predates the TF32 fix, so treat it as a floor.

A system sharing a GPU ran at about 5 steps/s against 13.9 dedicated, so four
systems on four GPUs beats five. Each pass takes the four least advanced
systems, and resubmitting advances all five evenly.

Keep walltime requests short. A 24 hour request pended for 17 days and never
started, while every 30 minute job reached a node within hours. At 13.9 steps/s
a 6 hour job covers about 300,000 steps.

Benchmark a change before committing queue time:

```bash
python run_uma_md.py droplets/La3+_F_droplet.xyz -o /tmp/bench --steps 2000
```

Progress lines print 100 and 1000 steps in, then every `--progress-interval`
steps, so throughput is visible immediately. Divide 10,000,000 by the `st/s`
figure for hours per system.

For a code change, test on CPU first and skip the queue entirely:

```bash
bash deep-shell/smoke_test.sh
```

If 10 ns proves out of reach, the honest options are a shorter target
(2 to 5 ns is still well past the 100 ps ligand-exchange timescale) or a
larger timestep with constrained H (rigid water), not a silently truncated
run.

## Resume on timeout

The sbatch script always passes `--resume`. If the job times out or OOMs,
resubmit the same script, each system picks up from its last checkpoint
(saved every 10 ps). Preemption is normal on the overrun queue, so `--requeue`
puts the job straight back in the queue.

```bash
sbatch -A m4292 -q overrun --requeue -t 06:00:00 perlmutter/la_uma_md.sbatch
```

Checkpoints are sparser than the trajectory and log, so a killed job leaves
output past the step it resumes from. `_trim_after_checkpoint` drops those
frames and rows on resume, which keeps the step column monotonic.

## Directory layout on Perlmutter

```
$SCRATCH/SolvationNet/deep-shell/
├── run_uma_md.py              # MD runner
├── build_droplet.py           # Droplet builder
├── droplets/                  # Input structures
│   ├── La3+_F_droplet.xyz
│   └── ...
├── perlmutter/                # SLURM scripts
│   ├── la_uma_md.sbatch
│   ├── setup_env.sh
│   └── deploy.sh
└── results/                   # Output (created by sbatch)
    ├── La3+_F/
    │   ├── trajectory.xyz     # 10,000 frames at 1 ps
    │   ├── md.log             # step, time, T, PE, KE
    │   ├── checkpoint.pkl     # latest checkpoint
    │   ├── final.xyz          # final structure
    │   └── snap_*.xyz         # periodic snapshots
    └── ...
```
