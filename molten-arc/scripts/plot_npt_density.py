#!/usr/bin/env python3
"""Plots NPT density equilibration for the molten salt boxes and compares to reference.

Reads the JSON logs written by the MACE NPT runs in
data/molten_salts_solvation_boxes/npt/ and writes two figures.

    python molten-arc/scripts/plot_npt_density.py -o figures/molten-salt/
"""

import argparse
import glob
import json
import os

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

# Molar masses of the salt species in the boxes (g/mol)
SALT_MOLAR_MASSES = {
    "LiCl":   42.394,
    "NaCl":   58.443,
    "KCl":    74.551,
    "CaCl2": 110.984,
    "MgCl2":  95.211,
    "LiF":    25.939,
    "LiBr":   86.845,
    "LiI":   133.845,
}

# Pure-salt densities near their measured temperature, from the Janz NIST
# compilations as tabulated in molten_salt_systems.py. The measurement
# temperature is kept so the mismatch against the run temperature stays visible
SALT_REFERENCE = {
    "LiCl":  (1.502, 973),
    "NaCl":  (1.556, 1123),
    "KCl":   (1.527, 1073),
    "CaCl2": (2.085, 1055),
    "MgCl2": (1.680, 987),
    "LiF":   (1.810, 1143),
    "LiBr":  (2.528, 825),
    "LiI":   (3.109, 742),
}

# Compositions in mol%, from Table 3 of Liu et al., Materials Today 60 (2022) 128
SYSTEM_COMPOSITIONS = {
    "LiCl-KCl":        {"LiCl": 59, "KCl": 41},
    "LiCl-LiI":        {"LiCl": 36, "LiI": 64},
    "LiCl-NaCl-CaCl2": {"LiCl": 38, "NaCl": 27, "CaCl2": 35},
    "LiF-LiCl-LiBr":   {"LiF": 22, "LiCl": 31, "LiBr": 47},
    "MgCl2-NaCl-KCl":  {"MgCl2": 50, "NaCl": 30, "KCl": 20},
}

TIMESTEP_FS = 1.0

# Fraction of each run treated as equilibrated and averaged over
EQUILIBRATED_FROM = 0.6


def ideal_mixing_density(components_mol_pct):
    """Additive molar volume estimate, no temperature correction."""
    total = sum(components_mol_pct.values())
    x = {k: v / total for k, v in components_mol_pct.items()}
    molar_volume = sum(x[k] * SALT_MOLAR_MASSES[k] / SALT_REFERENCE[k][0] for k in x)
    molar_mass = sum(x[k] * SALT_MOLAR_MASSES[k] for k in x)
    return molar_mass / molar_volume


def parse_log(path):
    """Returns system name, run temperature, and the per-frame arrays."""
    name = os.path.basename(path).replace("_MACE-small-0b2.log", "")
    system, _, temp, _ = name.split("_")
    with open(path) as fh:
        records = json.load(fh)

    steps = np.array([r["step"] for r in records])
    return {
        "system": system,
        "temp_K": int(temp.rstrip("K")),
        "time_ps": steps * TIMESTEP_FS / 1000.0,
        "density": np.array([r["density_g_cm3"] for r in records]),
        "T_K": np.array([r["T_K"] for r in records]),
        "volume": np.array([r["V_A3"] for r in records]),
        "elapsed_s": np.array([r["elapsed_s"] for r in records]),
    }


def summarize(run):
    cut = int(len(run["density"]) * EQUILIBRATED_FROM)
    tail = run["density"][cut:]
    reference = ideal_mixing_density(SYSTEM_COMPOSITIONS[run["system"]])
    return {
        "system": run["system"],
        "temp_K": run["temp_K"],
        "ps": run["time_ps"][-1],
        "rho_mean": tail.mean(),
        "rho_sd": tail.std(),
        "T_mean": run["T_K"][cut:].mean(),
        "reference": reference,
        "deviation_pct": 100.0 * (tail.mean() - reference) / reference,
        "steps_per_s": run["time_ps"][-1] * 1000.0 / TIMESTEP_FS / run["elapsed_s"][-1],
    }


