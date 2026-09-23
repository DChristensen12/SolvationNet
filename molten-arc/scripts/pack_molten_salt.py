#!/usr/bin/env python3
"""Packs molten salt ions into a cubic simulation cell with Packmol.

Part of BACON — Battery Architectures via Computational Observation of Nonaqueous salts

Molten salts are pure ionic systems — no organic solvents. You specify
the salt composition (mol fractions), a target density, and a box size,
and this script figures out how many of each ion to pack.

Unlike the Na-electrolyte toolkit where we mix salt + solvent at a molarity,
here the entire box IS the salt. So the workflow is:

    1. Pick a system from molten_salt_systems.py
    2. Set the box size and target density
    3. This script calculates ion counts from the mol fractions
    4. Packmol packs them

Needs the `packmol` binary on PATH and PDB files for each ion species.

Examples
--------
# NaAlCl4 electrolyte for Al-ion batteries
python pack_molten_salt.py \
  --system NaAlCl4 \
  --box-size 25 \
  --density 1.6 \
  --ion-dir ../data/ions \
  --output packed/NaAlCl4_25A.pdb

# Custom composition
python pack_molten_salt.py \
  --ion Na:na.pdb:38 \
  --ion Li:li.pdb:29 \
  --ion Ca:ca.pdb:35 \
  --ion Cl:cl.pdb:auto \
  --box-size 30 \
  --density 2.0 \
  --output packed/custom.pdb
"""

import argparse
import math
import os
import shutil
import subprocess
import sys

AVOGADRO = 6.02214076e23


# Formula-unit compositions: for each salt, what ions it dissociates into
# and how many of each per formula unit
SALT_DISSOCIATION = {
    "LiCl":   {"Li": 1, "Cl": 1},
    "NaCl":   {"Na": 1, "Cl": 1},
    "KCl":    {"K": 1,  "Cl": 1},
    "CaCl2":  {"Ca": 1, "Cl": 2},
    "BaCl2":  {"Ba": 1, "Cl": 2},
    "MgCl2":  {"Mg": 1, "Cl": 2},
    "AlCl3":  {"Al": 1, "Cl": 3},
    "LiF":    {"Li": 1, "F": 1},
    "NaF":    {"Na": 1, "F": 1},
    "KF":     {"K": 1,  "F": 1},
    "LiBr":   {"Li": 1, "Br": 1},
    "LiI":    {"Li": 1, "I": 1},
    "LiNO3":  {"Li": 1, "NO3": 1},
    "LiOH":   {"Li": 1, "OH": 1},
    "Li2CO3": {"Li": 2, "CO3": 1},
    "Na2CO3": {"Na": 2, "CO3": 1},
    "K2CO3":  {"K": 2,  "CO3": 1},
    "ZnCl2":  {"Zn": 1, "Cl": 2},
}

# Molar masses needed for density-based count calculation
SALT_MOLAR_MASSES = {
    "LiCl":   42.394,  "NaCl":   58.443, "KCl":    74.551,
    "CaCl2": 110.984,  "BaCl2": 208.233, "MgCl2":  95.211,
    "AlCl3": 133.341,  "LiF":    25.939, "NaF":    41.988,
    "KF":     58.097,  "LiBr":   86.845, "LiI":   133.845,
    "LiNO3":  68.946,  "LiOH":   23.948, "Li2CO3": 73.891,
    "Na2CO3":105.989,  "K2CO3": 138.205, "ZnCl2": 136.286,
}


def compute_ion_counts(components_mol_pct, box_size_A, density_g_cm3):
    """Given mol% of each salt, box size, and target density, return ion counts.

    The idea: figure out how many total formula units fit in the box at the
    given density, then split them according to mol fractions, then dissociate
    each salt into its constituent ions.
    """
    # Normalize mol fractions
    total_pct = sum(components_mol_pct.values())
    fractions = {k: v / total_pct for k, v in components_mol_pct.items()}

    # Average molar mass of the mixture
    avg_mw = sum(fractions[salt] * SALT_MOLAR_MASSES[salt] for salt in fractions)

    # Volume in cm^3
    vol_cm3 = (box_size_A * 1e-8) ** 3

    # Total mass that fits in the box
    total_mass_g = density_g_cm3 * vol_cm3

    # Total moles of formula units
    total_moles = total_mass_g / avg_mw

    # Total formula units
    total_fu = total_moles * AVOGADRO

    # Count of each salt's formula units
    salt_counts = {}
    for salt, frac in fractions.items():
        salt_counts[salt] = max(1, round(frac * total_fu))

    # Dissociate into ions
    ion_counts = {}
    for salt, n_fu in salt_counts.items():
        if salt not in SALT_DISSOCIATION:
            raise ValueError(f"Don't know how to dissociate '{salt}'. "
                             f"Add it to SALT_DISSOCIATION.")
        for ion, stoich in SALT_DISSOCIATION[salt].items():
            ion_counts[ion] = ion_counts.get(ion, 0) + n_fu * stoich

    return salt_counts, ion_counts


