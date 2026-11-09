#!/usr/bin/env python3
"""Builds the Packmol boxes for the Nitro NPT campaign.

Every composition below carries a measured density, which sets the cubic box
edge for the molecule counts we pack into it. Writes one extxyz per system for
equilibrate.py. Needs packmol on PATH, ASE, and RDKit for any missing PDB.

    python electrolyte_toolkit/build_nitro_boxes.py --dry-run
"""

import argparse
import os
import shutil
import subprocess
import sys

from ase.io import read, write

MOLECULES_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "data", "na-electrolyte-solvation-boxes", "molecules",
)

CAMPAIGN_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "data", "na-electrolyte-solvation-boxes", "nitro_campaign",
)

MW = {
    "Na":     22.990,
    "PF6":   144.964,
    "TFSI":  280.146,
    "ClO4":   99.451,
    "EC":     88.062,
    "DMC":    90.078,
    "PC":    102.089,
    "water":  18.015,
    "Pyr14": 142.261,  # 1-butyl-1-methylpyrrolidinium
    "BMMI":  153.247,  # 1-butyl-2,3-dimethylimidazolium
}

# Atom counts used only for the dry-run estimate, the real count comes from the PDB
ATOMS_PER_MOLECULE = {
    "Na": 1, "PF6": 7, "TFSI": 15, "ClO4": 5,
    "EC": 10, "DMC": 12, "PC": 13, "water": 3,
    "Pyr14": 30, "BMMI": 28,
}

# Cations with no PDB in the molecules folder yet
SMILES = {
    "BMMI": "CCCC[n+]1ccn(C)c1C",
}

# Boxes land near this size, small enough for NPT on one GPU
TARGET_ATOMS = 2000


def napf6_ecdmc(conc_M, density):
    """NaPF6 in EC:DMC 1:1 by weight."""
    mw_salt = MW["Na"] + MW["PF6"]
    mass_solv_per_cm3 = density - conc_M * mw_salt * 1e-3
    r_ec = 0.5 * mass_solv_per_cm3 / (MW["EC"] * 1e-3 * conc_M)
    r_dmc = 0.5 * mass_solv_per_cm3 / (MW["DMC"] * 1e-3 * conc_M)

    atoms_per_salt = 1 + 7  # Na+ and PF6-
    n_salt = max(5, round(TARGET_ATOMS / (atoms_per_salt + r_ec * 10 + r_dmc * 12)))
    n_ec = round(r_ec * n_salt)
    n_dmc = round(r_dmc * n_salt)

    return {
        "molecules": [
            ("Na", n_salt),
            ("PF6", n_salt),
            ("EC", n_ec),
            ("DMC", n_dmc),
        ],
        "density": density,
        "mw_total": n_salt * mw_salt + n_ec * MW["EC"] + n_dmc * MW["DMC"],
    }


def natfsi_ecdmc(conc_M, density):
    """NaTFSI in EC:DMC 1:1 by weight."""
    mw_salt = MW["Na"] + MW["TFSI"]
    mass_solv_per_cm3 = density - conc_M * mw_salt * 1e-3
    r_ec = 0.5 * mass_solv_per_cm3 / (MW["EC"] * 1e-3 * conc_M)
    r_dmc = 0.5 * mass_solv_per_cm3 / (MW["DMC"] * 1e-3 * conc_M)

    atoms_per_salt = 1 + 15  # Na+ and TFSI-
    n_salt = max(5, round(TARGET_ATOMS / (atoms_per_salt + r_ec * 10 + r_dmc * 12)))
    n_ec = round(r_ec * n_salt)
    n_dmc = round(r_dmc * n_salt)

    return {
        "molecules": [
            ("Na", n_salt),
            ("TFSI", n_salt),
            ("EC", n_ec),
            ("DMC", n_dmc),
        ],
        "density": density,
        "mw_total": n_salt * mw_salt + n_ec * MW["EC"] + n_dmc * MW["DMC"],
    }


def ternary(salt_anion, conc_M, density, wt_ec=0.45, wt_pc=0.45, wt_dmc=0.10):
    """Sodium salt in an EC:PC:DMC solvent given as weight fractions."""
    mw_salt = MW["Na"] + MW[salt_anion]
    mass_solv = density - conc_M * mw_salt * 1e-3
    r_ec = wt_ec * mass_solv / (MW["EC"] * 1e-3 * conc_M)
    r_pc = wt_pc * mass_solv / (MW["PC"] * 1e-3 * conc_M)
    r_dmc = wt_dmc * mass_solv / (MW["DMC"] * 1e-3 * conc_M)

    atoms_per_salt = 1 + ATOMS_PER_MOLECULE[salt_anion]
    n_salt = max(5, round(2100 / (atoms_per_salt + r_ec * 10 + r_pc * 13 + r_dmc * 12)))
    n_ec = round(r_ec * n_salt)
    n_pc = round(r_pc * n_salt)
    n_dmc = round(r_dmc * n_salt)

    return {
        "molecules": [
            ("Na", n_salt),
            (salt_anion, n_salt),
            ("EC", n_ec),
            ("PC", n_pc),
            ("DMC", n_dmc),
        ],
        "density": density,
        "mw_total": (n_salt * mw_salt + n_ec * MW["EC"] +
                     n_pc * MW["PC"] + n_dmc * MW["DMC"]),
    }


