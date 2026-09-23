"""Molten salt electrolyte and synthesis systems for batteries.

codename: BACON — Battery Architectures via Computational Observation of Nonaqueous salts

Curated from Liu et al., Materials Today 60 (2022) 128-157.
Each entry carries the composition, working temperature, target application,
and physical properties needed to set up MD boxes.

Usage
-----
    from molten_salt_systems import ELECTROLYTE_SYSTEMS, SYNTHESIS_SALTS
    system = ELECTROLYTE_SYSTEMS["NaAlCl4"]
    print(system["description"])
    print(system["components"])
"""


# ---------------------------------------------------------------------------
# Molar masses of the salt species we care about (g/mol)
# ---------------------------------------------------------------------------
SALT_MOLAR_MASSES = {
    "LiCl":   42.394,
    "NaCl":   58.443,
    "KCl":    74.551,
    "CaCl2": 110.984,
    "BaCl2": 208.233,
    "MgCl2":  95.211,
    "AlCl3": 133.341,
    "LiF":    25.939,
    "LiI":   133.845,
    "LiBr":   86.845,
    "LiNO3":  68.946,
    "LiOH":   23.948,
    "KF":     58.097,
    "NaF":    41.988,
    "CsCl":  168.358,
    "KI":    166.003,
    "Li2CO3": 73.891,
    "Na2CO3":105.989,
    "K2CO3": 138.205,
    "Li2SO4":109.945,
    "Na2SO4":142.042,
    "ZnCl2": 136.286,
}


# ---------------------------------------------------------------------------
# Approximate densities of select molten salts near their working temps (g/cm^3)
# From Janz et al. NIST molten salt databases and other standard refs.
# These are rough — real densities shift with temperature and mixing.
# ---------------------------------------------------------------------------
MOLTEN_SALT_DENSITIES = {
    "LiCl":   1.502,   # at 700 °C
    "NaCl":   1.556,   # at 850 °C
    "KCl":    1.527,   # at 800 °C
    "CaCl2":  2.085,   # at 782 °C
    "MgCl2":  1.680,   # at 714 °C
    "AlCl3":  1.314,   # at 200 °C (low-melting)
    "LiF":    1.810,   # at 870 °C
    "NaF":    2.080,   # at 1000 °C
    "KF":     2.480,   # at 858 °C
    "LiBr":   2.528,   # at 552 °C
    "LiI":    3.109,   # at 469 °C
    "BaCl2":  3.150,   # at 963 °C
    "ZnCl2":  2.540,   # at 300 °C
    "LiNO3":  1.781,   # at 264 °C
    "LiOH":   1.460,   # at 462 °C
}


# ---------------------------------------------------------------------------
# Melting points (°C) of single-component salts
# ---------------------------------------------------------------------------
MELTING_POINTS = {
    "LiCl":   605,
    "NaCl":   801,
    "KCl":    770,
    "CaCl2":  782,
    "BaCl2":  963,
    "MgCl2":  714,
    "AlCl3":  192,
    "LiF":    845,
    "NaF":    996,
    "KF":     858,
    "LiBr":   552,
    "LiI":    449,
    "LiNO3":  253,
    "LiOH":   462,
    "CsCl":   645,
    "ZnCl2":  290,
    "Li2CO3": 723,
    "Na2CO3": 851,
    "K2CO3":  891,
}


# ===================================================================
#  ELECTROLYTE SYSTEMS (Table 3 from Liu et al. 2022)
#  These are molten salts used *as electrolytes* in AIBs, LMBs, MABs
# ===================================================================

