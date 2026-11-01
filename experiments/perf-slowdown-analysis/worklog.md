# Perf-based slowdown root-cause — running work log

TASK 2 from `/home/curche/git/pplacer-workdir/PLAN.md`. Plan file:
`/home/curche/git/pplacer-workdir/TASK2-PLAN.md`. Append-only, following the
TASK 1 convention.

## Context

TASK 0/1 established the wall-time deltas of the three patched runtimes vs.
stock `ocaml-5.5` (see `experiments/compactor-comparison/results.md`,
`auto-compact-tuning/worklog.md`, `space-time-curve/results.md`). TASK 2:
use `perf record` + flamegraphs + differential analysis + supporting tooling
to attribute each slowdown to a concrete runtime function/subsystem, and
find any single overlapping cost source fixable in the patch.

Slowdown targets (vs. stock): **owl_gc** socaml +140% / socaml-auto-compact
+126% / ocaml-auto-compact +26%; **eio_fiber_stream** socaml-auto-compact
+22%; **ocamlc_self_compile** socaml +12%; plus Tier-2 ≤5% (pplacer +2%,
liq_video_frames_pool +2%, cpdf_squeeze +1.5%, …) and speedup controls
(zarith_pi socaml −22%, test_decompress).

## Phase 0 — tooling & methodology (2026-09-09) — DONE

Environment: `perf 7.0.14`, `perf_event_paranoid=-1` (full access),
`kptr_restrict=1` (kernel syms restricted → non-root sees kernel frames as
`[unknown]`), 28 cores, 30 GB RAM. All four runtimes pre-built; each
benchmark has a standalone **not-stripped** `.exe` with
`.debug_info`/`.debug_line`/`.eh_frame` and 25k+ `caml*` symbols under
`macro-benches/_build-<rt>/default/benchmarks/<b>/<b>.exe`, plus a
per-runtime wrapper script `benchmarks/<sd>/<bench>-<rt>` that `exec`s it.

**Methodology decisions (each validated by smoke test on owl_gc):**

1. **Call-graph = `dwarf,16384`, not `fp`.** FP self-time symbols resolve
   fine, but FP call-graphs *break at the OCaml↔C boundary* — OCaml native
   code omits frame pointers, so the unwinder loses the chain (`[unknown]`
   frames, gaps at `caml_c_call_stack_args`, ~34% of stack weight orphaned).
   DWARF (via `.eh_frame`) reconstructs the full hierarchy correctly
   (`cblas_dgemm;dgemm_nn;dgemm_oncopy_HASWELL` etc.).
2. **`perf script` MUST use `--no-inline`.** The default inline-frame
   resolver re-parses the 31 MB binary's DWARF per sample and hangs
   (>90 s for 1779 samples). With `--no-inline`: 0.09 s for the same data.
   This was the single biggest gotcha.
3. **`--all-user`** on record (kernel syms restricted anyway); kernel-side
   cost (page faults from mmap, etc.) captured via `perf stat` instead.
4. Stability: `taskset -c 3` pin, `setarch -R` (ASLR off), fixed
   `OCAMLRUNPARAM="e=25,d=2"` (matches the 4-way baseline's `re-25|md-2`;
   inert without olly attached), `-F 999` sampling, 3 reps/cell.
5. Flamegraphs are **period-weighted** (stackcollapse sums the sample
   period, ∝ CPU time), so weight totals track wall time: owl stock
   20.8e9 vs. socaml 45.3e9 = 2.18×, matching the measured 5.24 s→11.45 s.

**Harness written & validated:**
- `capture.sh <bench> <runtime> [reps] [strace:0|1]` — per-runtime
  `perf record` (dwarf) × reps + one `perf stat` (task-clock, cycles,
  instructions, page-faults, minor/major-faults, cache-refs/misses,
  dTLB-load-misses, context-switches) + optional `strace -f -c`. Uses the
  wrapper if present, else the `_build` exe. Per-benchmark args/env table
  mirrors `macro_base.yml`.
- `fold_and_plot.sh {fold|diff|all}` — folds all reps (summed), renders
  per-cell flamegraph SVGs and **differential** flamegraphs via
  `difffolded.pl` (red = hotter in the patched runtime). Fixed a subshell
  bug where the perf-data-present check was set inside a pipeline and lost.
- FlameGraph (brendangregg) vendored at `./FlameGraph`.

