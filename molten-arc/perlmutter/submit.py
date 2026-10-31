#!/usr/bin/env python3
"""Perlmutter batch submission for molten-arc molten salt simulations.

Part of BACON, Battery Architectures via Computational Observation of Nonaqueous salts

Thin wrapper around tools/perlmutter/perlmutter.py with molten-salt defaults.
Knows the salt systems, temperatures, and density estimates so you don't have
to specify everything manually.

Usage
-----
    # Submit using a named system (auto-fills temperature)
    python submit.py create licl_kcl_run \\
        --system LiCl-KCl \\
        --inputs "../data/packed/LiCl-KCl*.xyz"

    # Submit with explicit temperature
    python submit.py create mgcl2_run \\
        --inputs "../data/packed/MgCl2*.xyz" \\
        --temp 973

    # Check on progress
    python submit.py status licl_kcl_run

    # Pull results
    python submit.py pull licl_kcl_run

    # Retry failures
    python submit.py retry licl_kcl_run
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

sys.path.insert(0, str(MOLTEN_ARC_ROOT / "scripts"))
from molten_salt_systems import ELECTROLYTE_SYSTEMS


def _resolve_temperature(args):
    """Get temperature from --temp, or auto-fill from --system."""
    if args.temp is not None:
        return args.temp

    system_name = getattr(args, "system", None)
    if system_name:
        if system_name not in ELECTROLYTE_SYSTEMS:
            matches = [k for k in ELECTROLYTE_SYSTEMS if system_name.lower() in k.lower()]
            if len(matches) == 1:
                system_name = matches[0]
            else:
                print(f"Unknown system: {system_name}")
                print(f"Available: {', '.join(ELECTROLYTE_SYSTEMS.keys())}")
                sys.exit(1)
        temp_C = ELECTROLYTE_SYSTEMS[system_name]["working_temp_C"]
        temp_K = temp_C + 273.15
        print(f"System {system_name}: auto-set temperature to {temp_K:.0f} K ({temp_C} °C)")
        return temp_K

    print("ERROR: Provide --temp or --system to set the temperature.")
    sys.exit(1)


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

    temp_K = _resolve_temperature(args)

    extra_args = (
        f"--model uma --workflow nvt+npt"
        f" --temperature {temp_K:.0f}"
        f" --nvt-steps {args.nvt_steps}"
        f" --npt-steps {args.npt_steps}"
    )

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

    print(f"\nSubmitting: {args.name}")
    print(f"  Model: UMA (turbo)")
    print(f"  Workflow: NVT ({args.nvt_steps} steps) → NPT ({args.npt_steps} steps)")
    print(f"  Temperature: {temp_K:.0f} K")
    print(f"  Inputs: {args.inputs}")
    print()

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
        description="BACON, Perlmutter batch runner for molten-arc",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd")

    # campaign create
    p = sub.add_parser("create", help="submit NVT+NPT equilibration campaign")
    p.add_argument("name", help="campaign name")
    p.add_argument("--system",
                    help="salt system name (auto-fills temperature from database)")
    p.add_argument("--inputs", nargs="+", required=True,
                    help="input file globs (e.g. '../data/packed/*.xyz')")
    p.add_argument("--temp", type=float, default=None,
                    help="temperature in K (overrides --system)")
    p.add_argument("--nvt-steps", type=int, default=50000,
                    help="NVT warmup steps (default: 50000)")
    p.add_argument("--npt-steps", type=int, default=100000,
                    help="NPT production steps (default: 100000)")
    p.add_argument("--time", default="06:00:00",
                    help="SLURM wall time (default: 06:00:00)")
    p.add_argument("--qos", default="regular",
                    choices=["regular", "debug", "preempt"])
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
