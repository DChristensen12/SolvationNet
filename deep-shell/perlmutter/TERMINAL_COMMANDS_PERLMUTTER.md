# Perlmutter Terminal Commands

We run these in order after signing in to NERSC. One box is one command.

## Run the job

Log in with the NERSC username for the account, giving password and OTP at the
prompt.

```bash
ssh user@perlmutter.nersc.gov
```

Go to the working directory.

```bash
cd $SCRATCH/SolvationNet/deep-shell
```

Get the latest script.

```bash
git pull
```

Submit.

```bash
sbatch -A m4292 -q overrun --requeue perlmutter/la_uma_md.sbatch
```

The `m4292_g` allocation is spent, so the charged form of the same submission
is kept here only for reference.

```bash
# sbatch -A m4292_g -q overrun --requeue perlmutter/la_uma_md.sbatch
```

A successful submission returns a job ID. Output beginning `error:` is covered
under Troubleshooting.

Confirm it queued.

```bash
squeue -u $USER
```

A row means the submission took. An empty table means nothing is running.

## Check on it

Speed and ETA per system.

```bash
grep st/s results/La3+_*/slurm.log
```

Latest step, time, temperature, and energy.

```bash
tail -n 1 results/La3+_*/md.log
```

Launcher output.

```bash
cat la_uma_md_*.out
```

Which of the five systems have finished.

```bash
ls results/La3+_*/final.xyz
```

## Resubmit

Jobs time out or get preempted, and resubmitting picks up from the last
checkpoint. The submission above can be repeated as many times as it takes.

```bash
sbatch -A m4292 -q overrun --requeue perlmutter/la_uma_md.sbatch
```

## Troubleshooting

Check the allocation balance.

```bash
iris
```

When `git pull` refuses because of local edits, drop the Perlmutter-side change
and pull again.

```bash
git checkout -- perlmutter/la_uma_md.sbatch
```

Run a 30 minute test instead of the full job.

```bash
sbatch -q debug -t 00:30:00 perlmutter/la_uma_md.sbatch
```

## Notes

- `-q gpu_regular` and `-q gpu_debug` are internal names, and Slurm rejects them
  with "Job request does not match any supported policy". The QOS names that
  work are `regular`, `debug`, and `overrun`.
- `overrun` is free but runs at the lowest priority and gets preempted. The
  script checkpoints every 10 ps and resumes, so preemption is survivable.
- `sbatch` returns right away, and the job keeps going after logout.