ELECTROLYTE_SYSTEMS = {

    # ---- Aluminium-ion batteries (AIBs) ----

    "NaAlCl4": {
        "description": "Binary AlCl3-NaCl electrolyte for aluminium-ion batteries",
        "application": "AIB",
        "components": {"AlCl3": 62, "NaCl": 48},   # mol%
        "working_temp_C": 120,
        "voltage_window_V": (0.5, 2.27),
        "ionic_conductivity_S_cm": 0.2,
        "notes": "Coexisted AlCl4- and Al2Cl7- anions. Intercalation into graphite.",
        "ref": "Song et al., J. Mater. Chem. A 5 (2017) 1282",
    },

    "AlCl3-NaCl-LiCl-KCl": {
        "description": "Quaternary chloride electrolyte, working below 100 °C for AIBs",
        "application": "AIB",
        "components": {"AlCl3": 56.7, "NaCl": 18.6, "LiCl": 18.2, "KCl": 6.5},
        "working_temp_C": 90,
        "voltage_window_V": (0.5, 2.35),
        "ionic_conductivity_S_cm": 0.2,
        "notes": "Eutectic mp below 75 °C. Low-temp AIB but Coulombic efficiency needs work.",
        "ref": "Tu et al., J. Alloys Compd. (2019) 153285",
    },

    "AlCl3-NaCl-KCl": {
        "description": "Ternary chloride electrolyte for low-temp AIBs",
        "application": "AIB",
        "components": {"AlCl3": 61, "NaCl": 26, "KCl": 13},
        "working_temp_C": 99,
        "voltage_window_V": (0.5, 2.3),
        "notes": "Practical heating via hot water bath. 2500 cycles at 1 A/g.",
        "ref": "Wang et al., Chem. Commun. 55 (2019) 2138",
    },

    # ---- Liquid metal batteries (LMBs) ----

    "LiCl-LiF": {
        "description": "Binary lithium chloride-fluoride for Li-based LMBs",
        "application": "LMB",
        "components": {"LiCl": 70, "LiF": 30},
        "working_temp_C": 550,
        "voltage_window_V": (0.35, 1.1),
        "notes": "Used with Li negative electrode. High-temp system.",
        "ref": "Ning et al., J. Power Sources 275 (2015) 370",
    },

    "LiCl-LiI": {
        "description": "Binary lithium chloride-iodide for Li||Bi LMBs",
        "application": "LMB",
        "components": {"LiCl": 36, "LiI": 64},
        "working_temp_C": 410,
        "voltage_window_V": (0.3, 1.1),
        "notes": "Li||Bi cell, 54.7 Ah theoretical. Li3Bi alloy at positive electrode.",
        "ref": "Kim et al., J. Power Sources 377 (2018) 87",
    },

    "LiCl-NaCl-CaCl2": {
        "description": "Ternary chloride for Ca-based LMBs",
        "application": "LMB",
        "components": {"LiCl": 38, "NaCl": 27, "CaCl2": 35},
        "working_temp_C": 600,
        "voltage_window_V": (0.7, 1.2),
        "notes": "Used with Ca-Bi or Ca-Sb positive electrodes.",
        "ref": "Kim et al., J. Power Sources 241 (2013) 239",
    },

    "LiCl-NaCl-CaCl2-BaCl2": {
        "description": "Quaternary chloride for LMBs, higher discharge capacity",
        "application": "LMB",
        "components": {"LiCl": 29, "NaCl": 20, "CaCl2": 35, "BaCl2": 16},
        "working_temp_C": 600,
        "voltage_window_V": (0.7, 1.2),
        "notes": "Higher capacity than ternary thanks to Ba solubility in Bi.",
        "ref": "Kim et al., J. Power Sources 241 (2013) 239",
    },

    "MgCl2-NaCl-KCl": {
        "description": "Ternary chloride for Mg-based LMBs",
        "application": "LMB",
        "components": {"MgCl2": 50, "NaCl": 30, "KCl": 20},
        "working_temp_C": 700,
        "voltage_window_V": (0.1, 1.2),
        "notes": "Mg||Sb system. Mg is earth-abundant.",
        "ref": "Bradwell et al., JACS 134 (2012) 1895",
    },

    "LiCl-NaCl-KCl": {
        "description": "Ternary lithium-sodium-potassium chloride for Na-based LMBs",
        "application": "LMB",
        "components": {"LiCl": 59, "NaCl": 5, "KCl": 36},
        "working_temp_C": 450,
        "voltage_window_V": (0.5, 0.95),
        "ionic_conductivity_S_cm": 1.3,
        "notes": "Na negative electrode, Zn-Sn positive.",
        "ref": "Zhou et al., Energy Storage Mater. 50 (2022) 572",
    },

    "LiF-LiCl-LiBr": {
        "description": "Ternary lithium halide for Li||Sb-Pb LMBs",
        "application": "LMB",
        "components": {"LiF": 22, "LiCl": 31, "LiBr": 47},
        "working_temp_C": 500,
        "voltage_window_V": (0.2, 1.2),
        "notes": "Sb-Pb positive electrode prepared by molten sulphide electrolysis.",
        "ref": "Li et al., J. Clean. Prod. 312 (2021) 127779",
    },

    # ---- Molten-air batteries (MABs) ----

    "Li2CO3-Na2CO3-K2CO3-LiOH": {
        "description": "Quaternary carbonate-hydroxide for iron molten-air batteries",
        "application": "MAB",
        "components": {"Li2CO3": 24.6, "Na2CO3": 17.8, "K2CO3": 14.1, "LiOH": 43.5},
        "working_temp_C": 500,
        "voltage_window_V": (0.7, 1.6),
        "notes": "Fe electrode, Ni air electrode. O2- conductor.",
        "ref": "Cui et al., Sustain. Energy Fuels 1 (2017) 474",
    },
}


