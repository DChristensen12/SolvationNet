#!/usr/bin/env python3
"""One run of NPT MD with UMA uma-s-1p2p1-ft-d4rev (UMA Nitro), at 1 bar and the system's own temperature.

    python md_turbo.py --ckpt uma-s-1p2p1-ft-d4rev.pt --replica 0 --stop-at <unix time> inputs/079_DME-neat.xyz

Inference: with --gpus 1 the model runs on fairchem's "nitro" preset (single GPU). With
--gpus > 1 it runs on fairchem's "multigpu" preset (merged experts, torch.compile, TF32,
graph parallel over Ray), because Nitro is single GPU only. --inference overrides either.

Dynamics: isotropic Martyna-Tobias-Klein NPT (ase.md.nose_hoover_chain.IsotropicMTKNPT),
thermostat and barostat time constants 100 fs, 1 fs steps. The cell stays cubic; only its
volume changes. The target temperature is run_T_K from the input file's header unless
--temp is given.

A new run first minimizes the packed positions with FIRE at fixed cell (fmax 0.05 eV/A or
500 steps; --no-minimize skips this), then draws Maxwell-Boltzmann velocities with its own
seed. The integrator is deterministic, so the seed only sets the starting velocities.
Output in replicas/<system>/repRR/:
  md.traj   positions and cell every 1 ps
  md.log    time, energies, temperature, volume and density every 0.1 ps, from step 0
  ckpt.npz  restart point: positions, momenta, cell and the thermostat and barostat state
  DONE      written when --ps is reached; a larger --ps later continues past it
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
p.add_argument("--ckpt", required=True, help="path to uma-s-1p2p1-ft-d4rev.pt")
p.add_argument("--replica", type=int, required=True)
p.add_argument("--ps", type=float, default=100.0, help="simulated time per replica")
p.add_argument("--temp", type=float, default=None, help="K; overrides run_T_K from the input header")
p.add_argument("--dt", type=float, default=1.0, help="fs")
p.add_argument("--pressure", type=float, default=1.0, help="bar")
p.add_argument("--tdamp", type=float, default=100.0, help="thermostat time constant, fs")
p.add_argument("--pdamp", type=float, default=100.0, help="barostat time constant, fs")
p.add_argument("--no-minimize", dest="minimize", action="store_false",
               help="skip the FIRE minimization before the first MD step of a new run")
p.add_argument("--min-steps", type=int, default=500, help="FIRE step limit")
p.add_argument("--fmax", type=float, default=0.05, help="FIRE force target, eV/A")
p.add_argument("--gpus", type=int, default=4, help="GPUs this replica is spread over")
p.add_argument("--inference", default=None,
               help="fairchem inference preset; default nitro for 1 GPU, multigpu for more")
p.add_argument("--device", default="cuda", choices=["cuda", "cpu"])
p.add_argument("--stop-at", type=float, default=0, help="unix time by which to checkpoint and stop")
p.add_argument("--seed-base", type=int, default=2026)
a = p.parse_args()
if a.device == "cuda":
    os.environ["CUDA_VISIBLE_DEVICES"] = ",".join(str(i) for i in range(a.gpus))
os.environ.setdefault("TRITON_CACHE_DIR", f"/tmp/{os.environ.get('USER', 'u')}_triton")  # off $HOME

from ase import Atoms, units  # noqa: E402
from ase.io import read  # noqa: E402
from ase.io.trajectory import Trajectory  # noqa: E402
from ase.md.nose_hoover_chain import IsotropicMTKNPT  # noqa: E402
from ase.md.velocitydistribution import MaxwellBoltzmannDistribution, Stationary  # noqa: E402
from ase.optimize import FIRE  # noqa: E402
from fairchem.core import FAIRChemCalculator  # noqa: E402
from fairchem.core.units.mlip_unit import load_predict_unit  # noqa: E402

xyz = Path(a.xyz)
tag = f"{xyz.stem} rep{a.replica:02d}"
out = Path("replicas") / xyz.stem / f"rep{a.replica:02d}"
out.mkdir(parents=True, exist_ok=True)


def say(msg):  # one write per line
    sys.stdout.write(f"{tag}: {msg}\n")
    sys.stdout.flush()


n_total = int(round(a.ps * 1000 / a.dt))
if (out / "DONE").exists():
    done_steps = int((out / "DONE").read_text().split()[0])
    if done_steps >= n_total:
        say("already finished")
        sys.exit(0)
    (out / "DONE").unlink()  # --ps was raised: carry on from ckpt.npz
    say(f"extending from {done_steps * a.dt / 1000:g} ps to {a.ps:g} ps")

seed = zlib.crc32(f"{xyz.stem}-{a.replica}-{a.seed_base}".encode())
atoms = read(xyz)
atoms.pbc = True
atoms.info["charge"] = int(atoms.info.get("charge", 0))
atoms.info["spin"] = int(atoms.info.get("spin", 1))
if a.temp is not None:
    temp = a.temp
elif "run_T_K" in atoms.info:
    temp = float(atoms.info["run_T_K"])
else:
    say(f"{xyz} has no run_T_K in its header; pass --temp")
    sys.exit(2)
mass_g = atoms.get_masses().sum() * units._amu * 1e3


def density():  # g/cm3
    return mass_g / (atoms.get_volume() * 1e-24)


step = 0
z = None
if (out / "ckpt.npz").exists():
    z = np.load(out / "ckpt.npz")
    atoms.set_cell(z["cell"], scale_atoms=False)
    atoms.set_positions(z["positions"])
    atoms.set_momenta(z["momenta"])
    step = int(z["step"])
    if not np.isclose(float(z["temp_K"]), temp):
        say(f"warning: checkpoint was run at {float(z['temp_K']):g} K, continuing at {temp:g} K")
    say(f"continuing from {step * a.dt / 1000:.1f} ps")

settings = a.inference or ("nitro" if a.gpus == 1 else "multigpu")
predictor = load_predict_unit(a.ckpt, inference_settings=settings, device=a.device, workers=a.gpus)
atoms.calc = FAIRChemCalculator(predictor, task_name="omol")
if "stress" not in atoms.calc.implemented_properties:
    say(f"{a.ckpt} gives no stress for the omol task, so NPT cannot run; use the D4rev checkpoint")
    sys.exit(4)
try:
    atoms.get_forces()  # first call: Ray workers start and torch.compile runs here
except Exception as e:
    if "out of memory" in f"{e} {e.__context__}".lower():
        say(f"{settings} ran out of GPU memory on {a.gpus} GPUs; use the 80 GB nodes (-C \"gpu&hbm80g\")")
        sys.exit(3)
    raise
say(f"{len(atoms)} atoms, charge {atoms.info['charge']}, spin {atoms.info['spin']}, "
    f"{settings} on {a.gpus} GPUs, {temp:g} K, {a.pressure:g} bar, target {a.ps:g} ps")

if z is None:
    if a.minimize:
        opt = FIRE(atoms, logfile=str(out / "minimize.log"))
        opt.run(fmax=a.fmax, steps=a.min_steps)
        fmax = float(np.sqrt((atoms.get_forces() ** 2).sum(axis=1).max()))
        say(f"FIRE at fixed cell: {opt.nsteps} steps, final fmax {fmax:.4f} eV/A")
    try:  # ASE >= 3.29
        from ase.md.velocitydistribution import thermalize_momenta

        thermalize_momenta(atoms, temp, rng=np.random.default_rng(seed))
    except ImportError:
        MaxwellBoltzmannDistribution(atoms, temperature_K=temp, rng=np.random.default_rng(seed))
    Stationary(atoms)
    say(f"new replica, velocities drawn at {temp:g} K with seed {seed}, "
        f"starting density {density():.4f} g/cm3")

dyn = IsotropicMTKNPT(atoms, timestep=a.dt * units.fs, temperature_K=temp,
                      pressure_au=a.pressure * units.bar, tdamp=a.tdamp * units.fs,
                      pdamp=a.pdamp * units.fs)
if z is not None:  # integrator state, so the continued run is the same trajectory
    dyn._cell0 = z["cell0"]
    dyn._volume0 = float(z["volume0"])
    dyn._eps = float(z["eps"])
    dyn._p_eps = float(z["p_eps"])
    dyn._thermostat._eta = z["eta"].copy()
    dyn._thermostat._p_eta = z["p_eta"].copy()
    dyn._barostat._xi = z["xi"].copy()
    dyn._barostat._p_xi = z["p_xi"].copy()
    dyn._update_atoms()
dyn.nsteps = step

log = open(out / "md.log", "a")
if log.tell() == 0:
    log.write(f"{'Time[ps]':>10} {'Etot[eV]':>14} {'Epot[eV]':>14} {'Ekin[eV]':>12} {'T[K]':>8} "
              f"{'Volume[A3]':>12} {'Density[g/cm3]':>15}\n")


def md_log():
    epot = atoms.get_potential_energy()
    ekin = atoms.get_kinetic_energy()
    log.write(f"{dyn.nsteps * a.dt / 1000:10.4f} {epot + ekin:14.4f} {epot:14.4f} {ekin:12.4f} "
              f"{atoms.get_temperature():8.2f} {atoms.get_volume():12.3f} {density():15.5f}\n")
    log.flush()


dyn.attach(md_log, interval=100)
traj = Trajectory(str(out / "md.traj"), "a")


def save():
    np.savez(out / "ckpt.tmp.npz", positions=atoms.get_positions(), momenta=atoms.get_momenta(),
             cell=np.array(atoms.get_cell()), step=dyn.nsteps, temp_K=temp,
             cell0=dyn._cell0, volume0=dyn._volume0, eps=dyn._eps, p_eps=dyn._p_eps,
             eta=dyn._thermostat._eta, p_eta=dyn._thermostat._p_eta,
             xi=dyn._barostat._xi, p_xi=dyn._barostat._p_xi)
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
        sec = (time.time() - start) / max(dyn.nsteps - step, 1)
        say(f"{dyn.nsteps * a.dt / 1000:.1f} ps, T {atoms.get_temperature():.0f} K, "
            f"density {density():.4f} g/cm3, {sec:.3f} s/step = {0.0864 * a.dt / sec:.3f} ns/day")
save()
traj.close()
log.close()
if dyn.nsteps >= n_total:
    (out / "DONE").write_text(f"{dyn.nsteps} steps\n")
    say(f"finished {a.ps:g} ps")
else:
    say(f"checkpointed at {dyn.nsteps * a.dt / 1000:.1f} ps; the next chunk continues from here")
