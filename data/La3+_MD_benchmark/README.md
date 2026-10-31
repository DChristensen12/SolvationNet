# La³⁺ UMA MD throughput benchmark, job 60508816

This directory holds the first successful GPU run of the La³⁺ droplet molecular
dynamics on Perlmutter, recorded on 2026-10-29. We share it as a throughput
measurement and a provenance record. It is not production data, for the reasons
given under Caveats.

| | |
| --- | --- |
| Slurm job | 60508816 |
| Account and QOS | m4292, overrun queue at zero charge, since the m4292_g allocation is spent |
| Node | 1 node, 4 NVIDIA A100-SXM4-40GB |
| Walltime | 30 min requested, ended TIMEOUT at 00:30:25 |
| Model | FAIRChem UMA-s-1.2, OMol25 task head, fairchem 2.22.0, torch 2.13.0+cu130 |
| Ensemble | NVT Langevin, 300 K, 1 fs timestep, friction 0.01 fs⁻¹, no periodic boundaries, centre of mass fixed |

## Throughput

We measured 13.9 steps/s with one system per GPU. This replaces the a priori
estimate of 20 to 50 steps/s in `deep-shell/perlmutter/SUBMISSION.md`.

```
La3+_CO3:  step=20,000  T=286K  13.9st/s  ETA=199.9h
La3+_NO3:  step=20,000  T=259K  13.9st/s  ETA=199.3h
La3+_OH:   step=20,000  T=305K  13.9st/s  ETA=199.2h
```

At that rate, 10 ns at a 1 fs timestep takes 200 GPU-hours per system, or
1,000 GPU-hours for all five systems. Running four systems per 4-GPU node, this
is roughly 250 node-hours of allocation, the low end of the 300 to 700
node-hour range estimated in SUBMISSION.md.

## Effect of sharing a GPU

The launcher assigned five systems to four GPUs round-robin, so F and PO₄ shared
GPU 0. Steps reached in the same 30 minutes:

| System | GPU | Steps | Rate |
| --- | --- | --- | --- |
| CO₃, NO₃, OH | one each | 22,000 | 13.9 steps/s |
| F, PO₄ | both on GPU 0 | 9,000 | about 5 steps/s each |

Sharing works and is not a failure mode, but one card serving two systems gives
about 10 steps/s against 13.9 dedicated. The batch script now runs one system
per GPU and selects the four least advanced systems on each pass.

## Caveats

These runs cannot be continued. The checkpoint interval was 50,000 steps, which
at 13.9 steps/s fires once an hour, so no `checkpoint.pkl` was written and no
velocities were saved. The default is now 10,000 steps.

The trajectories are not equilibrated. They cover 22 ps, which falls inside the
window SUBMISSION.md describes as a re-coordination transient rather than
equilibrium. Local tests on CPU showed about 28 eV released as the seeded
tricapped trigonal prism first shell relaxes, with temperature reaching 623 K
before the thermostat recovered it. The temperatures here, 259 to 306 K,
indicate thermal settling by 10 to 20 ps, but the structure has not settled.

The run predates the `fixcm=False` correction, so `Langevin` applied its own
deprecated centre of mass handling alongside the `FixCom` constraint. ASE warns
that this does not strictly sample the correct NVT distributions.

TensorFloat32 was off. `torch._inductor` reported that tensor cores were
available but not enabled, `InferenceSettings` defaults `tf32` to False, and the
module-level `set_float32_matmul_precision` call never reached the compiled
graph. Later runs pass `tf32=True`, so 13.9 steps/s should be read as a floor.

## Files

Each `La3+_<anion>/` directory holds three files. `md.log` gives step, time_ps,
T_K, PE_eV and KE_eV at 1 ps spacing. `trajectory.xyz` holds 22 frames at 1 ps
spacing, or 9 frames for F and PO₄. `slurm.log` is the driver's standard output,
including the progress lines quoted above.