def naclo4_water(molality, density):
    """NaClO4 in water, concentration given in mol per kg of solvent."""
    mw_salt = MW["Na"] + MW["ClO4"]
    atoms_per_salt = 1 + 5  # Na+ and ClO4-
    n_water_per_salt = 1000.0 / (molality * MW["water"])
    n_salt = max(20, round(TARGET_ATOMS / (atoms_per_salt + n_water_per_salt * 3)))
    n_water = round(n_water_per_salt * n_salt)

    return {
        "molecules": [
            ("Na", n_salt),
            ("ClO4", n_salt),
            ("water", n_water),
        ],
        "density": density,
        "mw_total": n_salt * mw_salt + n_water * MW["water"],
    }


def natfsi_il(il_cation, conc_M, density):
    """NaTFSI dissolved in a TFSI ionic liquid, so the melt supplies extra anions."""
    mw_salt = MW["Na"] + MW["TFSI"]
    mw_il = MW[il_cation] + MW["TFSI"]
    atoms_cation = ATOMS_PER_MOLECULE[il_cation]

    # Ionic liquid per salt follows from the molarity and the density alone,
    # since both are per unit volume: r = (rho / c - mw_salt) / mw_il
    r = (density / (conc_M * 1e-3) - mw_salt) / mw_il

    # Every salt unit brings 1 Na and the melt brings r cations and r anions
    denom = 1 + (1 + r) * 15 + r * atoms_cation
    n_salt = max(5, round(2100 / denom))
    n_il = round(r * n_salt)
    n_tfsi_total = n_salt + n_il

    return {
        "molecules": [
            ("Na", n_salt),
            ("TFSI", n_tfsi_total),
            (il_cation, n_il),
        ],
        "density": density,
        "mw_total": (n_salt * MW["Na"] + n_tfsi_total * MW["TFSI"] +
                     n_il * MW[il_cation]),
    }


