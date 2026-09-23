# Terminal Commands — Perlmutter

Run these in order. One box = one command.

---

## Run the job

**1. Log in** (Password + OTP at the prompt)

```bash
ssh dchrist2@perlmutter.nersc.gov
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

Success looks like `Submitted batch job 1234567`.
Anything with `error:` means it did not submit — see Troubleshooting below.

**5. Confirm it queued**

```bash
squeue -u $USER
```

A row = it took. An empty table = nothing is running.

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

Jobs time out or get preempted. Resubmitting resumes from the last checkpoint.
Same command as step 4, as many times as needed until all five say DONE.

```bash
sbatch -A m4292 -q overrun --requeue perlmutter/la_uma_md.sbatch
```

---

## Troubleshooting

**Check the allocation balance**

```bash
iris
```

**`git pull` refuses because of local edits** — throw away the Perlmutter-side change, then pull again

```bash
git checkout -- perlmutter/la_uma_md.sbatch
```

**30-minute test run instead of the full job**

```bash
sbatch -q debug -t 00:30:00 perlmutter/la_uma_md.sbatch
```

---

## Notes

- Do not submit with `-q gpu_regular` or `-q gpu_debug`. Those names are
  internal; asking for them gives "Job request does not match any supported
  policy". Use `regular`, `debug`, or `overrun`.
- `overrun` is free but lowest priority and gets preempted. That is fine —
  the script checkpoints every 50 ps and always resumes.
- Submitting under `m4292`, not `m4292_g`, per PI instruction. If overrun is
  refused there, it is because overrun is meant for repos that have spent their
  allocation and `m4292` has hours left; `m4292_g` is the spent one. Take that
  back to the PI rather than switching on your own.
- `sbatch` returns immediately. You can log out; the job keeps running.
