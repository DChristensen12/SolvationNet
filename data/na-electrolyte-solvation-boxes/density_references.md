# Experimental Density References

Sources for the `exp_density_g_cm3` column in `na_ion_salt_concentrations_and_dens.csv`.
Every value in that column traces to one of the sources below via the `exp_density_source` column.

## Sources

### Kumar2026_TableS1

Kumar, N. et al. "Prediction and Experimental Verification of Electrolyte Solvation
Structure from an OMol25-Trained Interatomic Potential." arXiv:2603.20183 (2026).
Table S1 (page S-5). Measured with Anton Paar DMA 4500M densitometer at 298.2 K.

Systems covered (all 1 M):
- NaOTf / DME: 0.980 g/cm3
- NaPF6 / DME: 0.995 g/cm3
- NaTFSI / DME: 1.055 g/cm3
- NaOTf / diglyme: 1.047 g/cm3
- NaPF6 / diglyme: 1.059 g/cm3
- NaOTf / tetraglyme: 1.106 g/cm3
- NaPF6 / tetraglyme: 1.115 g/cm3
- NaOTf / PC: 1.277 g/cm3
- NaPF6 / PC: 1.291 g/cm3

### Hofmann2021_Table2

Hofmann, A. et al. "Comprehensive Characterization of Propylene Carbonate Based Liquid
Electrolyte Mixtures for Sodium-Ion Cells." Electrochim. Acta 403, 139670 (2021).
DOI: 10.1016/j.electacta.2021.139670. Table 2. Anton Paar DMA 4500M at 25 C.

Systems covered (all 1 M NaClO4):
- PC: 1.2616 g/cm3
- EC:PC 1:1 mol: 1.3243 g/cm3

Note: Hofmann mixtures use 1:1 mol/mol ratios. Our boxes may use volume ratios.

### Monti2020_Fig4c

Monti, D. et al. "Towards Standard Electrolytes for Sodium-Ion Batteries: Physical
Properties, Ion Solvation and Ion-Ion Interactions." Phys. Chem. Chem. Phys. 22,
22768-22777 (2020). DOI: 10.1039/d0cp03639k. Anton Paar DMA 4500M at 25 C.
Values read from density-vs-temperature plot (Fig 4c). Uncertainty ~+/-0.01 g/cm3.

- NaPF6 / EC:DMC 1:1 / 1 M: 1.24 g/cm3

**Caveat**: Monti 2020 specifies EC:DMC 1:1 by WEIGHT, not by volume. If our boxes
use 1:1 v/v, the composition differs slightly and the density may not be directly
comparable.

### Monti2020_Fig4d

Same paper, Fig 4d. Same uncertainty and weight-fraction caveat.

- NaTFSI / EC:DMC 1:1 / 1 M: 1.26 g/cm3

### CRC_Handbook_97th

CRC Handbook of Chemistry and Physics, 97th ed. (2016-2017). "Concentrative Properties
of Aqueous Solutions." Density interpolated from tabulated density-vs-weight-percent data
for NaClO4(aq). Valid up to ~9.3 M (saturation limit).

- NaClO4 / water / 1 M: 1.080 g/cm3
- NaClO4 / water / 5 M: 1.371 g/cm3

### Jha2024_Fig3a

Jha, A. K. et al. "Super-concentrated sodium perchlorate electrolyte for sodium-ion
batteries." Energy Storage Materials 72, 103758 (2024).
DOI: 10.1016/j.ensm.2024.103758. Section 3 / Fig 3a. Measured on Anton Paar DMA 45
densitometer.

- NaClO4 / water / 17 m (molal): 1.664 g/cm3

Corroborated by: Gomez Vazquez, D. et al., JACS 2025. DOI: 10.1021/jacs.5c12989,
Table 1 (reports 1.67 g/cm3 for 17m NaClO4).

Note: "17M" in our filenames means 17 molal (mol/kg solvent), not 17 molar (mol/L).
17 m NaClO4 corresponds to ~9.2 M (molar), within the saturation limit.

---

## Missing Density: Search Status (2026-11-04)

Systematic literature search for the 60 systems without experimental density.
Paywalled papers could not be accessed; lead papers are listed so they can be
checked through institutional (LBNL) library access.