# Densities read off plots carry about +/-0.01 g/cm3, tabulated ones less
CAMPAIGN = {
    # NaPF6 in EC:DMC 1:1 wt, the concentration series in Monti 2020 Fig 4c
    "NaPF6_EC-DMC-1-1_0p3M": {
        **napf6_ecdmc(0.3, 1.20),
        "source": "Monti2020_Fig4c",
        "notes": "Read from plot at 25C. EC:DMC 1:1 by weight.",
    },
    "NaPF6_EC-DMC-1-1_0p6M": {
        **napf6_ecdmc(0.6, 1.22),
        "source": "Monti2020_Fig4c",
        "notes": "Read from plot at 25C. EC:DMC 1:1 by weight.",
    },
    "NaPF6_EC-DMC-1-1_0p8M": {
        **napf6_ecdmc(0.8, 1.23),
        "source": "Monti2020_Fig4c",
        "notes": "Read from plot at 25C. EC:DMC 1:1 by weight.",
    },
    "NaPF6_EC-DMC-1-1_1p2M": {
        **napf6_ecdmc(1.2, 1.26),
        "source": "Monti2020_Fig4c",
        "notes": "Read from plot at 25C. EC:DMC 1:1 by weight.",
    },
    "NaPF6_EC-DMC-1-1_1p4M": {
        **napf6_ecdmc(1.4, 1.28),
        "source": "Monti2020_Fig4c",
        "notes": "Read from plot at 25C. EC:DMC 1:1 by weight.",
    },
    "NaPF6_EC-DMC-1-1_1p6M": {
        **napf6_ecdmc(1.6, 1.30),
        "source": "Monti2020_Fig4c",
        "notes": "Read from plot at 25C. EC:DMC 1:1 by weight.",
    },
    "NaPF6_EC-DMC-1-1_1p8M": {
        **napf6_ecdmc(1.8, 1.33),
        "source": "Monti2020_Fig4c",
        "notes": "Read from plot at 25C. EC:DMC 1:1 by weight.",
    },
    "NaPF6_EC-DMC-1-1_2p0M": {
        **napf6_ecdmc(2.0, 1.36),
        "source": "Monti2020_Fig4c",
        "notes": "Read from plot at 25C. EC:DMC 1:1 by weight.",
    },

    # NaTFSI in EC:DMC 1:1 wt, Monti 2020 Fig 4d
    "NaTFSI_EC-DMC-1-1_0p3M": {
        **natfsi_ecdmc(0.3, 1.17),
        "source": "Monti2020_Fig4d",
        "notes": "Read from plot at 25C. EC:DMC 1:1 by weight.",
    },
    "NaTFSI_EC-DMC-1-1_0p6M": {
        **natfsi_ecdmc(0.6, 1.20),
        "source": "Monti2020_Fig4d",
        "notes": "Read from plot at 25C. EC:DMC 1:1 by weight.",
    },
    "NaTFSI_EC-DMC-1-1_0p8M": {
        **natfsi_ecdmc(0.8, 1.22),
        "source": "Monti2020_Fig4d",
        "notes": "Read from plot at 25C. EC:DMC 1:1 by weight.",
    },
    "NaTFSI_EC-DMC-1-1_1p4M": {
        **natfsi_ecdmc(1.4, 1.30),
        "source": "Monti2020_Fig4d",
        "notes": "Read from plot at 25C. EC:DMC 1:1 by weight.",
    },

    # Ternary solvent, EC:PC:DMC at 45:45:10 wt%
    "NaPF6_EC45-PC45-DMC10_1M": {
        **ternary("PF6", 1.0, 1.28),
        "source": "Monti2020_Fig4c",
        "notes": "Read from plot at 25C. Solvent 45:45:10 wt%.",
    },
    "NaTFSI_EC45-PC45-DMC10_1M": {
        **ternary("TFSI", 1.0, 1.27),
        "source": "Monti2020_Fig4d",
        "notes": "Read from plot at 25C. Solvent 45:45:10 wt%.",
    },

    # Water in sodium, the only aqueous box in the campaign
    "NaClO4_water_10m": {
        **naclo4_water(10.0, 1.50),
        "source": "GomezVazquez2025_Table1",
        "notes": "10 molal. Gomez Vazquez et al., JACS 2025, Table 1.",
    },

    # NaTFSI in ionic liquids, Appetecchi et al., Batteries 2024, Table 1, 25C
    "NaTFSI_BMPyrTFSI_0p5M": {
        **natfsi_il("Pyr14", 0.5, 1.436),
        "source": "Appetecchi2024_Table1",
        "notes": "PMC12908124, Table 1, 25C.",
    },
    "NaTFSI_BMPyrTFSI_1p0M": {
        **natfsi_il("Pyr14", 1.0, 1.474),
        "source": "Appetecchi2024_Table1",
        "notes": "PMC12908124, Table 1, 25C.",
    },
    "NaTFSI_BMMITFSI_0p5M": {
        **natfsi_il("BMMI", 0.5, 1.455),
        "source": "Appetecchi2024_Table1",
        "notes": "PMC12908124, Table 1, 25C.",
    },
    "NaTFSI_BMMITFSI_0p83M": {
        **natfsi_il("BMMI", 0.83, 1.491),
        "source": "Appetecchi2024_Table1",
        "notes": "PMC12908124, Table 1, 25C.",
    },
}


def count_atoms_in_pdb(pdb_path):
    n = 0
    with open(pdb_path) as f:
        for line in f:
            if line.startswith(("ATOM", "HETATM")):
                n += 1
    return n


def generate_pdb_from_smiles(name, smiles, output_path):
    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem
    except ImportError:
        print(f"rdkit not available, cannot build {name}.pdb from SMILES")
        print("  pip install rdkit, or draw the molecule in Avogadro")
        sys.exit(1)

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        print(f"invalid SMILES for {name}: {smiles}")
        sys.exit(1)

    # Hydrogens then a quick MMFF relax, packmol only needs a sane geometry
    mol = Chem.AddHs(mol)
    AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
    AllChem.MMFFOptimizeMolecule(mol)

    Chem.MolToPDBFile(mol, output_path)
    print(f"  wrote {output_path} from SMILES {smiles}")


def ensure_pdb_inputs(molecules_dir):
    needed = set()
    for sys_def in CAMPAIGN.values():
        for mol_name, _ in sys_def["molecules"]:
            needed.add(mol_name)

    missing = []
    for name in sorted(needed):
        pdb = os.path.join(molecules_dir, f"{name}.pdb")
        if not os.path.isfile(pdb):
            if name in SMILES:
                generate_pdb_from_smiles(name, SMILES[name], pdb)
            else:
                missing.append(name)

    if missing:
        print("\nmissing PDB inputs with no SMILES fallback:")
        for m in missing:
            print(f"  {m}.pdb")
        print(f"\nDraw them in Avogadro and save to {molecules_dir}/")
        sys.exit(1)


def box_size_from_density(mw_total, density):
    # amu to g is 1.66054e-24, and cm^3 to A^3 is 1e24, so the two cancel
    volume = mw_total * 1.66054 / density
    return volume ** (1.0 / 3.0)