**Phase 0 bonus finding (owl_gc stock vs socaml, 1 rep each):**
- Wall 5.24 s → 11.45 s (2.18×), reproducing the clean 4.62→11.08 ratio
  under perf.
- **strace: socaml issues *fewer* mmap calls (103 vs 126), same munmap
  (7).** So the 2.18× is **not** syscall/mmap overhead — chunk batching is
  doing its job on the syscall count. The extra time is elsewhere.
- Differential flamegraph (socaml − stock) top movers are **all
  major-GC mark/sweep**: `caml_scan_global_roots` (largest), `do_some_
  marking`, `caml_darken`, `mark_stack_push_block`, `pool_sweep`,
  `caml_sweep`, `caml_scan_stack`. This is the 5.5×-more-collections cost
  (per Phase 1 of auto-compact-tuning) landing squarely in mark/sweep —
  to be quantified properly in Phase 1 with 3 reps + all 4 runtimes.

Artifacts: `flamegraphs/owl_gc__{ocaml-5.5,socaml}.svg`,
`flamegraphs/owl_gc__DIFF__socaml_vs_ocaml-5.5.svg`,
`stat/owl_gc__*.stat.txt`, `strace/owl_gc__*.strace.txt`.

## Phase 1 — owl_gc deep dive (2026-09-09) — DONE

Full capture: all 4 runtimes, 3 reps each + `perf stat` + `strace -c`.
Wall under perf (very stable across reps): stock 5.29 s, ocaml-auto-compact
6.46 s (+22%), socaml 11.45 s (+117%), socaml-auto-compact 10.85 s (+105%)
— faithfully reproducing the clean running-ng ratios.

### Subsystem attribution (`subsys.py`, period-weight ≈ CPU-ms, millions)

| subsystem | ocaml-5.5 | ocaml-auto-compact | socaml | socaml-auto-compact |
|---|---|---|---|---|
| BLAS/compute | 43,724 | 43,674 | 42,821 | 41,449 |
| GC:mark | 8,550 | 9,055 (+505) | **49,263 (+40,713)** | **47,005 (+38,455)** |
| GC:roots | 5,651 | **12,099 (+6,448)** | **36,132 (+30,481)** | **32,402 (+26,751)** |
| GC:compact | 0 | **7,207 (+7,207)** | 0 | 0 |
| GC:sweep | 390 | 351 | 1,677 (+1,287) | 1,747 (+1,357) |
| **TOTAL** | 62,757 | 76,851 (+14,094) | 135,561 (+72,804) | 128,403 (+65,645) |

(BLAS/compute — the actual owl workload — is **flat** across all four
runtimes: the entire regression is GC-side.)

### perf stat (`stat_table.py`)

| metric | ocaml-5.5 | ocaml-auto-compact | socaml | socaml-auto-compact |
|---|---|---|---|---|
| cycles | 21.1e9 | 25.8e9 (1.22x) | 45.7e9 (2.17x) | 43.3e9 (2.05x) |
| instructions | 70.5e9 | 90.5e9 (1.28x) | **184.9e9 (2.62x)** | **184.9e9 (2.62x)** |
| IPC | 3.34 | 3.51 | 4.05 | 4.27 |
| page-faults | 24.5e3 | 24.5e3 | 63.1e3 (2.57x) | 63.1e3 (2.57x) |
| cache-references | 240.8e6 | 196.6e6 | 162.7e6 (0.68x) | 128.4e6 (0.53x) |
| dTLB-load-misses | 3.7e6 | 3.9e6 | 7.0e6 (1.91x) | 7.3e6 (1.98x) |
| strace mmap / munmap | 126 / 6 | 126 / 6 | **103 / 7** | 103 / 7 |

### Root cause — owl_gc

1. **socaml (+117%) = ~2.6× more instructions, almost entirely GC:mark +
   GC:roots.** Mark cost 5.8×, root-scan cost 6.4× stock — tracking the
   TASK 1 finding of **~5.5× more minor+major collections** (297K/149K vs
   54K/27K). Root-scanning is a *fixed per-major-cycle cost* (owl has a
   large global/Bigarray root set); with 5.5× more cycles it explodes, and
   marking scales the same way. **IPC actually *rises* (3.34→4.05) and
   cache-references *drop*** — so this is not a cache/TLB/stall regression,
   it is simply *more work*: the chunk allocator drives many more GC cycles
   for owl's Bigarray/OpenBLAS allocation profile. `strace` confirms it is
   **not** mmap/syscall overhead (socaml issues *fewer* mmaps, 103 vs 126).
   The +2.57× page-faults and +1.9× dTLB-misses are real but secondary
   footprint effects (2.2× RSS from 8 MB chunk granularity), not the
   dominant cost — major-faults = 0 (no swap).
