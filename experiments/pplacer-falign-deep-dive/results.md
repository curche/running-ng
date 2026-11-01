# pplacer_testsuite falign mechanism -- results

Follow-up to TASK 3 (`../fp-falign-autocompact/`). `pplacer_testsuite` is the
benchmark this whole investigation originally started from (the "turing
regression"), and it's the one real, non-trivial falign-alone slowdown left
in the 8-way table (+3.2%, 11.22s -> 11.58s). The working theory since
`../compactor-comparison-falign/results.md` has been "code-alignment /
icache-layout artifact" -- but that was inferred purely from wall-time
deltas, never confirmed with hardware counters. This investigation checked
it directly, using the same pinned-measurement + perf-counter + flamegraph
methodology as `../eio-deep-dive/`.

## Headline: the icache-miss theory is wrong. It's a front-end/decode-bandwidth tax.

Under `taskset -c 3` + `setarch -R` + `perf stat -r 20`:

| metric | stock | falign | delta |
|---|---|---|---|
| wall time | 11.211s | 11.497s | **+2.55%** |
| cycles | 39.91B | 41.09B | +2.96% |
| instructions | 133.67B | 133.83B | +0.12% (flat) |
| IPC | 3.350 | 3.257 | **-2.75%** |
| cache-misses | 29.18M | 25.24M | **-13.5%** |
| L1i-misses (frontend_retired.l1i_miss) | 29.13M | 26.62M | **-8.6%** |
| iTLB-misses | 543.7K | 530.6K | -2.4% |
| branch-misses | 437.7M | 430.4M | -1.7% |

Every cache/TLB/branch-miss counter **decreased** under falign. Instruction
count barely moved. Yet cycles rose and IPC dropped by nearly 3%. This
directly rules out "code landed in a worse cache-alignment spot and now
misses more" -- if anything falign's layout has *fewer* memory-hierarchy
problems here, not more.

Topdown microarchitecture analysis (`perf stat -M tma_frontend_bound`,
r=10, single metric group, no multiplexing) confirms where the cycles
actually went:

| topdown category | stock | falign | delta |
|---|---|---|---|
| Frontend Bound % | 23.1% | **26.0%** | **+2.9pp (+12.6% relative)** |
| topdown-fe-bound (raw slots) | 56.80B | 65.29B | +15.0% |
| topdown-bad-spec (raw slots) | 49.14B | 45.96B | -6.5% |
| topdown-be-bound (raw slots) | 20.13B | 20.88B | +3.7% |
| topdown-retiring (raw slots) | 115.68B | 116.08B | +0.3% (flat) |

Textbook front-end/fetch-bound signature: Frontend Bound rises, Bad
Speculation *falls* (matches the branch-miss decrease), Retiring stays flat
(matches the flat instruction count). The CPU pipeline is measurably more
often stalled waiting for instructions to be fetched/decoded, not waiting
on memory or recovering from mispredicts.

## Where: diffuse, not concentrated

A raw stack-diff flamegraph (`flamegraphs/diff2.svg`) is **not trustworthy
here** -- `[unknown]`-attributed weight nearly doubles under falign (5.02B
-> 8.91B, +77%), meaning DWARF unwinding resolves noticeably worse on the
falign binary for some fraction of samples (plausibly the alignment padding
itself interacting with CFI/frame-pointer-adjacent heuristics). The naive
top-mover list is dominated by this artifact (`[unknown];do_some_marking`
appearing to jump from 0 to 3.9B is unwind noise, not a real new cost).

Redone as a **leaf-function (self-time), fraction-of-total** comparison
(robust to unwind-depth differences -- see `results.md` script in
`worklog.md`), the picture is clean: growth is **diffuse across dozens of
unrelated functions** -- `do_some_marking` (the GC mark function, already
64.5% of total runtime -- pplacer is GC-heavy, matches its
`custom_block_finalisation`/`ffi_bulk` tags from `macro_base.yml`) gains
+1.05 percentage points, but so does `caml_shared_try_alloc`,
`try_update_object_header`, `oldify_mopup`, `caml_ba_slice`, GSL library
calls, OCaml stdlib `Lexing`/`Parsing`, `__memcmp_avx2_movbe`, `_int_malloc`
-- each by a small amount, spread across the whole call graph. `do_some_marking`
shows the largest *absolute* delta simply because it's the largest function
to begin with (64.5% of runtime), not because it was specifically targeted.

This diffuse, no-single-hot-path pattern is exactly what you'd expect from
a **blanket per-function code-size tax**: `-falign-functions=64` pads
*every* function to a 64-byte boundary. For a program with many small,
frequently-called functions (this GC-heavy OCaml benchmark has plenty --
GC internals, small stdlib helpers), that padding inflates .text size and
costs front-end fetch/decode cycles broadly, roughly in proportion to how
much of the runtime each function already accounted for -- not concentrated
in whichever function happened to land badly.

## Mitigation, given this mechanism

The confirmed mechanism changes which mitigations make sense:

1. **Don't apply `-falign-functions=64` globally.** Simplest fix, still
   valid -- TASK 3 already showed it's a wash in aggregate (helps some
   benchmarks a lot, e.g. `frama_c_eva_sqlite` -43%, `menhir_sql_parser`
   -11.5%; hurts others, e.g. this one).
2. **Try a smaller alignment value (16 or 32 instead of 64) -- now the
   best-supported option.** Since the mechanism is confirmed to be raw
   padding volume (not layout luck), a smaller value directly and
   predictably reduces the front-end tax, unlike under the old "landed
   badly" theory where changing the value would've been a re-roll of the
   same dice. Worth sweeping `-falign-functions={16,32,64}` on this
   benchmark specifically to find where the frontend-bound cost stops
   being worth whatever benefit falign brings elsewhere.
3. **PGO or a post-link layout tool (e.g. LLVM BOLT)** instead of a
   blanket compile flag -- pads/reorders based on real hot-path profiling
   rather than uniformly bloating every function, which is exactly the
   failure mode identified here.
4. **Per-function targeted alignment is NOT a good fit here** (unlike a
   scenario with one specific regressed hot function) -- the cost is
   diffuse across dozens of functions, so there's no single function to
   annotate. This mitigation remains viable for a benchmark with a
   concentrated regression, just not this one.

## Files

- `stat/pplacer_testsuite__ocaml-5.5.stat_r20.txt`,
  `stat/pplacer_testsuite__ocaml-5.5-falign.stat_r20.txt` -- raw
  `perf stat -r 20` output (cache/TLB/branch counters).
- `flamegraphs/{ocaml-5.5,ocaml-5.5-falign}.svg` -- individual on-CPU
  flamegraphs (8 reps each merged, dwarf call-graph, 999Hz).
- `flamegraphs/diff2.svg` -- raw normalized stack diff. Caveat above
  applies -- prefer the leaf-function table in this file over eyeballing
  this SVG's top frames.
- `report.html` -- interactive write-up (topdown chart, leaf-function
  table, flamegraphs), same format as `../eio-deep-dive/report.html`.
