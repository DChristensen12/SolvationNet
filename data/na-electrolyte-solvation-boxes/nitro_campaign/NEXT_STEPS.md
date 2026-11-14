# Nitro NPT campaign: handoff (updated 2026-11-12 05:00 UTC)

## Status: DONE. All 21 boxes finished (50 ps NPT each); no sandbox running. Updated 2026-11-12 05:00 UTC.

Protocol: UMA Nitro (uma_nitro = UMA-S-1.2.1-FT-D4rev), NPT only, 50 ps (--npt-steps 50000), 300 K, 1 atm,
from the NVT_OrbMolV2 boxes. Density = mean of the last 20% of the run. Drift = change in mean density
between the last two 20% windows; <1% counts as converged.

All 21 final structures: <name>/<name>.xyz in this folder. Results table: nitro_npt_50ps_summary.csv.
Checkpoints, diagnostics plots and logs stay on the volume: /mnt/remote/26-11-08-nitro-npt/results/<name>/.

### Open items for the user (nothing was extended; user wanted to review first)
- 13 of 21 boxes have drift >=1% (not converged at 50 ps). Candidates for 100 ps extension, worst first:
  NaTFSI_DME_1M (-9.6%, drift 2.7%), NaPF6_DME_1M (-4.5%, 2.3%), NaClO4_PC_1M (-3.1%, 2.2%), NaPF6_DME_1M-r2, NaOTf_DME_1M-r2, NaOTf_DME_1M (see the CSV for all, sort by converged_drift_pct).
- NaClO4_water_1M: +7.7% error and a noisy trajectory (final frame 1.279 vs tail mean 1.163).
- Organic boxes mostly finish below experiment; the error shrinks with glyme chain length.
- README.md in data/na-electrolyte-solvation-boxes does not yet list the Nitro subset.
- To extend a box, resume from its checkpoint with: equilibrate.py --resume <name> --npt-steps 100000 --model uma_nitro
  (checkpoint dir must contain the box; copy results/<name> to the checkpoint dir first).

## Where things live
- Remote volume: /mnt/remote/26-11-08-nitro-npt/
  - boxes/ (inputs; npt_extended/ subfolder is NOT part of the 21), scripts/ (equilibrate.py, utils.py, driver.py),
    exp_densities.csv, results/ (summary.csv, heartbeat.json, per-box folders with checkpoints, diagnostics.png, run logs)
- Local: data/na-electrolyte-solvation-boxes/nitro_campaign/ (finished .xyz + summary CSV)
- Token: HF_TOKEN in SolvationNet/.env (git-ignored; template .env.example). utils.py loads it via load_env().
  Needs access to the gated repo facebook/UMA.

## How to resume (about 10 minutes of setup, then about 4-5 hours for the 5 boxes)
1. Create sandbox: image chemistry-py-3.12-gpu, gpu H100, timeout 86400, NO cwd (a cwd inside /mnt/remote breaks execution).
2. Ask the user to confirm the token upload (the permission system has blocked .env uploads without explicit confirmation).
   Upload SolvationNet/.env to /mnt/remote/26-11-08-nitro-npt/envtmp.txt. WAIT for it to finish, then in the sandbox:
   copy it to /tmp/run/.env (chmod 600) and delete envtmp.txt from the volume. Never print the token. Do not batch the delete with the copy.
3. In the sandbox: pip install fairchem-core (2.25.0 worked); copy scripts/{equilibrate,utils,driver}.py to /tmp/run/ and exp_densities.csv to /tmp/run/exp.csv.
4. Check token + checkpoint access (huggingface_hub get_hf_file_metadata on facebook/UMA checkpoints/uma-s-1p2p1-ft-d4rev.pt).
5. Run: cd /tmp/run && nohup python driver.py > /tmp/driver.log 2>&1 &   (it skips boxes already in results/summary.csv).
6. Verify after a few minutes: results/heartbeat.json names the current box (the first write shows box null); speed about 13-17 steps/s.

## Gotchas
- pkill does not always kill equilibrate.py: check with ps and kill -9 leftover PIDs, or two runs share the GPU.
- Sandboxes have died unexpectedly once; heartbeat.json (every 3 min) shows when. Finished boxes are safe on the volume.
- To pause cleanly: stop the driver and any equilibrate.py, then download new results to nitro_campaign/<name>/<name>.xyz.
- Parallel runs on 3 GPUs would cut the 8 remaining boxes to about 3 h but need a driver that splits the box list; the user declined this for now.

## Open items for the user
- Review unconverged boxes (drift >1%) and decide which to extend to 100 ps.
- README.md in data/na-electrolyte-solvation-boxes does not list the Nitro subset yet.
- NaTFSI boxes are larger and will run slower than the 55 min average.

## Update 2026-11-14: two boxes extended to 100 ps
NaPF6_DME_1M and NaClO4_PC_1M were resumed from their 50 ps checkpoints for another 50 ps (100 ps total, new random velocities on resume).
Structures + summary: extended_100ps/ (summary_100ps.csv). Remote: /mnt/remote/26-11-08-nitro-npt/results_100ps/.
- NaPF6_DME_1M: 0.9623 g/cm3 (exp 0.995, -3.3%), drift 0.01% (100 ps) / 0.45% (ps 50-100). Converged.
- NaClO4_PC_1M: 1.2504 g/cm3 (exp 1.2616, -0.9%), drift 0.75% (100 ps) / 0.23% (ps 50-100). Converged.
Their 50 ps entries in nitro_npt_50ps_summary.csv are unchanged (-4.5% and -3.1%). The 11 other unconverged boxes remain at 50 ps.
The 100 ps boxes have not yet been added to na-electrolyte-solvation-boxes-UMA-S-1p2p1-FT-D4rev/ (pending user decision).
Extension driver saved at remote scripts/ext_driver.py (hardcodes the two box names; edit the list to extend others).
