#!/usr/bin/env python3
"""Runs every campaign box through NPT with UMA Nitro (UMA-S-1.2.1-FT-D4rev). 

Each box is handed to equilibrate.py as its own process, so a crash costs one
system and not the campaign. Boxes with a final structure are skipped, and
boxes with a checkpoint resume from it.

    python electrolyte_toolkit/run_nitro_npt.py --input-dir ./nitro_campaign
    python electrolyte_toolkit/run_nitro_npt.py --status
"""

import argparse
import glob
import os
import subprocess
import sys
import time

DEFAULT_CHECKPOINT_DIR = os.path.join(os.path.expanduser("~"), "electrolyte_equilibration")
EQUILIBRATE_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "equilibrate.py")

CAMPAIGN_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "data", "na-electrolyte-solvation-boxes", "nitro_campaign",
)


def find_boxes(input_dir):
    """Maps system name to its box, one subdirectory per system."""
    boxes = {}
    for subdir in sorted(os.listdir(input_dir)):
        subpath = os.path.join(input_dir, subdir)
        if not os.path.isdir(subpath):
            continue
        xyz = os.path.join(subpath, f"{subdir}.xyz")
        if os.path.isfile(xyz):
            boxes[subdir] = xyz
    return boxes


def is_done(name, checkpoint_dir):
    final = os.path.join(checkpoint_dir, name, f"{name}.xyz")
    return os.path.isfile(final)


def has_checkpoint(name, checkpoint_dir):
    d = os.path.join(checkpoint_dir, name)
    return bool(glob.glob(os.path.join(d, "ckpt_*.npz")))


def run_box(name, xyz_path, checkpoint_dir, npt_steps, device):
    """Runs or resumes one box, resuming when xyz_path is None."""
    if xyz_path is None:
        where = ["--resume", name]
    else:
        where = [xyz_path, "--name", name]

    cmd = [
        sys.executable, EQUILIBRATE_SCRIPT,
        *where,
        "--model", "uma_nitro",
        "--workflow", "npt",
        "--npt-steps", str(npt_steps),
        "--checkpoint-dir", checkpoint_dir,
        "--device", device,
    ]

    print(f"\n{name}, {'resuming' if xyz_path is None else xyz_path}")
    print(f"  {' '.join(cmd)}\n")

    t0 = time.time()
    result = subprocess.run(cmd)
    elapsed = time.time() - t0

    status = "ok" if result.returncode == 0 else f"failed, exit {result.returncode}"
    print(f"\n{name}: {status} ({elapsed / 60:.1f} min)")
    return result.returncode == 0


def main(input_dir, checkpoint_dir, only, npt_steps, device, status, resume_all):
    if status:
        subprocess.run([sys.executable, EQUILIBRATE_SCRIPT, "--status",
                        "--checkpoint-dir", checkpoint_dir])
        return

    if resume_all:
        if not os.path.isdir(checkpoint_dir):
            print(f"no checkpoint directory at {checkpoint_dir}")
            return
        resumed = 0
        for name in sorted(os.listdir(checkpoint_dir)):
            if is_done(name, checkpoint_dir) or not has_checkpoint(name, checkpoint_dir):
                continue
            run_box(name, None, checkpoint_dir, npt_steps, device)
            resumed += 1
        print(f"\nResumed {resumed} interrupted runs")
        return

    input_dir = os.path.abspath(input_dir)
    boxes = find_boxes(input_dir)
    if not boxes:
        print(f"no boxes in {input_dir}/, run build_nitro_boxes.py first")
        return

    if only:
        boxes = {k: v for k, v in boxes.items() if k in only}
        unknown = set(only) - set(boxes)
        if unknown:
            print(f"not found: {', '.join(sorted(unknown))}")

    done = [n for n in boxes if is_done(n, checkpoint_dir)]
    pending = [n for n in boxes if n not in done]

    print(f"Found {len(boxes)} boxes, {len(done)} done and {len(pending)} pending")
    print("Model:      uma_nitro (UMA-S-1.2.1-FT-D4rev)")
    print(f"Workflow:   NPT, {npt_steps} steps")
    print(f"Checkpoint: {checkpoint_dir}")
    print(f"Device:     {device}")

    if not pending:
        print("\nNothing left to run")
        return

    print(f"\nRunning {len(pending)} boxes:")
    for name in pending:
        print(f"  {name} ({'resume' if has_checkpoint(name, checkpoint_dir) else 'fresh'})")

    succeeded, failed = 0, 0
    t_total = time.time()

    for name in pending:
        # A checkpoint carries the box with it, so resume ignores the input file
        xyz_path = None if has_checkpoint(name, checkpoint_dir) else boxes[name]
        if run_box(name, xyz_path, checkpoint_dir, npt_steps, device):
            succeeded += 1
        else:
            failed += 1

    elapsed = time.time() - t_total
    print(f"\nCampaign done, {succeeded} succeeded and {failed} failed "
          f"({elapsed / 60:.1f} min total)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", default=CAMPAIGN_DIR,
                        help="Directory holding the built boxes.")
    parser.add_argument("--checkpoint-dir", default=DEFAULT_CHECKPOINT_DIR,
                        help="Where equilibrate.py keeps its checkpoints.")
    parser.add_argument("--only", nargs="+", metavar="NAME",
                        help="Run only these systems.")
    parser.add_argument("--npt-steps", type=int, default=100000,
                        help="NPT steps per box, 100000 is 100 ps at 1 fs.")
    parser.add_argument("--device", default="cuda", choices=["cuda", "cpu"])

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--status", action="store_true",
                      help="Print status and exit.")
    mode.add_argument("--resume-all", action="store_true",
                      help="Resume every interrupted run.")
    _args = parser.parse_args()
    main(**vars(_args))
