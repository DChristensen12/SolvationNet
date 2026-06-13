""" utils.py is the shared utilities for the electrolyte MD toolkit.

It contains constants, atomic data, PDB parsing,
calculator setup, and project directory layout.
Every other script imports from here.
"""

import os

# --------------------------------------------------------------------------- #
#  Physical constants
# --------------------------------------------------------------------------- #
AVOGADRO = 6.02214076e23
AMU_TO_GRAMS = 1.66053906660e-24  # 1 amu in grams
ATM_TO_GPA = 1.01325e-4           # 1 atm in GPa
ATM_TO_EV_A3 = 1.01325e-4 / 160.2176634  # 1 atm in eV/Å³

# --------------------------------------------------------------------------- #
#  Simulation defaults
# --------------------------------------------------------------------------- #
DEFAULT_MODEL = "orb_v3_conservative_omol"
DEFAULT_TIMESTEP_FS = 1.0   # femtoseconds
DEFAULT_TRAJ_INTERVAL = 100
DEFAULT_PROP_INTERVAL = 10

# --------------------------------------------------------------------------- #
#  Atomic masses (amu)
# --------------------------------------------------------------------------- #
ATOMIC_MASSES = {
    "H": 1.008, "He": 4.003, "Li": 6.941, "Be": 9.012, "B": 10.81,
    "C": 12.011, "N": 14.007, "O": 15.999, "F": 18.998, "Ne": 20.180,
    "Na": 22.990, "Mg": 24.305, "Al": 26.982, "Si": 28.086, "P": 30.974,
    "S": 32.065, "Cl": 35.453, "Ar": 39.948, "K": 39.098, "Ca": 40.078,
    "Ti": 47.867, "V": 50.942, "Cr": 51.996, "Mn": 54.938, "Fe": 55.845,
    "Co": 58.933, "Ni": 58.693, "Cu": 63.546, "Zn": 65.380, "Br": 79.904,
    "I": 126.904, "Cs": 132.905, "Ba": 137.327,
}


# --------------------------------------------------------------------------- #
#  Concentration / mass helpers
# --------------------------------------------------------------------------- #

def concentration_to_count(conc_mol_per_L: float, box_size_angstrom: float) -> int:
    """Convert molar concentration + cubic box edge length to molecule count.

    N = c * L^3 * 6.022e-4  (L in angstroms, c in mol/L)
    """
    n = conc_mol_per_L * (box_size_angstrom ** 3) * 6.02214076e-4
    return max(1, round(n))


def total_mass_amu(elements: list[str]) -> float:
    return sum(ATOMIC_MASSES.get(e, 12.0) for e in elements)


def total_mass_grams(elements: list[str]) -> float:
    return total_mass_amu(elements) * AMU_TO_GRAMS


# --------------------------------------------------------------------------- #
#  PDB helpers
# --------------------------------------------------------------------------- #

def parse_pdb_elements(pdb_path: str) -> list[str]:
    """Extract element symbols from ATOM/HETATM records in a PDB file."""
    elements = []
    with open(pdb_path) as f:
        for line in f:
            if not line.startswith(("ATOM", "HETATM")):
                continue
            elem = ""
            if len(line) >= 78:
                elem = line[76:78].strip()
            if not elem:
                atom_name = line[12:16].strip()
                for i, ch in enumerate(atom_name):
                    if ch.isalpha():
                        candidate = atom_name[i:]
                        break
                else:
                    candidate = atom_name
                if len(candidate) >= 2 and candidate[:2] in ATOMIC_MASSES:
                    elem = candidate[:2]
                elif len(candidate) >= 1 and candidate[0] in ATOMIC_MASSES:
                    elem = candidate[0]
            if elem:
                elements.append(elem)
    return elements


def add_cryst1_to_pdb(pdb_path: str, box_size: float):
    """Prepend a CRYST1 record to a PDB file for periodic boundary conditions."""
    cryst1 = (
        f"CRYST1{box_size:9.3f}{box_size:9.3f}{box_size:9.3f}"
        f"  90.00  90.00  90.00 P 1           1\n"
    )
    with open(pdb_path) as f:
        content = f.read()
    if content.startswith("CRYST1"):
        lines = content.split("\n")
        lines[0] = cryst1.rstrip()
        content = "\n".join(lines)
    else:
        content = cryst1 + content
    with open(pdb_path, "w") as f:
        f.write(content)


