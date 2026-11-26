#!/usr/bin/env python3
"""Relaxes the starting boxes with UMA uma-s-1p2p1-ft-d4rev (UMA Nitro) before NPT.

    python relax_boxes.py --ckpt uma-s-1p2p1-ft-d4rev.pt --stop-at <unix time>
    python relax_boxes.py --report

Run one copy per GPU (relax_boxes_nitro.sbatch starts four). Each copy claims the next
unfinished box from inputs/*.xyz, largest first, and minimizes its positions with FIRE at
fixed cell until fmax <= 0.05 eV/A, at most 5000 steps counted across chunks. The model
runs on fairchem's single-GPU "nitro" preset, task omol, with a fresh predictor per box
because Nitro is set up for one composition at a time.
Output:
  relaxed/<system>.xyz         relaxed box: the input header, positions and cell, plus
                               fire_steps and fmax_eV_A; this is the NPT starting structure
  relaxed/FAILED/<system>.txt  fmax and step count of a box that reached 5000 steps unrelaxed
  relax_work/<system>.npz      restart point of a box cut off by the deadline
  relax_work/<system>.log      FIRE log
  relax_report.csv             one row per box (written by --report)
Running the same command again skips finished boxes and resumes cut-off ones.
"""
import argparse
import csv
import gc
import os
import re
import sys
import time
from pathlib import Path

import numpy as np

p = argparse.ArgumentParser()
p.add_argument("--ckpt", help="path to uma-s-1p2p1-ft-d4rev.pt")
p.add_argument("--inputs", default="inputs", help="folder of raw boxes")
p.add_argument("--fmax", type=float, default=0.05, help="force target, eV/A")
p.add_argument("--max-steps", type=int, default=5000, help="FIRE step cap per box, counted across chunks")
p.add_argument("--inference", default="nitro", help="fairchem inference preset")
p.add_argument("--device", default="cuda", choices=["cuda", "cpu"])
p.add_argument("--stop-at", type=float, default=0, help="unix time by which to save and stop")
p.add_argument("--report", action="store_true", help="only write relax_report.csv and exit")
a = p.parse_args()
os.environ.setdefault("TRITON_CACHE_DIR", f"/tmp/{os.environ.get('USER', 'u')}_triton")  # off $HOME

from ase.io import read, write  # noqa: E402

inputs = Path(a.inputs)
relaxed = Path("relaxed")
failed = relaxed / "FAILED"
work = Path("relax_work")
for d in (relaxed, failed, work):
    d.mkdir(parents=True, exist_ok=True)
gpu = os.environ.get("CUDA_VISIBLE_DEVICES", a.device)


def say(msg):  # one write per line
    sys.stdout.write(f"relax gpu {gpu}: {msg}\n")
    sys.stdout.flush()


def n_atoms(xyz):
    with open(xyz) as f:
        return int(f.readline())


boxes = sorted(inputs.glob("*.xyz"), key=lambda f: (-n_atoms(f), f.name))