def write_packmol_input(molecules_dir, molecules, box_size, output_pdb, tolerance=2.0):
    lines = [
        f"tolerance {tolerance}",
        "filetype pdb",
        f"output {output_pdb}",
        "",
    ]
    for mol_name, count in molecules:
        pdb = os.path.join(molecules_dir, f"{mol_name}.pdb")
        lines.append(f"structure {pdb}")
        lines.append(f"  number {count}")
        lines.append(f"  inside box 0. 0. 0. {box_size:.3f} {box_size:.3f} {box_size:.3f}")
        lines.append("end structure")
        lines.append("")
    return "\n".join(lines)


def add_cryst1(pdb_path, box_size):
    """Writes the cell into the PDB header so ASE picks up periodicity."""
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


def build_one(name, sys_def, molecules_dir, output_dir, dry_run=False):
    molecules = sys_def["molecules"]
    density = sys_def["density"]
    box_size = box_size_from_density(sys_def["mw_total"], density)

    total_atoms = 0
    for mol_name, count in molecules:
        pdb = os.path.join(molecules_dir, f"{mol_name}.pdb")
        if os.path.isfile(pdb):
            n_atoms = count_atoms_in_pdb(pdb)
        else:
            n_atoms = ATOMS_PER_MOLECULE.get(mol_name, 10)
        total_atoms += count * n_atoms

    n_salt = dict(molecules)["Na"]

    print(f"\n  {name}")
    print(f"    density={density:.2f} g/cm3  box={box_size:.1f} A  "
          f"atoms={total_atoms}  n_salt={n_salt}")
    for mol_name, count in molecules:
        print(f"    {mol_name:>8s}: {count:4d}")
    print(f"    source: {sys_def['source']}")

    if dry_run:
        return

    sys_dir = os.path.join(output_dir, name)
    os.makedirs(sys_dir, exist_ok=True)
    pdb_out = os.path.join(sys_dir, f"{name}.pdb")
    xyz_out = os.path.join(sys_dir, f"{name}.xyz")

    if os.path.exists(xyz_out):
        print(f"    skipping, {xyz_out} exists")
        return

    inp = write_packmol_input(molecules_dir, molecules, box_size, pdb_out)
    with open(os.path.join(sys_dir, "packmol.inp"), "w") as f:
        f.write(inp)

    if shutil.which("packmol") is None:
        print("    packmol not found on PATH")
        return

    result = subprocess.run(
        ["packmol"], input=inp, capture_output=True, text=True, timeout=300,
    )

    if result.returncode != 0 or not os.path.exists(pdb_out):
        print(f"    packmol failed, exit {result.returncode}")
        if result.stdout:
            for line in result.stdout.strip().split("\n")[-5:]:
                print(f"      {line}")
        return

    add_cryst1(pdb_out, box_size)
    atoms = read(pdb_out)
    atoms.pbc = True
    write(xyz_out, atoms, format="extxyz")
    print(f"    wrote {xyz_out}")


def main(output_dir, molecules_dir, only, dry_run, list_systems):
    if list_systems:
        print(f"{'name':<40s} {'density':>8s} source")
        for name, sys_def in CAMPAIGN.items():
            print(f"{name:<40s} {sys_def['density']:>7.2f}  {sys_def['source']}")
        print(f"\n{len(CAMPAIGN)} systems")
        return

    molecules_dir = os.path.abspath(molecules_dir)
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    print(f"Molecules: {molecules_dir}")
    print(f"Output:    {output_dir}")

    if not dry_run:
        ensure_pdb_inputs(molecules_dir)

    systems = CAMPAIGN
    if only:
        systems = {k: v for k, v in CAMPAIGN.items() if k in only}
        unknown = set(only) - set(CAMPAIGN)
        if unknown:
            print(f"unknown systems: {', '.join(sorted(unknown))}")

    print(f"\nBuilding {len(systems)} boxes")
    for name, sys_def in systems.items():
        build_one(name, sys_def, molecules_dir, output_dir, dry_run=dry_run)

    if not dry_run:
        built = [n for n in systems
                 if os.path.exists(os.path.join(output_dir, n, f"{n}.xyz"))]
        print(f"\nBuilt {len(built)} of {len(systems)} boxes in {output_dir}/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output-dir", default=CAMPAIGN_DIR,
                        help="Where to write the built boxes.")
    parser.add_argument("--molecules-dir", default=MOLECULES_DIR,
                        help="Directory holding the PDB molecule inputs.")
    parser.add_argument("--only", nargs="+", metavar="NAME",
                        help="Build only these systems.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print molecule counts and box sizes without building.")
    parser.add_argument("--list", dest="list_systems", action="store_true",
                        help="List the campaign and exit.")
    _args = parser.parse_args()
    main(**vars(_args))