def parse_molecule_spec(spec_str: str, box_size: float) -> tuple[str, str, int]:
    """Parse a molecule specification string 'name:path:amount'.

    amount can be:
      - An integer (explicit count)
      - A float followed by 'M' (molar concentration)

    Returns (name, path, count).
    """
    parts = spec_str.split(":")
    if len(parts) != 3:
        raise ValueError(
            f"Molecule spec must be 'name:path:amount', got: {spec_str}"
        )
    name, path, amount = parts

    if amount.upper().endswith("M"):
        conc = float(amount[:-1])
        count = concentration_to_count(conc, box_size)
    else:
        count = int(amount)

    return name, path, count


# --------------------------------------------------------------------------- #
#  Calculator factory
# --------------------------------------------------------------------------- #

def get_calculator(model: str = DEFAULT_MODEL, device: str | None = None):
    """Create an ASE calculator for ML-potential MD.

    Supports orb-models (default) and MACE.  Edit this function or
    pass your own calculator to run_md if you use a different potential.

    Install the backend you need:
        pip install orb-models     # OMol potential (recommended for electrolytes)
        pip install mace-torch     # MACE foundation model
    """
    import torch
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        if device == "cpu":
            print("WARNING: No CUDA GPU detected — MD will be slow on CPU.")

    # --- orb-models ---
    if "orb" in model:
        try:
            from orb_models.forcefield import pretrained
            from orb_models.forcefield.calculator import ORBCalculator
        except ImportError:
            raise ImportError(
                "orb-models is not installed.\n"
                "  pip install orb-models\n"
                "  See https://github.com/orbital-materials/orb-models"
            )
        model_name = model.replace("-", "_")
        loader = getattr(pretrained, model_name, None)
        if loader is None:
            available = [a for a in dir(pretrained) if a.startswith("orb")]
            raise ValueError(
                f"Unknown model '{model_name}'. Available:\n  "
                + "\n  ".join(available)
            )
        orbff = loader(device=device)
        calc = ORBCalculator(orbff, device=device)
        print(f"Calculator: orb-models / {model_name} on {device}")
        return calc

    # --- MACE ---
    if "mace" in model:
        try:
            from mace.calculators import mace_mp
        except ImportError:
            raise ImportError(
                "mace-torch is not installed.\n"
                "  pip install mace-torch"
            )
        calc = mace_mp(model=model, device=device, default_dtype="float64")
        print(f"Calculator: MACE / {model} on {device}")
        return calc

    raise ValueError(
        f"Unknown model family: {model}\n"
        "Supported prefixes: 'orb' (orb-models), 'mace' (mace-torch).\n"
        "Or edit utils.get_calculator() to add your own."
    )


# --------------------------------------------------------------------------- #
#  Project directory layout
# --------------------------------------------------------------------------- #

class ProjectLayout:
    """Standard directory layout for this electrolyte MD project.

        inputs/      — Avogadro PDB files
        packed/      — packed cell output
        nvt/         — NVT equilibration (trajectory.traj, md.log, final.xyz)
        npt/         — NPT equilibration
        anneal/      — annealing equilibration
        analysis/    — equilibration diagnostic plots
        vmd/         — VMD-ready trajectory exports
    """

    SUBDIRS = ("inputs", "packed", "nvt", "npt", "anneal", "analysis", "vmd")

    def __init__(self, root: str):
        self.root = root

    @property
    def inputs(self) -> str:
        return os.path.join(self.root, "inputs")

    @property
    def packed_pdb(self) -> str:
        return os.path.join(self.root, "packed", "system.pdb")

    def equilibration_dir(self, protocol: str) -> str:
        return os.path.join(self.root, protocol)

    def trajectory(self, protocol: str) -> str:
        return os.path.join(self.root, protocol, "trajectory.traj")

    def md_log(self, protocol: str) -> str:
        return os.path.join(self.root, protocol, "md.log")

    def final_structure(self, protocol: str) -> str:
        return os.path.join(self.root, protocol, "final.xyz")

    @property
    def analysis(self) -> str:
        return os.path.join(self.root, "analysis")

    @property
    def vmd(self) -> str:
        return os.path.join(self.root, "vmd")

    def vmd_trajectory(self, fmt: str = "xyz") -> str:
        return os.path.join(self.root, "vmd", f"trajectory.{fmt}")

    def ensure_dirs(self):
        for d in self.SUBDIRS:
            os.makedirs(os.path.join(self.root, d), exist_ok=True)

    def summary(self) -> str:
        lines = [f"Project root: {self.root}"]
        for d in self.SUBDIRS:
            lines.append(f"  {d + '/':12s} → {os.path.join(self.root, d)}")
        return "\n".join(lines)