58 unverified systems have been moved to `electrolyte_toolkit/data/unverified/`.

### Priority Group 1: NaFSI/DME concentration series (0.5-5 M)

**Status: ALL MISSING.** No open-access source found with NaFSI/DME density
as a function of concentration.

Lead papers (likely contain density data):
- Kazhiyev et al. (NOT Huang), J. Power Sources 2025, 238235.
  DOI: 10.1016/j.jpowsour.2025.238235
  Note: This paper is DFT/AIMD/MD, not experimental. May not contain
  measured density.
- Geysens et al. (NOT Mandai), J. Phys. Chem. B 2018, 122, 275-289.
  DOI: 10.1021/acs.jpcb.7b10158
  Note: Studies NaFSI-glyme solvate ILs; may have density for concentrated
  NaFSI/glyme systems but not necessarily DME.

### Priority Group 2: NaPF6/EC:DEC ratio series (1:1 to 9:1, all 1 M)

**Status: ALL MISSING.** The exact density values at each EC:DEC ratio could
not be extracted from open sources.

Lead papers:
- Ould et al. (NOT Sheridan), Chem. Commun. 2025, 61, 8516.
  DOI: 10.1039/D5CC01447F (CC BY).
  Note: Reports properties of NaPF6 electrolytes; may contain density data.
- Ponrouch et al., Energy Environ. Sci. 2012, 5, 8572.
  DOI: 10.1039/c2ee22258b
  **Note: This paper does NOT report density.** Measures only viscosity,
  conductivity, thermal and electrochemical stability.
- Landesfeind et al., J. Electrochem. Soc. 2021, 168, 040538.
  DOI: 10.1149/1945-7111/abf8d9 (CC BY).

### Priority Group 3: NaClO4 in organic solvents (DME, EC:DEC, EC:DMC, EC:DME)

**Status: ALL MISSING.** Density data for NaClO4 in organic carbonates/ethers
is scarce; most papers report only conductivity and viscosity.

### Priority Group 4: NaClO4/water supersaturated (10 M)

**Status: DROPPED.** NaClO4_water_10M exceeds the saturation limit of NaClO4
in water at 25 C (~9.32 M). This concentration cannot exist as a stable solution
at room temperature; no standard measured density is possible. This system should
be dropped or relabeled.

### Priority Group 5: NaFSI/Pyr13FSI ionic liquid

**Status: COMMERCIAL ONLY.**

- NaFSI:Pyr13FSI 1:9 mol ratio: Density = 1.372 g/cm3 at 20 C.
  Source: Solvionic product specification E072. This is a commercial
  product datasheet, NOT a peer-reviewed measurement. Does not qualify
  as verified.
- NaFSI/Pyr13FSI 3.8M: MISSING.

### Priority Group 6: Other single-salt/single-solvent systems

- NaFSI/TMP 3.3M: MISSING.
- NaFSI/diglyme 1M: MISSING.
- NaFSI/water 21M: MISSING. Reber et al., Adv. Energy Mater. 2021, 11,
  2002913 (DOI: 10.1002/aenm.202002913) studied WIS electrolytes but
  **does NOT report density** data. Paywalled.
- NaOTf/water 9.26M: MISSING.
- NaPF6/triglyme 1M: MISSING.
- NaPF6/EC:PC 1M: MISSING.
- NaTFSI/PC 1M: MISSING.

### Priority Group 7: NaPF6/diglyme concentration series (0.4-2.5 M)

**Status: ALL MISSING.** Kumar2026 has 1 M only.

Lead papers:
- Westman et al., ACS Appl. Energy Mater. 2018, 1, 2671-2680.
  DOI: 10.1021/acsaem.8b00360
  **Caveat**: Westman defines concentration per dm3 of SOLVENT, not
  per dm3 of solution. Their 1.0 M NaPF6/diglyme = 1.04 g/cm3, vs
  Kumar's 1.059 g/cm3 at standard molar definition. Values are not
  directly comparable.
- Ravikumar et al., J. Phys. Chem. B 2022, 126, 2765-2776.
  DOI: 10.1021/acs.jpcb.2c00557

### Niche/mixed systems (~18 rows)

**Status: ALL MISSING.** These are dual-salt, localized-HCE, or unusual-solvent
formulations with no published density data expected.
