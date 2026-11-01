# worklog -- eio_fiber_stream deep dive

Follow-up to TASK 3. User: "eio_fiber_stream results are very odd across
all variants we've tested" -> asked to reduce noise to a minimum, perf
capture + flamegraph + diff, off-CPU analysis per Brendan Gregg's method.

## Environment recon

- `perf_event_paranoid = -1` (unrestricted perf record, no root needed).
- `perf sched record` / `bpftrace` / `offcputime-bpfcc` all need root
  (tracing debugfs perms: "No permissions to read
  /sys/kernel/tracing/events/sched/sched_switch"). No passwordless sudo.
  Asked the user to run `sudo mount -o remount,mode=755
  /sys/kernel/tracing/` themselves via `!` if they want off-CPU covered;
  proceeded with on-CPU in the meantime (see results.md -- turned out not
  to be needed).
- CPU is a hybrid Intel i7-14700 (P-cores + E-cores; perf's `cpu_core` vs
  `cpu_atom` counter split confirms it). Governor: `powersave`,
  800MHz-5.3GHz range. Asked the user to also set `performance` governor
  via sudo for noise reduction.
- `cpu3` has an SMT sibling (`cpu2`) -- confirmed it's a P-core (E-cores on
  this chip have no SMT). `../perf-slowdown-analysis/capture.sh` already
  pins to `CORE=3` for this reason; reused that choice.

## Phase 1 -- noise quantification (`perf stat -r 30`)

Set up `eio-deep-dive/capture.sh` (adapted from
`../perf-slowdown-analysis/capture.sh`, eio-only, higher rep counts,
added `stat`/`offcpu` modes). Ran `perf stat -r 30` (taskset -c 3 +
setarch -R) for the 4 key runtimes:

- `ocaml-5.5`: 3.283s ± 0.02%, 42.14B instructions
- `ocaml-auto-compact`: 3.316s (+1.0%), 42.13B instructions (flat)
- `ocaml-5.5-fp`: 3.458s (+5.3%), 46.22B instructions (+9.7%)
- `ocaml-auto-compact-fp`: 3.454s (+5.2%), 46.22B instructions (+9.7%,
  identical to fp-alone)

Immediate conclusion: this is NOT noise (±0.02% stddev is about as tight as
wall-clock measurement gets) and it's NOT auto-compaction (fp-alone and
fp+auto-compact land on the same numbers). Clean, fully explained by fp
alone. This directly overturns the "treat every eio delta as noise" read
from the original (unpinned) TASK 3 table -- the earlier spread was real
signal (fp) plus environmental noise (unpinned harness on a hybrid CPU
under a DVFS governor) layered together, not noise alone.

## Phase 2 -- on-CPU capture hits an ENOMEM crash

First `perf record --call-graph dwarf,16384 --all-user` attempt: **every
single rep crashed** with `Fatal error: exception Unix.Unix_error(Unix.ENOMEM,
"io_uring_queue_init", "")` -- only 3 samples captured per rep (the crash
happened almost immediately after exec).

Root-caused: `eio_fiber_stream` unconditionally calls
`Eio_main.run`'s Linux backend setup, which calls `io_uring_queue_init` at
startup regardless of whether the workload ever issues ring I/O (per
`macro_base.yml`'s own comment, this benchmark's Stream workload is
in-memory only and "never hits the ring" -- but the io_uring instance still
gets created). `io_uring_queue_init` needs to `mlock` some pages; this
account's `RLIMIT_MEMLOCK` is a hard-capped 8MB (`ulimit -Hl` = 8192,
confirmed not raisable without root: "cannot modify limit: Operation not
permitted"). `perf record`'s own default mmap ring buffer ALSO counts
against that same 8MB budget for an unprivileged user -- together they
exceeded it, so `io_uring_queue_init`'s mlock request failed.

Bisected which side was the actual problem: tried shrinking the *dwarf
per-sample stack size* first (`dwarf,8192` / `4096` / `2048` / `1024`,
even `--call-graph fp` and no call-graph at all) -- all still crashed
identically. Then tried shrinking perf's own *mmap ring buffer* instead
(`-m 4`) -- fixed immediately, 3,320 samples captured on a plain smoke
test. So it was perf's base ring buffer overhead, not the dwarf unwind
buffer. Folded this into `capture.sh`'s `oncpu` mode permanently (`-m 4`
now baked in, with a comment explaining why).

## Phase 3 -- flamegraphs + diff

Reran `oncpu` for `ocaml-5.5` and `ocaml-5.5-fp` (8 reps each, ~2,200-2,400
samples/rep, full fidelity). Folded with the vendored
`../perf-slowdown-analysis/FlameGraph/stackcollapse-perf.pl` (`perf script
--no-inline`), rendered individual flamegraphs, and generated a normalized
differential (`difffolded.pl -n` -- normalizing matters here since the fp
run does ~1.9% more total weighted work, want the diff to isolate shape
change not just "the fp run took longer overall").

Top movers by absolute weighted-sample delta, stock -> fp (see
`flamegraphs/diff2.folded`):
1. `caml_c_call;caml_ml_mutex_lock` -- +65% (3.71B -> 6.12B), by far the
   largest single delta (~4% of total run weight on its own).
2. `[unknown];pthread_mutex_trylock` -- +219% (304M -> 972M).
3. `caml_c_call;caml_ml_mutex_unlock;pthread_mutex_unlock` -- +24%.
4. `caml_c_call;caml_ml_mutex_unlock` -- +58%.
5. `caml_c_call;pthread_mutex_unlock` -- new path entirely under fp.
6. `caml_alloc_string`, `caml_modify`, `Bytes.make` -- smaller secondary
   growth, plausibly downstream of the mutex contention rather than an
   independent effect.

Essentially all growth is in the mutex lock/unlock/trylock call paths --
`caml_ml_mutex_lock`/`unlock` are OCaml-runtime C functions
(`runtime/sync_posix.c`); `--enable-frame-pointers` rebuilds the whole
runtime with a frame-pointer prologue/epilogue on every C function
including these. They're tiny and called millions of times by this
benchmark's 4-producer/4-consumer design ("Processed 60,000,000 items"),
so the fixed per-call tax dominates far more than on compute-bound
benchmarks (suite median fp cost ~1-2.5%, see
`../fp-falign-autocompact/results.md`).

## Phase 4 -- off-CPU, scoped but not needed

Checked whether off-CPU time could still be contributing independently:
in every `perf stat` run, `task-clock` ≈ wall-clock (e.g. 3,281.79ms
task-clock vs 3.283s wall for `ocaml-5.5`) -- the process is on-CPU
essentially the entire time, never meaningfully blocked. The on-CPU
instruction-count story already fully accounts for the wall-time delta, so
off-CPU analysis wouldn't add anything here. Left the capability in
`capture.sh`'s `offcpu` mode (untested pending the sudo/tracing-perms fix)
for anyone who wants to double-check independently.

## Phase 5 -- write-up

Built an interactive HTML report (`report.html`, also published as a
Claude artifact) embedding the three flamegraphs (stock / fp / diff) each
in an isolated `<iframe>` with a base64 `data:` URI -- needed because
flamegraph.pl's generated SVGs define global JS functions (`zoom`,
`search`, etc.) that collide if multiple are inlined directly into the same
page. Wrote `results.md` with the numeric findings and flagged the
correction to TASK 3's `results.md` (which had said to treat every eio
delta as noise -- true for auto-compaction alone, false for fp).
