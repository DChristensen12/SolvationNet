---
license: cc-by-4.0
task_categories:
  - other
tags:
  - chemistry
  - molecular-dynamics
  - lanthanide
  - actinide
  - solvation
  - hydration
  - simulation
  - MLIP
pretty_name: Lanthanide Hydration Droplets
---

# Lanthanide Hydration Droplets

Seeded starting structures for molecular dynamics (MD) of the La³⁺ aqua ion with five inner-sphere anions. Each structure is a non-periodic water droplet holding one La³⁺, its counter-anions, and 128 water molecules, built so that the first coordination shell starts in the geometry that experiment reports for aqueous La³⁺.

These are inputs, not trajectories. We share them so that the production runs now queued on NERSC Perlmutter, and any independent run, start from the same geometry. Trajectories will be released as a separate subset once the 10 ns production campaign finishes.

## Structures

| File | Composition | Atoms | Net charge | Spin multiplicity |
|------|-------------|-------|------------|-------------------|
| `La3+_F_droplet.xyz` | 1 La³⁺ + 3 F⁻ + 128 H₂O | 388 | 0 | 1 |
| `La3+_OH_droplet.xyz` | 1 La³⁺ + 3 OH⁻ + 128 H₂O | 391 | 0 | 1 |
| `La3+_NO3_droplet.xyz` | 1 La³⁺ + 3 NO₃⁻ + 128 H₂O | 397 | 0 | 1 |
| `La3+_CO3_droplet.xyz` | 1 La³⁺ + 2 CO₃²⁻ + 128 H₂O | 393 | −1 | 1 |
| `La3+_PO4_droplet.xyz` | 1 La³⁺ + 1 PO₄³⁻ + 128 H₂O | 390 | 0 | 1 |

La³⁺ is [Xe]4f⁰ and closed shell, and F⁻, OH⁻, NO₃⁻, CO₃²⁻ and PO₄³⁻ are closed shell as well, so every system is a singlet. The `charge` and `spin` keys in `atoms.info` are read directly by the OMol25 task head of the FAIRChem UMA potential.

The carbonate system is not charge neutral. A 3+ cation cannot be balanced by an integer number of divalent anions, so this droplet carries a net −1 and its electrostatics are not strictly comparable to the other four. A neutral alternative is 2 La³⁺ + 3 CO₃²⁻, which we plan as a later system.

## How the structures were built

> The La³⁺ first shell is seeded as a tricapped trigonal prism with coordination number 9, with anions on the capping sites and water on the remaining vertices. Mean La–X distances are 2.48 to 2.55 Å, against an experimental 2.54 to 2.56 Å. First-shell water dipoles point away from the cation, with La···H of at least 3.2 Å. Bulk water fills a sphere of radius about 9.5 Å at 0.93 to 1.07 times bulk density. No intermolecular contact is shorter than 2.17 Å, so the droplets run at a 1 fs timestep without a minimization pass.

Experimental first-shell distances are from Persson et al., *Chem. Eur. J.* **14**, 3056 (2008) and D'Angelo et al., *Inorg. Chem.* **50**, 4572 (2011).

Anions start inner-sphere and monodentate. Nitrate and carbonate are usually bidentate on La³⁺ in the solid state, so we expect the first tens of picoseconds of any trajectory started here to be a re-coordination transient rather than equilibrium. A 150 step test on CPU released about 28 eV as the seeded shell relaxed, and the temperature reached 623 K before the thermostat recovered it.

`build_droplet.py` regenerates all five structures:

```bash
python build_droplet.py -o droplets/
```

## Intended use

These structures are built for unconstrained NVT MD with a universal MLIP. The protocol we run is Langevin dynamics at 300 K with a 1 fs timestep, friction 0.01 fs⁻¹, no periodic boundaries, and the centre of mass fixed, using FAIRChem UMA-s-1.2 with the OMol25 task head.

A throughput measurement on one Perlmutter node with four NVIDIA A100-SXM4-40GB cards gave 13.9 steps/s with one system per GPU. At that rate, 10 ns per system takes about 200 GPU-hours, or about 250 node-hours for all five systems.

## Scope

The droplet model is finite and non-periodic. It captures the first and second hydration shells well and avoids the periodic image artifacts that a small charged cell would introduce, but it has a liquid-vapour interface about 9.5 Å from the cation and no bulk dielectric beyond that. Properties that depend on long-range solvent response, such as absolute solvation free energies, should not be read from these droplets without a correction.

Lanthanum is the entry point for this work. The same construction extends to the rest of the lanthanide series and to the early actinides, where the contraction of the ionic radius across the series is expected to change the preferred coordination number.

## License

CC BY 4.0.
