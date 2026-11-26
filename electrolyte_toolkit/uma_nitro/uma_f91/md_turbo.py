#!/usr/bin/env python3
"""One replica of NVT MD with UMA uma-s-1p2p1 in turbo mode, spread over a node's GPUs.

    python md_turbo.py --ckpt uma-s-1p2p1.pt --replica 3 --stop-at <unix time> inputs/F91_TTE.xyz

Turbo is fairchem's "multigpu" preset (merged experts, torch.compile, TF32 tensor cores).
With --gpus 4 the system is split over four GPUs (graph parallel, uses Ray), so these
~8,000-atom cells fit in memory. Replica R starts from the snapshot's positions with
fresh Maxwell-Boltzmann velocities at --temp, drawn with its own seed; the thermostat
noise is seeded per replica as well. Output in replicas/<system>/repRR/:
  md.traj   positions every 1 ps        md.log  ASE MD log every 0.1 ps
  ckpt.npz  restart point               DONE    written when --ps is reached
  run.log   this script's output
Running the same command again continues from ckpt.npz.
"""
import argparse
import os
import sys
import time
import zlib
from pathlib import Path

import numpy as np

p = argparse.ArgumentParser()
p.add_argument("xyz")
p.add_argument("--ckpt", required=True, help="path to uma-s-1p2p1.pt")
p.add_argument("--replica", type=int, required=True)
p.add_argument("--ps", type=float, default=100.0, help="simulated time per replica")
p.add_argument("--temp", type=float, default=300.0, help="K")
p.add_argument("--dt", type=float, default=1.0, help="fs")
p.add_argument("--gpus", type=int, default=4, help="GPUs this replica is spread over")
p.add_argument("--stop-at", type=float, default=0, help="unix time by which to checkpoint and stop")
p.add_argument("--seed-base", type=int, default=2026)
a = p.parse_args()
os.environ["CUDA_VISIBLE_DEVICES"] = ",".join(str(i) for i in range(a.gpus))
os.environ.setdefault("TRITON_CACHE_DIR", f"/tmp/{os.environ.get('USER', 'u')}_triton")  # off $HOME

from ase import Atoms, units  # noqa: E402
from ase.io import read  # noqa: E402
from ase.io.trajectory import Trajectory  # noqa: E402
from ase.md import MDLogger  # noqa: E402
from ase.md.bussi import Bussi  # noqa: E402
from ase.md.velocitydistribution import MaxwellBoltzmannDistribution, Stationary  # noqa: E402
from fairchem.core import FAIRChemCalculator  # noqa: E402
from fairchem.core.units.mlip_unit import load_predict_unit  # noqa: E402

xyz = Path(a.xyz)
tag = f"{xyz.stem} rep{a.replica:02d}"
out = Path("replicas") / xyz.stem / f"rep{a.replica:02d}"
out.mkdir(parents=True, exist_ok=True)


def say(msg):  # one write per line
    sys.stdout.write(f"{tag}: {msg}\n")
    sys.stdout.flush()


if (out / "DONE").exists():
    say("already finished")
    sys.exit(0)

seed = zlib.crc32(f"{xyz.stem}-{a.replica}-{a.seed_base}".encode())
atoms = read(xyz)
atoms.info["charge"] = int(atoms.info.get("charge", 0))
atoms.info["spin"] = int(atoms.info.get("spin", 1))
n_total = int(round(a.ps * 1000 / a.dt))
step = 0
if (out / "ckpt.npz").exists():
    z = np.load(out / "ckpt.npz")
    atoms.set_positions(z["positions"])
    atoms.set_momenta(z["momenta"])
    step = int(z["step"])
    say(f"continuing from {step * a.dt / 1000:.1f} ps")
else:
    try:  # ASE >= 3.29
        from ase.md.velocitydistribution import thermalize_momenta

        thermalize_momenta(atoms, a.temp, rng=np.random.default_rng(seed))
    except ImportError:
        MaxwellBoltzmannDistribution(atoms, temperature_K=a.temp, rng=np.random.default_rng(seed))
    Stationary(atoms)
    say(f"new replica, velocities drawn at {a.temp} K with seed {seed}")

predictor = load_predict_unit(a.ckpt, inference_settings="multigpu", device="cuda", workers=a.gpus)
atoms.calc = FAIRChemCalculator(predictor, task_name="omol")
try:
    atoms.get_forces()  # first call: Ray workers start and torch.compile runs here
except Exception as e:
    if "out of memory" in f"{e} {e.__context__}".lower():
        say(f"turbo ran out of GPU memory on {a.gpus} GPUs; use the 80 GB nodes (-C \"gpu&hbm80g\")")
        sys.exit(3)
    raise
say(f"{len(atoms)} atoms, charge {atoms.info['charge']}, spin {atoms.info['spin']}, "
    f"turbo on {a.gpus} GPUs, target {a.ps:g} ps")

dyn = Bussi(atoms, timestep=a.dt * units.fs, temperature_K=a.temp, taut=100 * units.fs,
            rng=np.random.default_rng([seed, step]))
dyn.nsteps = step
dyn.attach(MDLogger(dyn, atoms, str(out / "md.log"), header=(step == 0), mode="a"), interval=100)
traj = Trajectory(str(out / "md.traj"), "a")


def save():
    np.savez(out / "ckpt.tmp.npz", positions=atoms.get_positions(), momenta=atoms.get_momenta(), step=dyn.nsteps)
    os.replace(out / "ckpt.tmp.npz", out / "ckpt.npz")


def frame():
    f = Atoms(atoms.numbers, positions=atoms.get_positions(), cell=atoms.cell, pbc=True)
    f.info["time_ps"] = round(dyn.nsteps * a.dt / 1000, 6)
    traj.write(f)
    save()


class TimeUp(Exception):
    pass


start = time.time()
deadline = a.stop_at if a.stop_at else float("inf")


def clock():  # checked after every MD step
    if time.time() > deadline:
        raise TimeUp


if step == 0:
    frame()
dyn.attach(clock, interval=1)
while dyn.nsteps < n_total and time.time() < deadline:
    try:
        dyn.run(min(100 - dyn.nsteps % 100, n_total - dyn.nsteps))  # 0.1 ps blocks
    except TimeUp:
        break
    if dyn.nsteps % 1000 == 0:
        frame()
    if dyn.nsteps - step <= 1000 or dyn.nsteps % 1000 == 0:
        sec = (time.time() - start) / (dyn.nsteps - step)
        say(f"{dyn.nsteps * a.dt / 1000:.1f} ps, T {atoms.get_temperature():.0f} K, "
            f"{sec:.3f} s/step = {0.0864 * a.dt / sec:.3f} ns/day")
save()
traj.close()
if dyn.nsteps >= n_total:
    (out / "DONE").write_text(f"{dyn.nsteps} steps\n")
    say(f"finished {a.ps:g} ps")
else:
    say(f"checkpointed at {dyn.nsteps * a.dt / 1000:.1f} ps; the next chunk continues from here")