def plot_traces(runs, summaries, out_path):
    fig, axes = plt.subplots(1, len(runs), figsize=(3.1 * len(runs), 3.2), sharey=False)

    for ax, run, s in zip(axes, runs, summaries):
        cut = int(len(run["density"]) * EQUILIBRATED_FROM)
        ax.plot(run["time_ps"], run["density"], lw=0.8, color="#2563eb", alpha=0.85)

        # Reference and the equilibrated mean
        ax.axhline(s["reference"], c=(0.6, 0.6, 0.6), ls="--", lw=1.0)
        ax.axhline(s["rho_mean"], c="#dc2626", ls="-", lw=1.0)
        ax.axvspan(run["time_ps"][cut], run["time_ps"][-1], color=(0.9, 0.9, 0.9), zorder=0)

        ax.set_title(f"{run['system']}\n{run['temp_K']} K", fontsize=9)
        ax.set_xlabel("time (ps)", fontsize=8)
        ax.tick_params(labelsize=7)
        ax.text(0.04, 0.06, f"{s['deviation_pct']:+.1f}%", transform=ax.transAxes,
                fontsize=8, color="#dc2626")

    axes[0].set_ylabel("density (g/cm$^3$)", fontsize=8)

    # One legend for the whole row, the panels are too narrow to carry their own
    handles = [
        Line2D([], [], color="#2563eb", lw=1.2, label="density, 0.1 ps sampling"),
        Line2D([], [], color="#dc2626", lw=1.2, label="mean over averaging window"),
        Line2D([], [], color=(0.6, 0.6, 0.6), ls="--", lw=1.2, label="ideal mixing reference"),
        Patch(facecolor=(0.9, 0.9, 0.9), label="averaging window, last 40%"),
    ]
    fig.legend(handles=handles, fontsize=8, frameon=False, ncol=4,
               loc="lower center", bbox_to_anchor=(0.5, -0.07))

    fig.suptitle("NPT density equilibration, MACE-MP small 0b2, 1 atm. "
                 "Red label is the deviation from the reference", fontsize=10)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    print(f"wrote {out_path}")


def plot_comparison(summaries, out_path):
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(9.5, 3.6),
                                  gridspec_kw={"width_ratios": [1.35, 1]})

    names = [s["system"] for s in summaries]
    y = np.arange(len(names))
    mace = np.array([s["rho_mean"] for s in summaries])
    sd = np.array([s["rho_sd"] for s in summaries])
    ref = np.array([s["reference"] for s in summaries])

    ax.barh(y - 0.19, ref, height=0.36, color="#94a3b8", label="ideal mixing estimate")
    ax.barh(y + 0.19, mace, height=0.36, xerr=sd, color="#2563eb",
            error_kw=dict(lw=0.9, capsize=2), label="MACE NPT")
    ax.set_yticks(y)
    ax.set_yticklabels([f"{s['system']}\n{s['temp_K']} K" for s in summaries], fontsize=7.5)
    ax.invert_yaxis()
    ax.set_xlabel("density (g/cm$^3$)", fontsize=8)
    ax.tick_params(labelsize=7)
    ax.legend(fontsize=7.5, frameon=False, loc="lower right")

    dev = np.array([s["deviation_pct"] for s in summaries])
    ax2.barh(y, dev, height=0.5, color="#dc2626")
    ax2.axvline(0, c=(0.6, 0.6, 0.6), ls="--", lw=1.0)
    ax2.set_yticks(y)
    ax2.set_yticklabels([])
    ax2.invert_yaxis()
    ax2.set_xlabel("deviation from reference (%)", fontsize=8)
    ax2.tick_params(labelsize=7)
    for yi, d in zip(y, dev):
        ax2.text(d + 0.3, yi, f"{d:+.1f}%", va="center", ha="left", fontsize=7.5, color="white")

    fig.suptitle("MACE underestimates melt density by 5 to 15 percent", fontsize=10)
    fig.tight_layout()
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    print(f"wrote {out_path}")


def main(npt_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)

    paths = sorted(glob.glob(os.path.join(npt_dir, "*.log")))
    runs = [parse_log(p) for p in paths]
    summaries = [summarize(r) for r in runs]
    print(f"Parsed {len(runs)} NPT logs")

    header = f"{'system':18s} {'T_K':>5s} {'ps':>6s} {'rho':>7s} {'sd':>6s} {'ref':>7s} {'dev%':>7s} {'st/s':>6s}"
    print(header)
    for s in summaries:
        print(f"{s['system']:18s} {s['temp_K']:5d} {s['ps']:6.0f} {s['rho_mean']:7.3f} "
              f"{s['rho_sd']:6.3f} {s['reference']:7.3f} {s['deviation_pct']:+7.1f} "
              f"{s['steps_per_s']:6.1f}")

    plot_traces(runs, summaries, os.path.join(out_dir, "npt_density_traces.png"))
    plot_comparison(summaries, os.path.join(out_dir, "npt_density_comparison.png"))

    # Dump the table so the dataset card and slides read from one source
    table_path = os.path.join(out_dir, "npt_density_summary.json")
    with open(table_path, "w") as fh:
        json.dump(summaries, fh, indent=2)
    print(f"wrote {table_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--npt-dir", default="data/molten_salts_solvation_boxes/npt",
                        help="Directory holding the NPT JSON logs.")
    parser.add_argument("-o", "--out-dir", default="figures/molten-salt",
                        help="Where to write the figures.")
    _args = parser.parse_args()
    main(**vars(_args))
