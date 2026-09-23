#!/usr/bin/env python3
"""
bacon.py — convenience wrapper for molten-arc because its funny
codename: BACON (Battery Architectures via Computational Observation of Nonaqueous salts)

This is just a front door. All the real work lives in:
    scripts/molten_salt_systems.py   — salt database
    scripts/pack_molten_salt.py      — box packing
    notebooks/MoltenArc.ipynb        — walkthrough and analysis
    perlmutter/submit.py             — HPC batch submission

bacon.py only exists so you can quickly peek at the available systems
and their ion counts without opening the notebook.

Usage
-----
    python bacon.py --menu
    python bacon.py --system NaAlCl4 --box-size 25 --density 1.6
    python bacon.py --system LiCl-LiI --box-size 30 --density 2.5 --dry-run
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scripts"))

from molten_salt_systems import ELECTROLYTE_SYSTEMS, SYNTHESIS_SALTS, list_all_systems
from pack_molten_salt import compute_ion_counts


BANNER = r"""
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║   🥓  B A C O N  🥓                                         ║
    ║   Battery Architectures via Computational                    ║
    ║   Observation of Nonaqueous salts                            ║
    ║                                                              ║
    ║   molten-arc / SolvationNet                                  ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
"""


def print_menu():
    """What's on the menu today?"""
    print(BANNER)
    print("=" * 64)
    print("  THE MENU — Molten Salt Systems Ready to Simulate")
    print("=" * 64)
    print()

    print("  APPETIZERS (Al-ion battery electrolytes, <120 °C)")
    print("  " + "-" * 50)
    for name in ["NaAlCl4", "AlCl3-NaCl-LiCl-KCl", "AlCl3-NaCl-KCl"]:
        sys_info = ELECTROLYTE_SYSTEMS[name]
        print(f"    {name:<32s}  {sys_info['working_temp_C']:>4d} °C")
    print()

    print("  MAIN COURSE (Liquid metal battery electrolytes, 400-700 °C)")
    print("  " + "-" * 50)
    for name in ["LiCl-LiF", "LiCl-LiI", "LiCl-NaCl-CaCl2",
                  "LiCl-NaCl-CaCl2-BaCl2", "MgCl2-NaCl-KCl",
                  "LiCl-NaCl-KCl", "LiF-LiCl-LiBr"]:
        sys_info = ELECTROLYTE_SYSTEMS[name]
        print(f"    {name:<32s}  {sys_info['working_temp_C']:>4d} °C")
    print()

    print("  DESSERT (Molten-air battery electrolytes)")
    print("  " + "-" * 50)
    for name in ["Li2CO3-Na2CO3-K2CO3-LiOH"]:
        sys_info = ELECTROLYTE_SYSTEMS[name]
        print(f"    {name:<32s}  {sys_info['working_temp_C']:>4d} °C")
    print()

    print("  SIDES (Synthesis salts — reaction media for electrode materials)")
    print("  " + "-" * 50)
    for name, info in SYNTHESIS_SALTS.items():
        lo, hi = info["typical_temp_C"]
        print(f"    {name:<32s}  {lo}-{hi} °C")
    print()


def sizzle(system_name, box_size, density, dry_run=False):
    """The main cook — compute ion counts for a system."""
    if system_name not in ELECTROLYTE_SYSTEMS:
        print(f"  '{system_name}' is not on the menu.")
        print(f"  Run: python bacon.py --menu")
        sys.exit(1)

    system = ELECTROLYTE_SYSTEMS[system_name]
    salt_counts, ion_counts = compute_ion_counts(
        system["components"], box_size, density
    )

    total_ions = sum(ion_counts.values())
    temp_C = system["working_temp_C"]

    print(BANNER)
    print(f"  Order up: {system_name}")
    print(f"  {system['description']}")
    print(f"  Application: {system['application']}")
    print(f"  Temperature: {temp_C} °C ({temp_C + 273.15:.1f} K)")
    print()
    print(f"  Box: {box_size:.1f} Å  |  Density: {density:.3f} g/cm³")
    print()
    print(f"  Salt formula units:")
    for salt, count in salt_counts.items():
        print(f"    {salt:>10s}: {count:>5d}")
    print()
    print(f"  Ions in the box:")
    for ion, count in ion_counts.items():
        print(f"    {ion:>10s}: {count:>5d}")
    print(f"    {'Total':>10s}: {total_ions:>5d}")
    print()

    if dry_run:
        print("  (dry run — nothing was packed, just showing counts)")
    else:
        print("  Next steps:")
        print(f"    1. Generate ion PDB files (see the notebook)")
        print(f"    2. python scripts/pack_molten_salt.py \\")
        print(f"         --system {system_name} --box-size {box_size} \\")
        print(f"         --density {density} --ion-dir data/ions \\")
        print(f"         --output data/packed/{system_name}_{box_size:.0f}A.pdb")
        print(f"    3. Equilibrate at {temp_C + 273.15:.0f} K (NVT → NPT)")
        print(f"    4. Production MD")


def main():
    parser = argparse.ArgumentParser(
        description="bacon.py — molten salt simulation runner (codename BACON)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="🥓 Battery Architectures via Computational Observation of Nonaqueous salts",
    )
    parser.add_argument("--menu", action="store_true",
                        help="Show all available molten salt systems.")
    parser.add_argument("--system",
                        help="Name of the molten salt system (see --menu).")
    parser.add_argument("-b", "--box-size", type=float, default=25.0,
                        help="Cubic box edge in Å (default: 25).")
    parser.add_argument("-d", "--density", type=float, default=1.8,
                        help="Target density in g/cm³ (default: 1.8).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show ion counts without packing.")

    args = parser.parse_args()

    if args.menu:
        print_menu()
    elif args.system:
        sizzle(args.system, args.box_size, args.density, args.dry_run)
    else:
        print(BANNER)
        print("  Run with --menu to see available systems,")
        print("  or --system <name> to start cooking.")
        print()
        print("  Examples:")
        print("    python bacon.py --menu")
        print("    python bacon.py --system NaAlCl4 --box-size 25 --density 1.6")
        print("    python bacon.py --system LiCl-LiI --box-size 30 --density 2.5 --dry-run")


if __name__ == "__main__":
    main()
