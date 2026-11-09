#!/usr/bin/env python3
"""Compares the equilibrated Nitro densities against the measured ones.

Reads the final structure and the last checkpoint of every campaign system,
prints the per-system error, and writes the table as CSV. The measured
densities come from the CAMPAIGN definitions in build_nitro_boxes.py.

    python electrolyte_toolkit/collect_nitro_results.py -o results_nitro.csv
"""

import argparse
import csv
import glob
import os
import sys

import numpy as np
from ase.io import read

# build_nitro_boxes sits next to this file, not on the path when run from elsewhere
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_nitro_boxes import CAMPAIGN

DEFAULT_CHECKPOINT_DIR = os.path.join(os.path.expanduser("~"), "electrolyte_equilibration")

AMU_PER_A3_TO_G_PER_CM3 = 1.66054

# Density is called converged once the drift between the last two windows is under this
DRIFT_TOLERANCE_PCT = 1.0

RESULT_FIELDS = [
    "name", "exp_density", "sim_density", "error_pct",
    "converged", "drift_pct", "n_atoms", "box_a", "source",
]

DATASET_FIELDS = [
    "filename", "concentration_M", "n_salt",
    "box_a", "box_b", "box_c", "volume_ang3",
    "exp_density_g_cm3", "exp_density_source",
]


def read_final_density(checkpoint_dir, name):
    """Density, atom count, and cell of the final structure, Nones if it is not there."""
    final_xyz = os.path.join(checkpoint_dir, name, f"{name}.xyz")
    if not os.path.isfile(final_xyz):
        return None, None, None

    atoms = read(final_xyz)

    # A blown up box leaves NaN positions, so the run is unusable
    if np.any(np.isnan(atoms.get_positions())):
        return None, len(atoms), None

    density = (sum(atoms.get_masses()) * AMU_PER_A3_TO_G_PER_CM3 / atoms.get_volume())
    return density, len(atoms), atoms.cell.lengths()


def read_convergence(checkpoint_dir, name):
    """Compares the last fifth of the density trace against the one before it."""
    npzs = sorted(glob.glob(os.path.join(checkpoint_dir, name, "ckpt_npt_*.npz")))
    if not npzs:
        return None, None, None

    data = np.load(npzs[-1], allow_pickle=True)
    densities = data.get("densities", None)
    if densities is None or len(densities) < 100:
        return None, None, None

    densities = densities.tolist()
    window = len(densities) // 5
    prev = densities[-(2 * window):-window]
    last = densities[-window:]
    mean_last = np.mean(last)
    drift = 100 * abs(np.mean(last) - np.mean(prev)) / mean_last

    return drift < DRIFT_TOLERANCE_PCT, drift, mean_last


def main(checkpoint_dir, output, append_to):
    results = []

    print(f"\n{'name':<40s} {'exp':>6s} {'sim':>7s} {'err%':>6s} "
          f"{'conv':>5s} {'drift%':>7s} {'atoms':>6s}")

    for name, sys_def in CAMPAIGN.items():
        exp_density = sys_def["density"]
        sim_density, n_atoms, cell = read_final_density(checkpoint_dir, name)
        converged, drift, mean_rho = read_convergence(checkpoint_dir, name)

        if sim_density is None:
            print(f"{name:<40s} {exp_density:>6.3f}     ---   not done")
            continue

        err_pct = 100 * (sim_density - exp_density) / exp_density
        conv_str = "?" if converged is None else "y" if converged else "n"
        drift_str = f"{drift:.2f}" if drift is not None else "?"
        print(f"{name:<40s} {exp_density:>6.3f} {sim_density:>7.4f} "
              f"{err_pct:>+5.1f}% {conv_str:>5s} {drift_str:>7s} {n_atoms:>6d}")

        results.append({
            "name": name,
            "exp_density": exp_density,
            "sim_density": round(sim_density, 4),
            "error_pct": round(err_pct, 2),
            "converged": converged,
            "drift_pct": round(drift, 2) if drift is not None else None,
            "n_atoms": n_atoms,
            "box_a": round(cell[0], 2) if cell is not None else None,
            "source": sys_def["source"],
        })

    print(f"\n{len(results)} of {len(CAMPAIGN)} systems finished")

    if results:
        errors = np.abs([r["error_pct"] for r in results])
        print(f"Mean absolute error {errors.mean():.2f}%, worst {errors.max():.2f}%")
        print(f"Converged: {sum(1 for r in results if r['converged'])} of {len(results)}")

    if output and results:
        with open(output, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS)
            writer.writeheader()
            writer.writerows(results)
        print(f"\nwrote {output}")

    if append_to and results:
        append_dataset_rows(append_to, results)


def append_dataset_rows(append_to, results):
    """Adds the converged systems to the dataset CSV, skipping ones already listed."""
    converged = [r for r in results if r["converged"]]
    if not converged:
        print("\nno converged results to append")
        return

    existing_names = set()
    if os.path.isfile(append_to):
        with open(append_to) as f:
            for row in csv.DictReader(f):
                existing_names.add(row["filename"])

    new_rows = []
    for r in converged:
        fname = f"{r['name']}.xyz"
        if fname in existing_names:
            continue

        n_salt = dict(CAMPAIGN[r["name"]]["molecules"])["Na"]

        # The boxes are cubic, so one edge sets all three
        box_a = r["box_a"]
        new_rows.append({
            "filename": fname,
            "concentration_M": "",
            "n_salt": n_salt,
            "box_a": box_a,
            "box_b": box_a,
            "box_c": box_a,
            "volume_ang3": round(box_a ** 3, 4) if box_a else "",
            "exp_density_g_cm3": r["exp_density"],
            "exp_density_source": r["source"],
        })

    if not new_rows:
        print("\nevery converged result is already in the dataset")
        return

    with open(append_to, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=DATASET_FIELDS)
        writer.writerows(new_rows)
    print(f"\nappended {len(new_rows)} rows to {append_to}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint-dir", default=DEFAULT_CHECKPOINT_DIR,
                        help="Where equilibrate.py kept its checkpoints.")
    parser.add_argument("-o", "--output", metavar="CSV",
                        help="Write the result table here.")
    parser.add_argument("--append-to", metavar="CSV",
                        help="Append the converged systems to this dataset CSV.")
    _args = parser.parse_args()
    main(**vars(_args))
