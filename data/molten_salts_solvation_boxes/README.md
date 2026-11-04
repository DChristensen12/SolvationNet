---
license: cc-by-4.0
task_categories:
  - other
tags:
  - chemistry
  - molecular-dynamics
  - molten-salt
  - electrolyte
  - liquid-metal-battery
  - simulation
  - MLIP
pretty_name: Molten Salt Solvation Boxes
---

# Molten Salt Solvation Boxes

Periodic simulation boxes of molten salt battery electrolytes in extended XYZ format, equilibrated with a machine-learned interatomic potential (MLIP). The systems are pure ionic melts, with no organic solvent, run at the working temperature of the device they serve. Compositions are taken from Table 3 of Liu et al., *Materials Today* **60** (2022) 128, which surveys molten salts used in aluminium-ion batteries (AIBs), liquid metal batteries (LMBs), and molten-air batteries (MABs).

This dataset is the high-temperature counterpart to [na-ion-electrolyte-solvation-boxes](https://huggingface.co/datasets/DChristensen12/na-ion-electrolyte-solvation-boxes), which covers room-temperature organic electrolytes.

## Subsets

| Subset | Files | Systems | Protocol | Potential |
|--------|-------|---------|----------|-----------|
| `npt/` | 10 | 5 | NPT, 1 atm, working temperature | MACE-MP small 0b2 |
| `nvt/` | 5 | 3 | NVT Langevin, working temperature | MACE-MP small 0b2 |
| `packed/` | 3 | 3 | Packmol output, before dynamics | n/a |
| `scripts/` | 2 | n/a | Composition database and packing script | n/a |

### npt

> Initial configurations were packed with Packmol at a literature estimate of the melt density, then equilibrated under NPT dynamics at 1 atm and the working temperature of the system using the MACE-MP small 0b2 potential. The box volume was free to relax, so the resulting density is a prediction rather than an input.

Each run writes a trajectory (`.xyz`) and a per-frame log (`.log`). The trajectory holds positions, momenta, forces, per-atom energies, the full cell matrix, and the virial stress, at 0.5 ps spacing. The log is a JSON list with `step`, `PE_eV`, `KE_eV`, `T_K`, `V_A3`, `density_g_cm3`, `cell_A`, and `elapsed_s` at 0.1 ps spacing.

| System | Application | Composition (mol%) | T (K) | Length (ps) | Density (g/cm³) |
|--------|-------------|--------------------|-------|-------------|------------------|
| LiCl-KCl | synthesis flux | LiCl 59, KCl 41 | 750 | 35 | 1.433 ± 0.030 |
| LiCl-LiI | LMB | LiCl 36, LiI 64 | 683 | 40 | 2.279 ± 0.059 |
| LiCl-NaCl-CaCl₂ | LMB | LiCl 38, NaCl 27, CaCl₂ 35 | 873 | 50 | 1.546 ± 0.040 |
| LiF-LiCl-LiBr | LMB | LiF 22, LiCl 31, LiBr 47 | 773 | 55 | 1.902 ± 0.052 |
| MgCl₂-NaCl-KCl | LMB | MgCl₂ 50, NaCl 30, KCl 20 | 973 | 30 | 1.441 ± 0.049 |

Densities are the mean and standard deviation over the last 40% of each run. Every box holds 200 ions.

### nvt

> Three of the five compositions were thermalized under NVT Langevin dynamics at fixed volume. NVT does not adjust the cell, so these densities are the Packmol packing estimate rather than a prediction.

The NVT subset covers LiCl-KCl, LiF-LiCl-LiBr, and MgCl₂-NaCl-KCl. Files ending in `_continuation` restart from the end of the matching run, giving five files over three systems. These are HDF5 trajectories rather than XYZ. LiCl-LiI and LiCl-NaCl-CaCl₂ went straight from Packmol to NPT and have no NVT stage.

## Density validation

We compared the NPT densities against an ideal additive molar volume estimate built from pure-salt reference densities in the Janz NIST compilations. MACE-MP small 0b2 falls below the estimate for all five systems, by 5.5% for LiCl-KCl and by 10.6% to 14.8% for the other four.

| System | MACE NPT | Ideal mixing | Deviation |
|--------|----------|--------------|-----------|
| LiCl-KCl | 1.433 | 1.516 | −5.5% |
| LiCl-LiI | 2.279 | 2.676 | −14.8% |
| LiCl-NaCl-CaCl₂ | 1.546 | 1.791 | −13.7% |
| LiF-LiCl-LiBr | 1.902 | 2.127 | −10.6% |
| MgCl₂-NaCl-KCl | 1.441 | 1.621 | −11.2% |

Two caveats apply to this comparison. First, the ideal mixing rule ignores the excess volume of mixing, which is small for molten halides but not zero. Second, the pure-salt reference densities were measured between 742 K and 1143 K, in most cases above the temperature of the run, and we did not correct them to the run temperature. Since melts contract on cooling, correcting them would raise the reference and widen the gap. The deviation reported here is therefore likely a lower bound.

The sign is consistent across five systems of differing cation charge and halide, so we read it as a systematic underestimate by the potential rather than a sampling artifact. MACE-MP small is the fastest model in the MACE family and was trained on inorganic crystals, so reduced accuracy on high-temperature ionic liquids is expected. For work that depends on quantitative density, we recommend either a larger MACE checkpoint, a potential fine-tuned on molten salts, or a classical polarizable ion model.

## Construction pipeline

1. Composition, working temperature, and a literature melt density are read from `molten_salt_systems.py`, which encodes Table 3 of Liu et al.
2. Ion counts are computed from the mol fractions, the target density, and the box size, then packed with Packmol at 2.0 Å tolerance into a cubic periodic cell.
3. For three of the five systems, the packed cell is thermalized under NVT Langevin dynamics at the working temperature with a 1 fs timestep.
4. The box is equilibrated under NPT at 1 atm, again with a 1 fs timestep, until the density trace is stationary.

## Naming convention

```
<system>_<ensemble>_<temperature>[_<pressure>]_<potential>[_continuation].<ext>
```

For example, `LiCl-NaCl-CaCl2_npt_873K_1atm_MACE-small-0b2.xyz` is the ternary LiCl-NaCl-CaCl₂ melt under NPT at 873 K and 1 atm with MACE-MP small 0b2.

## Limitations

The runs are 30 ps to 55 ps long, which is enough for the density to reach a stationary value but short for transport properties. Diffusion coefficients and ionic conductivities computed from these trajectories would carry large statistical error. The LiCl-KCl and MgCl₂-NaCl-KCl density traces remain visibly noisy over their averaging windows, so their error bars are wider than the quoted standard deviation suggests.

Boxes hold 200 ions, which is small enough that finite-size effects on the density may be of order one percent.

## Citation

The compositions come from:

> Liu, Y. et al. Molten salts for rechargeable batteries. *Materials Today* **60**, 128 (2022). doi:10.1016/j.mattod.2022.09.005

## License

CC BY 4.0.