# ===================================================================
#  SYNTHESIS SALTS — used as reaction media for electrode preparation
# ===================================================================

SYNTHESIS_SALTS = {

    "KCl": {
        "description": "Single-component flux for cathode/anode crystal growth",
        "mp_C": 770,
        "typical_temp_C": (800, 1000),
        "applications": [
            "LiCoO2 polyhedra",
            "NCM-333 single crystals",
            "Li-rich layered oxides",
            "LiFePO4 microspheres",
            "N-doped carbon nanosheets",
        ],
    },

    "NaCl-KCl": {
        "description": "Binary chloride flux, popular for spinel and phosphate synthesis",
        "components": {"NaCl": 50, "KCl": 50},
        "mp_C": 657,
        "typical_temp_C": (700, 900),
        "applications": [
            "LiMn2O4 microspheres",
            "LiNi0.5Mn1.5O4 microspheres",
            "LiFePO4 well-defined crystals",
            "NiFe2O4 nanoplates",
        ],
    },

    "LiNO3-LiOH": {
        "description": "Low-melting binary for layered oxide synthesis and recycling",
        "components": {"LiNO3": 62, "LiOH": 38},
        "mp_C": 183,
        "typical_temp_C": (250, 500),
        "applications": [
            "LiCoO2 nano-sheets and nano-petals",
            "NCM-811 single crystals",
            "TiO2 nanoparticles",
            "Li-rich nanoplate synthesis",
        ],
    },

    "LiNO3-LiCl": {
        "description": "Binary lithium flux for ion exchange and nanostructured oxides",
        "components": {"LiNO3": 88, "LiCl": 12},
        "mp_C": 244,
        "typical_temp_C": (280, 400),
        "applications": [
            "O2/O4-type LLOs by ion exchange (400 mAh/g!)",
            "Co3O4, CuO nanoparticles",
            "NCM cathodes from coprecipitated precursors",
        ],
    },

    "LiCl-KCl": {
        "description": "Binary eutectic for spinel synthesis and Si electrolysis",
        "components": {"LiCl": 59, "KCl": 41},
        "mp_C": 353,
        "typical_temp_C": (400, 900),
        "applications": [
            "Li4Ti5O12 octahedra",
            "LiNi0.5Mn1.5O4 octahedra",
            "Si nanoparticle reduction",
            "MXene Lewis acid etching",
        ],
    },

    "AlCl3": {
        "description": "Low-mp single salt for metallothermic Si reduction",
        "mp_C": 192,
        "typical_temp_C": (200, 250),
        "applications": [
            "Si nanoparticles from SiCl4 + Mg",
            "Si from zeolite reduction",
            "Hollow porous Si spheres",
        ],
    },
}


def list_all_systems():
    """Prints a quick summary of every system in the database."""
    print("=" * 72)
    print("ELECTROLYTE SYSTEMS (for AIBs, LMBs, MABs)")
    print("=" * 72)
    for name, sys in ELECTROLYTE_SYSTEMS.items():
        comps = " / ".join(f"{k} {v}%" for k, v in sys["components"].items())
        print(f"  {name:30s}  {sys['working_temp_C']:>5d} °C  [{sys['application']}]")
        print(f"    {comps}")
        print()

    print("=" * 72)
    print("SYNTHESIS SALTS (reaction media for electrode materials)")
    print("=" * 72)
    for name, sys in SYNTHESIS_SALTS.items():
        lo, hi = sys["typical_temp_C"]
        print(f"  {name:30s}  mp {sys['mp_C']:>4d} °C  |  used at {lo}-{hi} °C")
        for app in sys["applications"][:3]:
            print(f"    - {app}")
        print()


if __name__ == "__main__":
    list_all_systems()