def write_packmol_input(ion_specs, box_size, output_path, tolerance=2.5, seed=None):
    """Builds the packmol input for an all-ionic box."""
    lines = [
        f"tolerance {tolerance}",
        "filetype pdb",
        f"output {output_path}",
    ]
    if seed is not None:
        lines.append(f"seed {seed}")
    lines.append("")

    for ion_name, pdb_path, count in ion_specs:
        lines.append(f"structure {pdb_path}")
        lines.append(f"  number {count}")
        lines.append(f"  inside box 0. 0. 0. {box_size} {box_size} {box_size}")
        lines.append("end structure")
        lines.append("")

    return "\n".join(lines)


def add_cryst1_to_pdb(pdb_path, box_size):
    """Adds a CRYST1 record so MD codes know the box is periodic."""
    cryst1 = (
        f"CRYST1{box_size:9.3f}{box_size:9.3f}{box_size:9.3f}"
        f"  90.00  90.00  90.00 P 1           1\n"
    )
    with open(pdb_path) as f:
        content = f.read()
    if content.startswith("CRYST1"):
        lines = content.split("\n")
        lines[0] = cryst1.rstrip()
        content = "\n".join(lines)
    else:
        content = cryst1 + content
    with open(pdb_path, "w") as f:
        f.write(content)


def main():
    parser = argparse.ArgumentParser(
        description="Pack molten salt ions into a cubic simulation cell.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--system",
                        help="Named system from molten_salt_systems.py (e.g. NaAlCl4).")
    parser.add_argument("--ion", action="append", metavar="NAME:PATH:MOL_PCT",
                        help="Manual ion spec (use instead of --system).")
    parser.add_argument("-b", "--box-size", type=float, required=True,
                        help="Cubic box edge length in angstroms.")
    parser.add_argument("-d", "--density", type=float, required=True,
                        help="Target density in g/cm^3.")
    parser.add_argument("--ion-dir", default=".",
                        help="Directory containing ion PDB files.")
    parser.add_argument("-o", "--output", required=True,
                        help="Output PDB file path.")
    parser.add_argument("--tolerance", type=float, default=2.5,
                        help="Min distance between atoms in Å (default: 2.5).")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed for reproducibility.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print counts and Packmol input without executing.")

    args = parser.parse_args()

    if args.system:
        # Import the systems database
        sys.path.insert(0, os.path.dirname(__file__))
        from molten_salt_systems import ELECTROLYTE_SYSTEMS
        if args.system not in ELECTROLYTE_SYSTEMS:
            print(f"ERROR: Unknown system '{args.system}'")
            print(f"Available: {', '.join(ELECTROLYTE_SYSTEMS.keys())}")
            sys.exit(1)
        system = ELECTROLYTE_SYSTEMS[args.system]
        components = system["components"]
        print(f"System: {args.system}")
        print(f"  {system['description']}")
        print(f"  Application: {system['application']}")
        print(f"  Working temp: {system['working_temp_C']} °C")
    else:
        if not args.ion:
            parser.error("Provide either --system or --ion specs.")
        components = {}
        for spec in args.ion:
            parts = spec.split(":")
            if len(parts) != 3:
                raise ValueError(f"Ion spec must be 'SALT:path:mol_pct', got: {spec}")
            salt_name, _, mol_pct = parts
            components[salt_name] = float(mol_pct)

    vol_A3 = args.box_size ** 3
    vol_cm3 = vol_A3 * 1e-24
    print(f"\nBox: {args.box_size:.1f} Å  ({vol_A3:.0f} Å³ = {vol_cm3:.4e} cm³)")
    print(f"Target density: {args.density:.3f} g/cm³")

    salt_counts, ion_counts = compute_ion_counts(
        components, args.box_size, args.density
    )

    print(f"\nSalt formula units:")
    for salt, count in salt_counts.items():
        print(f"  {salt:>10s}: {count:>5d}")

    print(f"\nIon counts (after dissociation):")
    total_ions = 0
    for ion, count in ion_counts.items():
        print(f"  {ion:>10s}: {count:>5d}")
        total_ions += count
    print(f"  {'Total':>10s}: {total_ions:>5d} ions")

    # Build packmol specs
    ion_specs = []
    for ion_name, count in ion_counts.items():
        pdb_file = os.path.join(args.ion_dir, f"{ion_name.lower()}.pdb")
        if not os.path.isfile(pdb_file) and not args.dry_run:
            print(f"WARNING: Ion PDB not found: {pdb_file}")
            print(f"  Create it or point --ion-dir to the right place.")
        ion_specs.append((ion_name, pdb_file, count))

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)

    inp_content = write_packmol_input(
        ion_specs, args.box_size, os.path.abspath(args.output),
        args.tolerance, args.seed,
    )

    if args.dry_run:
        print("\n--- Packmol input ---")
        print(inp_content)
        return

    if shutil.which("packmol") is None:
        print("ERROR: 'packmol' not found on PATH.")
        sys.exit(1)

    print("\nRunning packmol...")
    result = subprocess.run(
        ["packmol"], input=inp_content, capture_output=True, text=True
    )

    if result.returncode != 0 or not os.path.exists(args.output):
        print(f"ERROR: Packmol failed (exit code {result.returncode})")
        print(result.stdout[-500:] if result.stdout else "")
        print(result.stderr[-500:] if result.stderr else "")
        sys.exit(1)

    for line in result.stdout.strip().split("\n")[-3:]:
        print(f"  {line}")

    add_cryst1_to_pdb(args.output, args.box_size)
    print(f"\nPacked molten salt cell written to: {args.output}")


if __name__ == "__main__":
    main()