def report():
    rows = []
    for xyz in sorted(inputs.glob("*.xyz")):
        name = xyz.stem
        row = {"system": name, "atoms": n_atoms(xyz), "status": "pending", "fire_steps": "", "fmax_eV_A": ""}
        if (relaxed / f"{name}.xyz").exists():
            info = read(relaxed / f"{name}.xyz").info
            row.update(status="relaxed", fire_steps=info["fire_steps"], fmax_eV_A=info["fmax_eV_A"])
        elif (failed / f"{name}.txt").exists():
            kv = dict(re.findall(r"(\w+)=(\S+)", (failed / f"{name}.txt").read_text()))
            row.update(status="failed", fire_steps=kv.get("fire_steps", ""), fmax_eV_A=kv.get("fmax_eV_A", ""))
        elif (work / f"{name}.npz").exists():
            row.update(status="in progress", fire_steps=int(np.load(work / f"{name}.npz")["steps"]))
        rows.append(row)
    with open("relax_report.tmp.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    os.replace("relax_report.tmp.csv", "relax_report.csv")
    counts = {s: sum(r["status"] == s for r in rows) for s in ("relaxed", "failed", "in progress", "pending")}
    print(f"relax_report.csv: {len(rows)} boxes, " + ", ".join(f"{v} {k}" for k, v in counts.items()))


if a.report:
    report()
    sys.exit(0)
if not a.ckpt:
    p.error("--ckpt is required unless --report is given")

from ase.optimize import FIRE  # noqa: E402
from fairchem.core import FAIRChemCalculator  # noqa: E402
from fairchem.core.units.mlip_unit import load_predict_unit  # noqa: E402


class TimeUp(Exception):
    pass


deadline = a.stop_at if a.stop_at else float("inf")


def clock():  # checked after every FIRE step
    if time.time() > deadline:
        raise TimeUp


def finished(name):
    return (relaxed / f"{name}.xyz").exists() or (failed / f"{name}.txt").exists()


def claim(name):  # one GPU per box; relax_boxes_nitro.sbatch clears stale claims each chunk
    try:
        os.mkdir(work / f"{name}.claim")
        return True
    except FileExistsError:
        return False


for xyz in boxes:
    name = xyz.stem
    if finished(name) or not claim(name):
        continue
    if time.time() > deadline:
        break
    atoms = read(xyz)
    atoms.pbc = True
    atoms.info["charge"] = int(atoms.info.get("charge", 0))
    atoms.info["spin"] = int(atoms.info.get("spin", 1))
    steps = 0
    if (work / f"{name}.npz").exists():
        r = np.load(work / f"{name}.npz")
        atoms.set_positions(r["positions"])
        steps = int(r["steps"])
    predictor = load_predict_unit(a.ckpt, inference_settings=a.inference, device=a.device)
    atoms.calc = FAIRChemCalculator(predictor, task_name="omol")
    try:
        atoms.get_forces()  # first call: compilation runs here
    except Exception as e:
        if "out of memory" in f"{e} {e.__context__}".lower():
            say(f"{name}: ran out of GPU memory; skipped this chunk (the 80 GB nodes are -C \"gpu&hbm80g\")")
            atoms.calc = None
            del predictor
            gc.collect()
            continue
        raise
    say(f"{name}: {len(atoms)} atoms, {'resuming after ' + str(steps) if steps else 'starting'} FIRE steps")
    opt = FIRE(atoms, logfile=str(work / f"{name}.log"))
    opt.attach(clock, interval=1)
    t0 = time.time()
    try:
        opt.run(fmax=a.fmax, steps=max(a.max_steps - steps, 0))
    except TimeUp:
        steps += opt.nsteps
        np.savez(work / f"{name}.tmp.npz", positions=atoms.get_positions(), steps=steps)
        os.replace(work / f"{name}.tmp.npz", work / f"{name}.npz")
        say(f"{name}: deadline reached after {steps} FIRE steps; the next chunk continues from relax_work/{name}.npz")
        break
    steps += opt.nsteps
    fmax = float(np.sqrt((atoms.get_forces() ** 2).sum(axis=1).max()))
    if fmax > a.fmax:
        (failed / f"{name}.txt").write_text(f"fmax_eV_A={fmax:.5f} fire_steps={steps}\n")
        say(f"{name}: failed to relax, fmax {fmax:.4f} eV/A after {steps} FIRE steps")
    else:
        box = read(xyz)  # keeps the input header (charge, spin, system_number, densities, run_T_K)
        box.set_positions(atoms.get_positions())
        box.info.update(fire_steps=steps, fmax_eV_A=round(fmax, 5))
        write(relaxed / f".{name}.tmp.xyz", box, format="extxyz")
        os.replace(relaxed / f".{name}.tmp.xyz", relaxed / f"{name}.xyz")
        say(f"{name}: relaxed, {steps} FIRE steps, fmax {fmax:.4f} eV/A, {time.time() - t0:.0f} s")
    (work / f"{name}.npz").unlink(missing_ok=True)
    atoms.calc = None
    del predictor, opt
    gc.collect()
    try:
        import torch

        torch.cuda.empty_cache()
    except Exception:
        pass