2. **ocaml-auto-compact (+22%) = compaction (GC:compact +7.2G) plus the
   root-rescan compaction induces (GC:roots +6.4G).** This is the
   O=-tunable cost from TASK 1: at the compiled-in `O=500`, owl compacts on
   ~100% of major cycles for ~0 RSS benefit. Raising the default to 700-1000
   (TASK 1's recommendation) removes this entire +22% — now confirmed at the
   flamegraph/instruction level, not just wall time.
3. **socaml-auto-compact (+105%) ≈ socaml.** Identical instruction count
   (184.9e9) and near-identical subsystem profile, **GC:compact = 0** —
   auto-compaction never engages under the chunk allocator for owl
   (TASK 1 Phase 7: cycles complete via opportunistic slices that skip the
   compaction check). So the two socaml variants are the same cost; the
   chunk-allocator's extra-cycles cost dominates and swamps everything.

### Overlap signal (feeds Phase 4)

**GC:roots (global root scanning) is inflated in *all three* patched
runtimes** (+6.4G / +30.5G / +26.8G). It is the per-major-cycle fixed cost
that both patches multiply — auto-compact by forcing full root updates on
compaction, the chunk allocator by driving far more cycles. This is the
first candidate for a common, overlapping cost source.

Artifacts: `flamegraphs/owl_gc__*.svg` (4 per-cell + 8 differential),
`stat/owl_gc__*`, `strace/owl_gc__*`, `subsys.py`, `stat_table.py`.

## Phase 2 — eio_fiber_stream & ocamlc_self_compile (2026-09-09) — DONE

Both original Tier-1 "slowdowns" turn out to be **non-reproducing noise**,
not runtime costs. This matches the compactor-comparison worklog, which
had itself flagged both as noisy/unconfirmed.

### eio_fiber_stream (+22% socaml-auto-compact was the claim)

- Wall under perf: stock 2.70 s, auto-compact 2.77 s, socaml 2.78 s,
  socaml-auto-compact 2.81 s — **all within 4%**; the +22% (3.51 vs 2.87)
  does not reproduce.
- **Not CPU-bound**: only ~3 perf samples in ~2.7 s → ~99.9% *off-CPU*
  (fiber scheduling / wakeup latency, io_uring wait). `perf record` (on-CPU
  sampler) correctly finds no hotspot because there is none; the wall time
  is dominated by blocking, not computation. The original +22% was
  scheduling/wakeup variance on a latency-bound benchmark.
- strace: socaml 22 mmaps vs stock 71 (chunk batching), irrelevant to wall
  time here. (Off-CPU attribution would need `perf sched`/BPF offcputime;
  not pursued since the delta doesn't reproduce.)

### ocamlc_self_compile (+12% socaml was the claim)

- Wall under perf: stock 4.81 s, auto-compact 4.83 s, socaml 4.79 s,
  socaml-auto-compact 4.75 s — socaml is **marginally faster**, not slower.
  The +12% (5.33 vs 4.76) was the bimodal wall-time noise this benchmark is
  already documented to have (auto-compact-tuning Phase 9: 4.78–5.68 s
  within a single config).
- Profile is essentially identical across runtimes: TOTAL CPU-weight socaml
  52,696 vs stock 53,478 (socaml 1.5% *lower*); instructions 44.2e9 vs
  44.9e9 (0.98×); IPC 2.39 both; no socaml hotspot in the diff flamegraph.
- **Dramatic mmap contrast with zero wall-time effect**: stock issues
  **30,563 mmap** calls, socaml **216** (140× fewer — the clearest chunk-
  batching demonstration in the suite, since ocamlc allocates a huge number
  of small pools during compilation). Yet wall time and **page-faults**
  (263K vs 272K) are unchanged — pages are faulted on first touch either
  way; batching saves *syscalls*, and here the ~30K saved syscalls are
  immaterial against the compile compute. (Contrast zarith_pi, where
  allocation churn *is* the workload, so the same batching is a real win —
  to be shown as a Phase 3 control.)

**Takeaway:** of the three Tier-1 targets, only **owl_gc** is a real,
reproducible slowdown. eio and ocamlc are noise.

Artifacts: `flamegraphs/{eio_fiber_stream,ocamlc_self_compile}__*`,
`stat/`, `strace/`.

## Phase 3 — Tier-2 small slowdowns + speedup controls (2026-09-09) — DONE

Methodology note added: the flamegraph fold sums perf's per-sample **period**
(event = `cpu_core/cycles`), which is a good *within-profile* attribution
weight but its **absolute** total can drift from wall time under `-F`
frequency mode (seen on zarith: folded-cycles ≈flat while wall −16%). So:
**`perf stat` (PMU counters, one clean run) is authoritative for per-runtime
totals; folded stacks for relative subsystem attribution.** All Tier-2
verdicts below use `perf stat` cycles/instructions as ground truth.

### Verdicts (perf stat, socaml & socaml-auto-compact vs stock)

| benchmark | wall Δ | cycles | **instructions** | verdict |
|---|---|---|---|---|
| pplacer_testsuite (loop=5) | +2.7% / −2.9% | 1.03× / 0.97× | **1.00× / 1.00×** | **noise** — 0 extra instructions; original regression subject, definitively not a runtime cost |
| cpdf_squeeze | +0.5% | 1.00× / 1.00× | **1.00× / 1.00×** | **noise** |
| test_decompress | ~0% | 1.00× / 1.00× | **1.00× / 1.00×** | **flat** — "faster" claim doesn't reproduce |
| zarith_pi | **−16%** | **0.84×** | **0.91×** | **real win** (control) |
| liq_video_frames_pool | — | — | — | exe not built (only stub wrapper); prior data flat ±2% across all 4 |

### zarith_pi win — refined mechanism

The −16% is real and the perf-stat counters localize *why*, refining TASK 1's
"mmap batching" summary:

| metric | stock | socaml | ratio |
|---|---|---|---|
| cycles | 15.7e9 | 13.2e9 | 0.84× |
| instructions | 40.6e9 | 36.8e9 | 0.91× |
| **cache-references** | 66.9e6 | 17.0e6 | **0.25×** |
| **page-faults** | 1.5e6 | 0.59e6 | **0.40×** |
| mmap syscalls | 36 | 21 | 0.58× |
| IPC | 2.58 | 2.79 | — |

The dominant win is **4× fewer cache-references and 2.5× fewer page-faults** —
bulk 8 MB chunk allocation gives far better memory locality and fewer
first-touch faults for zarith's extreme small-bignum churn. The mmap
*syscall* count barely moves (36→21, 15 calls) — so the headline mechanism is
locality/fault reduction, not syscall batching per se (the syscall saving is
real but tiny in absolute terms). Subsystem diff confirms the saved cycles are
in GC mark/sweep/roots/alloc paths, all shrinking together.

### pplacer / cpdf / decompress — flat

`instructions` is identical to 3 significant figures across runtimes for all
three — the chunk allocator adds **zero** instructions to these workloads.
The mmap-batching is dramatic in the syscall count (pplacer 668→120, cpdf
8735→55, decompress 45→23) but has no wall-time or page-fault effect, exactly
as on ocamlc — batching saves syscalls, pages still fault on first touch, and
none of these workloads is syscall-bound. pplacer settles the original
question definitively: the chunk allocator costs it nothing at the
instruction level (consistent with TASK 0's `-falign` finding).

**Takeaway:** across all Tier-2 targets, the only real effect of the patch is
a **speedup** (zarith −16%). Every claimed small slowdown is noise.

## Phase 4 — cross-benchmark overlap synthesis (2026-09-09) — DONE

### What is actually slow

Across every benchmark profiled, **instructions retired vs. stock** (the
honest "is real work being added?" metric — plots/instruction_ratio.png):

| benchmark | socaml | socaml-auto-compact | ocaml-auto-compact |
|---|---|---|---|
| **owl_gc** | **2.62×** | **2.62×** | **1.28×** |
| zarith_pi | 0.91× | 0.91× | ~1.0× |
| ocamlc_self_compile | 0.98× | 0.98× | ~1.0× |
| pplacer_testsuite | 1.00× | 1.00× | ~1.0× |
| cpdf_squeeze | 1.00× | 1.00× | ~1.0× |
| test_decompress | 1.00× | 1.00× | ~1.0× |
| eio_fiber_stream | (off-CPU, not measurable; wall flat ±4%) | | |

**Only owl_gc is a real slowdown.** Every other claimed slowdown is noise
(instructions flat to 3 sig figs) or off-CPU scheduling variance. zarith is
a real speedup.

### The owl_gc mechanism — pinned to a single trigger

The differential flamegraph localizes owl's regression to one call chain
(dominant socaml stacks, plots/owl_subsystem.png):

```
owl_gc.ml (Bigarray matmul)
 → caml_ba_create → caml_ba_alloc → caml_alloc_custom_mem → alloc_custom_gen
   → caml_check_urgent_gc → caml_poll_gc_work
     → caml_empty_minor_heaps_once → …stw… → caml_mark_roots_stw
       → caml_scan_global_roots           (fixed per-cycle root scan)
     → caml_major_collection_slice → mark → do_some_marking / caml_darken
```

owl allocates its matrices as **custom blocks with off-heap (Bigarray)
memory**. `caml_alloc_custom_mem`'s dependent-memory accounting forces a
minor+major GC slice as off-heap bytes accumulate. **On the chunk allocator
this trigger fires ~8× more often**:

- Weight under `alloc_custom_gen → caml_check_urgent_gc`:
  stock **8.3e9 (13.2% of all CPU)** → socaml **71.9e9 (53.0% of all CPU)**
  — an 8.7× increase, matching TASK 1's olly-measured **5.5× more
  minor+major collections** (297K/149K vs 54K/27K).
- The wasted work per firing is a *fixed cost* — `caml_scan_global_roots`
  (owl's large global/Bigarray root set is re-scanned every STW) plus
  marking/darkening — so multiplying the firing rate multiplies the cost
  linearly. Hence GC:mark 5.8× and GC:roots 6.4× in the subsystem table,
  with BLAS/compute (the actual matmul) dead flat.

This is **not** cache, TLB, mmap, or syscall driven (IPC rises, cache-refs
fall, socaml issues *fewer* mmaps). It is purely *more GC cycles* caused by
the chunk allocator perturbing the custom-block dependent-memory GC pacing
for a Bigarray-heavy workload.

### Is there an "overlap fixable in the patch"?

No *broad* overlap — because only one benchmark regresses, there is no
cost source shared across many benchmarks to fix. But within owl there are
**two distinct, both-actionable** cost sources, one per patch:

1. **auto-compaction (ocaml-auto-compact, +28% instructions / +22% wall):**
   GC:compact (+7.2e9) + the root-rescan it induces (GC:roots +6.4e9), at
   the compiled-in `O=500` default where owl compacts ~100% of cycles for
   ~0 RSS benefit. **Already fixable, and fixed by TASK 1's recommendation**
   — raise `Max_percent_free_def` from 500 to 700–1000; the perf data here
   confirms that removes the entire auto-compact regression (the green
   GC:compact block and the orange root-rescan bump both vanish above owl's
   ~700% overhead). This is the one concrete patch change TASK 2 endorses.

2. **chunk allocator (socaml, +162% instructions / +117% wall):** the
   custom-mem GC trigger fires ~8× too often. The fix is *not* a tuning
   knob (TASK 1 Phase 7 showed `O=` and the chunk-size floor are both inert
   for owl; the space-time-curve work showed `o=` is inert too) — it lives
   in the chunk allocator's interaction with the **custom-block
   dependent-memory pacing** (`caml_alloc_custom_mem` /
   `caml_custom_major_ratio` accounting vs. the chunk allocator's heap-size
   bookkeeping in `shared_heap.c`). That is a real, now-precisely-located
   code target (the perf work narrows TASK 1's open "opportunistic-slice
   pacing" question to specifically the custom-mem trigger path), but
   fixing it is a compiler-side change beyond this profiling task's scope.

### Bottom line

The patch's real profile is: **one large regression (owl_gc, chunk
allocator, custom-mem GC pacing), one tunable regression (owl_gc, auto-
compaction, fixed by the O= default change), one real win (zarith_pi,
locality/fault reduction), and no measurable effect on everything else.**
The mmap-batching the chunk allocator does is real and large in syscall
counts (140×+ on ocamlc/cpdf) but immaterial to wall time except where
allocation churn is the workload (zarith). The originally-reported
pplacer / eio / ocamlc slowdowns do not exist at the instruction level.

## Phase 5 — write-up — DONE

Final synthesis in `results.md` (tables, both plots, per-benchmark verdict,
mechanism, recommendations). Smoke-test scratch files removed. Harness
scripts are reusable for any (bench, runtime) pair.
