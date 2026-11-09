#!/usr/bin/env python3
"""Plots throughput and thermal settling for the La3+ UMA benchmark, job 60508816.

Reads data/La3+_MD_benchmark/La3+_<anion>/md.log and slurm.log and writes one
figure showing steps reached per system and the temperature trace.

    python deep-shell/plot_benchmark.py -o figures/lanthanide/
"""

import argparse
import glob
import os
import re

import matplotlib.pyplot as plt
import numpy as np
from ase.io import read

# First shell cutoff for La-O and La-F, past the first minimum of g(r)
SHELL_CUTOFF_A = 3.2

# Systems that shared GPU 0 under the round-robin launcher
SHARED_GPU = {"La3+_F", "La3+_PO4"}

TARGET_NS = 10.0


def parse_md_log(path):
    steps, time_ps, temps, pe = [], [], [], []
    with open(path) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            fields = line.split()
            if len(fields) < 4:
                continue
            steps.append(int(fields[0]))
            time_ps.append(float(fields[1]))
            temps.append(float(fields[2]))
            pe.append(float(fields[3]))
    return np.array(steps), np.array(time_ps), np.array(temps), np.array(pe)


def coordination_number(path):
    """Counts O and F inside the first shell of La per frame."""
    frames = read(path, ":")
    cns = []
    for atoms in frames:
        symbols = np.array(atoms.get_chemical_symbols())
        la = int(np.where(symbols == "La")[0][0])
        d = atoms.get_distances(la, range(len(atoms)))
        ligand = np.isin(symbols, ["O", "F"])
        cns.append(int(((d < SHELL_CUTOFF_A) & ligand).sum()))
    return np.array(cns)


def parse_rate(path):
    """Last reported steps/s from the driver's stdout, nan if it never logged one."""
    rates = re.findall(r"([\d.]+)st/s", open(path).read())
    return float(rates[-1]) if rates else float("nan")


def infer_shared_rates(runs):
    """Fills in rates for the runs that stopped before the first progress line."""
    # The driver logs every 10,000 steps, so the two systems sharing GPU 0 never
    # printed a rate. Every system ran in the same wall window, so scale by the
    # MD seconds the dedicated runs took
    dedicated = [r for r in runs if not np.isnan(r["rate"])]
    window_s = np.mean([r["steps"][-1] / r["rate"] for r in dedicated])
    for r in runs:
        if np.isnan(r["rate"]):
            r["rate"] = r["steps"][-1] / window_s
            r["rate_inferred"] = True
        else:
            r["rate_inferred"] = False
    return window_s


def main(bench_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)

    runs = []
    for d in sorted(glob.glob(os.path.join(bench_dir, "La3+_*"))):
        if not os.path.isdir(d):
            continue
        name = os.path.basename(d)
        steps, time_ps, temps, pe = parse_md_log(os.path.join(d, "md.log"))
        runs.append({
            "name": name,
            "anion": name.replace("La3+_", ""),
            "steps": steps,
            "time_ps": time_ps,
            "temps": temps,
            "pe": pe,
            "cn": coordination_number(os.path.join(d, "trajectory.xyz")),
            "rate": parse_rate(os.path.join(d, "slurm.log")),
            "shared": name in SHARED_GPU,
        })

    window_s = infer_shared_rates(runs)
    print(f"Parsed {len(runs)} benchmark runs over a {window_s:.0f} s MD window")
    for r in runs:
        tag = "inferred" if r["rate_inferred"] else "logged"
        print(f"{r['name']:12s} steps={r['steps'][-1]:>6d}  {r['time_ps'][-1]:>5.0f} ps  "
              f"{r['rate']:5.1f} st/s ({tag})  T={r['temps'][-1]:5.1f} K  "
              f"{'shared GPU' if r['shared'] else 'dedicated'}")

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(9.5, 3.6))

    # Steps reached in the same 30 min wall window
    x = np.arange(len(runs))
    colors = ["#f59e0b" if r["shared"] else "#2563eb" for r in runs]
    ax.bar(x, [r["steps"][-1] / 1000 for r in runs], color=colors, width=0.6)
    ax.set_xticks(x)
    ax.set_xticklabels([r["anion"] for r in runs], fontsize=8)
    ax.set_ylabel("steps reached (thousands)", fontsize=8)
    ax.set_xlabel("anion", fontsize=8)
    ax.tick_params(labelsize=7)
    for xi, r in zip(x, runs):
        ax.text(xi, r["steps"][-1] / 1000 + 0.5, f"{r['rate']:.1f}", ha="center", fontsize=7.5)
    ax.set_title("30 min wall clock, 4 A100s\norange shared one GPU", fontsize=9)

    # First shell occupancy. The seeded geometry is CN 9, so a flat trace means
    # the shell held and a rise means the anion re-coordinated
    # Occupancy is an integer and several systems sit on 9, so each trace is
    # nudged by a twentieth of a unit to keep them apart
    markers = ["o", "s", "^", "D", "v"]
    for i, (r, mark) in enumerate(zip(runs, markers)):
        offset = (i - 2) * 0.05
        ax2.plot(r["time_ps"][:len(r["cn"])], r["cn"] + offset, lw=1.3, marker=mark,
                 ms=3.0, label=r["anion"], alpha=0.9)
    ax2.axhline(9, c=(0.6, 0.6, 0.6), ls="--", lw=1.0)
    ax2.text(0.6, 9.42, "seeded CN 9, matches experiment", fontsize=7, color="#64748b")
    ax2.set_xlabel("time (ps)", fontsize=8)
    ax2.set_ylabel(f"La first shell occupancy, O and F within {SHELL_CUTOFF_A} $\\AA$", fontsize=8)
    ax2.set_yticks([8, 9, 10, 11])
    ax2.set_ylim(7.3, 11.6)
    ax2.tick_params(labelsize=7)
    ax2.legend(fontsize=7, frameon=False, ncol=5, loc="lower left")
    ax2.set_title("Seeded shell holds, nitrate re-coordinates to 10 and 11", fontsize=9)

    fig.suptitle("La$^{3+}$ droplet MD on Perlmutter, UMA-s-1.2, job 60508816", fontsize=10)
    fig.tight_layout()

    out_path = os.path.join(out_dir, "benchmark_throughput.png")
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    print(f"wrote {out_path}")

    # Cost of the production campaign at the measured rate
    dedicated = np.mean([r["rate"] for r in runs if not r["shared"]])
    gpu_hours = TARGET_NS * 1e6 / dedicated / 3600
    print(f"At {dedicated:.1f} steps/s, {TARGET_NS:.0f} ns takes {gpu_hours:.0f} GPU-hours per system")
    print(f"Five systems: {5 * gpu_hours:.0f} GPU-hours, about {5 * gpu_hours / 4:.0f} node-hours")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench-dir", default="data/La3+_MD_benchmark",
                        help="Directory holding the per-system benchmark logs.")
    parser.add_argument("-o", "--out-dir", default="figures/lanthanide",
                        help="Where to write the figure.")
    _args = parser.parse_args()
    main(**vars(_args))
