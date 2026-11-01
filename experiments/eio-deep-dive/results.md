# eio_fiber_stream deep dive -- results

Follow-up to TASK 3 (`../fp-falign-autocompact/`), which flagged
`eio_fiber_stream` as an outlier with a wide, inconsistent spread across
runtimes and (echoing TASK 2's inference) was tentatively written off as
scheduling noise. This investigation used repeated, pinned measurement plus
on-CPU flamegraph diffing to check that call. Interactive write-up (embedded
flamegraphs): `report.html` (also published as a Claude artifact during the
session).

## Headline

**Not noise.** Under `taskset -c 3` (a P-core) + `setarch -R` (ASLR off) +
`perf stat -r 30`, the wall-time/instruction delta between `ocaml-5.5` and
the fp variants reproduces with **±0.02% stddev over 30 repetitions** --
about as close to deterministic as a wall-clock measurement gets. The
~10% spread originally seen came from two sources layered on top of a real,
smaller effect: (1) the unpinned harness running on a hybrid P-core/E-core
CPU under the `powersave` governor (DVFS + possible core-type migration
across invocations), and (2) a genuine, reproducible cost from
`--enable-frame-pointers`.

## Decomposition (pinned, `perf stat -r 30`)

| runtime | instructions | vs stock | wall time | vs stock |
|---|---|---|---|---|
| `ocaml-5.5` | 42.14B | ref | 3.283s | ref |
| `ocaml-auto-compact` | 42.13B | -0.0% | 3.316s | +1.0% |
| `ocaml-5.5-fp` | 46.22B | +9.7% | 3.458s | +5.3% |
| `ocaml-auto-compact-fp` | 46.22B | +9.7% | 3.454s | +5.2% |

`ocaml-5.5-fp` and `ocaml-auto-compact-fp` land on the same instruction
count and wall time to within measurement noise -- **auto-compaction
contributes nothing here; the entire effect is frame pointers.**

## Where it comes from

Differential on-CPU flamegraph (`flamegraphs/diff2.svg`, normalized,
`difffolded.pl -n`) between `ocaml-5.5` and `ocaml-5.5-fp` (8 reps each,
dwarf call-graph, 999Hz): the single largest mover by weighted-sample
delta is `caml_ml_mutex_lock` (**+65%**), followed almost entirely by other
mutex paths -- `pthread_mutex_trylock` (+219%), `caml_ml_mutex_unlock`
(+58%), `pthread_mutex_unlock` (+24%, plus a new-under-fp path), and a
smaller secondary bump in `caml_modify` (minor-GC write barrier, +68% but
much lower absolute weight).

`caml_ml_mutex_lock`/`unlock` live in the OCaml runtime's C source
(`runtime/sync_posix.c`). `--enable-frame-pointers` rebuilds the entire
runtime with a `push %rbp; mov %rsp,%rbp ... pop %rbp` prologue/epilogue on
every C function in it, including these. They're tiny, extremely hot
functions, and `eio_fiber_stream`'s 4-producer/4-consumer design calls them
millions of times ("Processed 60,000,000 items") -- so the fixed per-call
tax dominates far more here than on compute-bound benchmarks, where the
suite-wide fp cost (see `../fp-falign-autocompact/results.md`) is only
~1-2.5%. This also explains why `owl_gc`/`zarith_pi`/etc. barely move under
fp: they aren't mutex-call-dense the way a multi-domain stream benchmark is.

## What wasn't done

Off-CPU analysis (`perf sched record` / bpftrace, per Brendan Gregg's
https://www.brendangregg.com/offcpuanalysis.html) was scoped in but not run
-- it needs root (tracing debugfs permissions), unavailable non-interactively
in this session. Not needed to explain the result: `task-clock` ≈ wall-clock
in every `perf stat` run (the process is essentially never blocked), so the
on-CPU instruction-count story already fully accounts for the wall-time
delta. Available as a follow-up (see `worklog.md` for exact commands) if
someone wants to double-check with root access.

## Correction to prior read of `eio_fiber_stream`

In conversation (not written into `../fp-falign-autocompact/results.md`
itself), the recommendation was to treat every `eio_fiber_stream` delta as
noise, extrapolating from TASK 2's inference that its harness-observed
swings didn't reproduce under perf. That's wrong for the fp axis
specifically -- it's a real, reproducible ~5% cost, not noise. Added a
proper note to `../fp-falign-autocompact/results.md` with this finding. It
likely still holds for auto-compaction alone (+1.0%, close to the noise
floor implied by this experiment's ±0.02% pinned stddev, though that
stddev was measured only for the fp-axis pair, not re-validated for
auto-compact alone).
