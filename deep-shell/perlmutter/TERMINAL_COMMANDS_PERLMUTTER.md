# Perlmutter Terminal Commands

I run these in order after signing in to NERSC. One box = one command.

---

## Run the job

**1. Log in.** Use your own NERSC username. Password + OTP at the prompt.

```bash
ssh user@perlmutter.nersc.gov
```

**2. Go to the working directory**

```bash
cd $SCRATCH/SolvationNet/deep-shell
```

**3. Get the latest script**

```bash
git pull
```

**4. Submit**

```bash
sbatch -A m4292 -q overrun --requeue perlmutter/la_uma_md.sbatch
```

or alternatively

```
# sbatch -A m4292_g -q overrun --requeue perlmutter/la_uma_md.sbatch
```

If it worked you get a job ID back. If the output says `error:`, check Troubleshooting.

**5. Confirm it queued**

```bash
squeue -u $USER
```

A row means it took. An empty table means nothing is running.

---

## Check on it

**Speed and ETA per system**

```bash
grep st/s results/La3+_*/slurm.log
```

**Latest step, time, temperature, energy**

```bash
tail -n 1 results/La3+_*/md.log
```

**Launcher output**

```bash
cat la_uma_md_*.out
```

**Are all five done?**

```bash
ls results/La3+_*/final.xyz
```

---

## Resubmit

Jobs time out or get preempted. Resubmitting picks up from the last checkpoint.
Run step 4 again as many times as it takes.

```bash
sbatch -A m4292 -q overrun --requeue perlmutter/la_uma_md.sbatch
```

---

## Troubleshooting

**Check the allocation balance**

```bash
iris
```

**`git pull` refuses because of local edits.** Drop the Perlmutter-side change, then pull again.

```bash
git checkout -- perlmutter/la_uma_md.sbatch
```

**30-minute test run instead of the full job**

```bash
sbatch -q debug -t 00:30:00 perlmutter/la_uma_md.sbatch
```

---

## Notes

- Don't use `-q gpu_regular` or `-q gpu_debug`. Those names are internal and
  Slurm rejects them with "Job request does not match any supported policy".
  Use `regular`, `debug`, or `overrun`.
- `overrun` is free but runs at the lowest priority and gets preempted. The
  script checkpoints every 50 ps and resumes, so that's survivable.
- `sbatch` returns right away. You can log out and the job keeps going.
