# Density References

Sources for the density columns in `molten_salt_concentrations_and_dens.csv`.

## sim_density_g_cm3

NPT-equilibrated density from MACE-MP small 0b2 simulations at 1 atm and each
system's working temperature. Mean over the last 40% of each run. See the dataset
README for per-system standard deviations and run lengths.

## ref_density_g_cm3

### Janz_NIST_ideal_mixing

Ideal additive molar volume estimate from pure-salt reference densities. The pure-salt
densities come from the Janz NIST Molten Salts Standard Reference Database, which
tabulates experimentally measured density as a function of temperature for >300 pure
molten salts.

Reference: Janz, G. J. et al. "NIST Properties of Molten Salts Database." NIST
Standard Reference Database 27. National Institute of Standards and Technology.

The ideal mixing rule assumes zero excess volume: the molar volume of the mixture
equals the mole-fraction-weighted sum of the pure-component molar volumes. Caveats:

1. The pure-salt reference densities were measured at temperatures that differ from
   the run temperature (742-1143 K for the sources used). No temperature correction
   was applied.
2. Excess volume of mixing is neglected. For molten halide mixtures this is typically
   small but nonzero.
3. Since melts contract on cooling, correcting the reference densities to the run
   temperature would raise the reference and widen the gap with the simulated values.

The reported deviations (MACE 5.5-14.8% below ideal mixing) are therefore lower bounds.

## System compositions

Compositions from Table 3 of:

Liu, Y. et al. "Molten Salts for Rechargeable Batteries." Materials Today 60, 128
(2022). DOI: 10.1016/j.mattod.2022.09.005
