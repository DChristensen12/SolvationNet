#!/usr/bin/env python3
"""Perlmutter batch submission for molten-arc molten salt simulations.

Part of BACON — Battery Architectures via Computational Observation of Nonaqueous salts

Thin wrapper around tools/perlmutter/perlmutter.py with molten-salt defaults.
Knows the salt systems, temperatures, and density estimates so you don't have
to specify everything manually.

Usage
-----
    # Submit a batch equilibration campaign
    python submit.py campaign create my_salt_run \\
        --inputs "data/packed/*.pdb" \\
        --temp 393 --steps 100000

    # Check on progress
    python submit.py status my_salt_run

    # Pull results
    python submit.py pull my_salt_run

    # Retry failures
    python submit.py retry my_salt_run
"""

import argparse
import os
import pathlib
import subprocess
import sys

PERLMUTTER_DIR = pathlib.Path(__file__).resolve().parent
MOLTEN_ARC_ROOT = PERLMUTTER_DIR.parent
REPO_ROOT = MOLTEN_ARC_ROOT.parent
PERLMUTTER_PY = REPO_ROOT / "tools" / "perlmutter" / "perlmutter.py"


def perlmutter(*args):
    """Forward a command to the main perlmutter.py."""
    cmd = [sys.executable, str(PERLMUTTER_PY)] + list(args)
    return subprocess.run(cmd, cwd=REPO_ROOT).returncode


def cmd_campaign_create(args):
    """Submit a molten salt equilibration campaign to Perlmutter."""
    if not PERLMUTTER_PY.exists():
        print(f"perlmutter.py not found at {PERLMUTTER_PY}")
        print("Make sure tools/perlmutter/ is set up.")
        return 1

    extra_args = f"--model uma --workflow npt --npt-steps {args.steps}"
    if args.temp:
        extra_args += f" --temperature {args.temp}"

    perlmutter_args = [
        "campaign", "create", args.name,
        "--workflow", "equilibrate",
        "--inputs",
    ] + args.inputs + [
        "--args", extra_args,
        "--time", args.time,
        "--qos", args.qos,
    ]

    if args.dry_run:
        perlmutter_args.append("--dry-run")

    return perlmutter(*perlmutter_args)


def cmd_status(args):
    """Check campaign status."""
    perlmutter_args = ["campaign", "status"]
    if args.name:
        perlmutter_args.append(args.name)
    return perlmutter(*perlmutter_args)


def cmd_retry(args):
    """Retry failed tasks in a campaign."""
    perlmutter_args = ["campaign", "retry", args.name]
    if args.dry_run:
        perlmutter_args.append("--dry-run")
    return perlmutter(*perlmutter_args)


def cmd_pull(args):
    """Pull results from a campaign."""
    perlmutter_args = ["pull", args.name]
    if args.output:
        perlmutter_args.extend(["-o", args.output])
    if args.force:
        perlmutter_args.append("--force")
    return perlmutter(*perlmutter_args)


def main():
    parser = argparse.ArgumentParser(
        description="Perlmutter batch runner for molten-arc",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd")

    # campaign create
    p = sub.add_parser("create", help="submit equilibration campaign")
    p.add_argument("name", help="campaign name")
    p.add_argument("--inputs", nargs="+", required=True,
                    help="input file globs (e.g. '../data/packed/*.pdb')")
    p.add_argument("--temp", type=float, default=None,
                    help="temperature in K")
    p.add_argument("--steps", type=int, default=100000,
                    help="NPT steps (default: 100000)")
    p.add_argument("--time", default="04:00:00", help="SLURM wall time")
    p.add_argument("--qos", default="regular", choices=["regular", "debug", "preempt"])
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_campaign_create)

    # status
    p = sub.add_parser("status", help="check campaign progress")
    p.add_argument("name", nargs="?", help="campaign name (omit for all)")
    p.set_defaults(func=cmd_status)

    # retry
    p = sub.add_parser("retry", help="retry failed tasks")
    p.add_argument("name", help="campaign name")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_retry)

    # pull
    p = sub.add_parser("pull", help="download results")
    p.add_argument("name", help="campaign name")
    p.add_argument("-o", "--output", help="local output directory")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_pull)

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main() or 0)
