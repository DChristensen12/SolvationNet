#!/usr/bin/env python3
"""Compares box density across the three equilibration protocols in the Na-ion dataset.

For every composition that finished NPT with UMA, we read the matching NVT box
and, where it exists, the OrbMol NPT box, and plot the densities side by side.

    python electrolyte_toolkit/plot_density_protocols.py -o figures/na-ion/
"""

import argparse
import glob
import json
import os

import matplotlib.pyplot as plt
import numpy as np
from ase.io import read

# amu/A^3 to g/cm^3
AMU_PER_A3_TO_G_PER_CM3 = 1.66053906660


def box_density(path):
    atoms = read(path)
    return atoms.get_masses().sum() / atoms.get_volume() * AMU_PER_A3_TO_G_PER_CM3, len(atoms)


def collect(root):
    npt_dir = os.path.join(root, "NPT_FAIRChem-UMA")
    nvt_dir = os.path.join(root, "NVT_OrbMolV2")
    ext_dir = os.path.join(nvt_dir, "npt_extended")

    rows = []
    for path in sorted(glob.glob(os.path.join(npt_dir, "*.xyz"))):
        name = os.path.basename(path)
        uma, n_atoms = box_density(path)

        nvt_path = os.path.join(nvt_dir, name)
        nvt = box_density(nvt_path)[0] if os.path.exists(nvt_path) else np.nan

        ext_path = os.path.join(ext_dir, name)
        orb = box_density(ext_path)[0] if os.path.exists(ext_path) else np.nan

        rows.append({
            "name": name.replace(".xyz", ""),
            "n_atoms": n_atoms,
            "packmol_nvt": nvt,
            "orbmol_npt": orb,
            "uma_npt": uma,
        })
    return rows


def main(root, out_dir):
    os.makedirs(out_dir, exist_ok=True)

    rows = collect(root)
    print(f"Collected {len(rows)} compositions that finished NPT with UMA")
    print(f"{'composition':34s} {'atoms':>6s} {'NVT':>7s} {'OrbNPT':>7s} {'UMANPT':>7s} {'dUMA%':>7s}")
    for r in rows:
        dev = 100.0 * (r["uma_npt"] - r["packmol_nvt"]) / r["packmol_nvt"]
        print(f"{r['name']:34s} {r['n_atoms']:6d} {r['packmol_nvt']:7.3f} "
              f"{r['orbmol_npt']:7.3f} {r['uma_npt']:7.3f} {dev:+7.1f}")

    fig, ax = plt.subplots(figsize=(8.5, 3.8))

    x = np.arange(len(rows))
    w = 0.26
    ax.bar(x - w, [r["packmol_nvt"] for r in rows], w, color="#94a3b8",
           label="Packmol estimate, NVT")
    ax.bar(x, [r["orbmol_npt"] for r in rows], w, color="#16a34a",
           label="OrbMol-v2 NPT")
    ax.bar(x + w, [r["uma_npt"] for r in rows], w, color="#2563eb",
           label="UMA-s-1.2 NPT")

    ax.set_xticks(x)
    ax.set_xticklabels([r["name"].replace("_", "\n") for r in rows], fontsize=6.5)
    ax.set_ylabel("density (g/cm$^3$)", fontsize=8)
    ax.tick_params(labelsize=7)
    ax.legend(fontsize=7.5, frameon=False, loc="upper right")
    ax.set_title("NPT raises the Packmol box density by two thirds, and the two potentials agree",
                 fontsize=10)

    # OrbMol has no NPT run for the KFSI box
    missing = [i for i, r in enumerate(rows) if np.isnan(r["orbmol_npt"])]
    for i in missing:
        ax.text(i, 0.05, "no run", ha="center", fontsize=6.5, rotation=90, color="#64748b")

    # The point of the figure is how far NPT moves the box, so label the rise
    for xi, r in zip(x, rows):
        rise = 100.0 * (r["uma_npt"] - r["packmol_nvt"]) / r["packmol_nvt"]
        top = max(r["uma_npt"], np.nan_to_num(r["orbmol_npt"]))
        ax.annotate("", xy=(xi + w, r["uma_npt"]), xytext=(xi - w, r["packmol_nvt"]),
                    arrowprops=dict(arrowstyle="->", color="#c2410c", lw=1.1,
                                    connectionstyle="arc3,rad=-0.25"))
        ax.text(xi, top + 0.13, f"+{rise:.0f}%", ha="center", fontsize=9,
                fontweight="bold", color="#c2410c")

    ax.set_ylim(0, max(r["uma_npt"] for r in rows) * 1.25)

    fig.tight_layout()
    out_path = os.path.join(out_dir, "density_by_protocol.png")
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    print(f"wrote {out_path}")

    table_path = os.path.join(out_dir, "density_by_protocol.json")
    with open(table_path, "w") as fh:
        json.dump(rows, fh, indent=2)
    print(f"wrote {table_path}")

    both = [r for r in rows if not np.isnan(r["orbmol_npt"])]
    spread = [100.0 * abs(r["uma_npt"] - r["orbmol_npt"]) / r["orbmol_npt"] for r in both]
    print(f"UMA and OrbMol agree to {np.mean(spread):.1f}% on average over {len(both)} boxes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="data/na-electrolyte-solvation-boxes",
                        help="Root of the Na-ion dataset tree.")
    parser.add_argument("-o", "--out-dir", default="figures/na-ion",
                        help="Where to write the figure.")
    _args = parser.parse_args()
    main(**vars(_args))
