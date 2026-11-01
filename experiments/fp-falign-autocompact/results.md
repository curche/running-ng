# Results -- falign x frame-pointers x auto-compaction (TASK 3)

Run `lovelace-2026-09-09-Wed-174336` (+ gap-fill rounds
`lovelace-2026-09-09-Wed-203616`, `lovelace-2026-09-09-Wed-205017`, merged
into the same directory). 8 runtimes, macro-benches full suite, 3
invocations/cell, `perf_grp1|re-25|md-2`. See `worklog.md` for the full
build/run/gap-fill narrative; this is the synthesis.

## Data completeness

232/256 (benchmark, runtime) cells (90.6%), 29 distinct benchmark programs
with data on all 8 runtimes. The only gap: `devkit_htmlstream` /
`devkit_stre` / `devkit_network` are missing on **all 8 runtimes**
uniformly -- a pre-existing macro-benches bug (`ahrefs-devkit.build.sh` sets
`PKG_CONFIG_PATH` for build-time PCRE1 discovery but never sets
`LD_LIBRARY_PATH`, so the resulting binary can't find `libpcre.so.1` at
exec time), unrelated to falign/fp/auto-compact and out of scope to fix
here (a macro-benches source change). Because it's uniform across every
column, it doesn't bias any comparison -- see `worklog.md` Phase 1 for the
two other gap classes found and fixed via `make gapfill`/`gapfill2`
(stale build artifacts on the 4 pre-existing switches, unrelated to this
experiment's design).

## The 8-cell matrix (full heatmaps: `plots/full/`)

| | no falign | falign |
|---|---|---|
| **no fp, no auto-compact** | `ocaml-5.5` -- reference | `ocaml-5.5-falign` |
| **fp, no auto-compact** | `ocaml-5.5-fp` | `ocaml-5.5-fp-falign` |
| **no fp, auto-compact** | `ocaml-auto-compact` | `ocaml-auto-compact-falign` |
| **fp, auto-compact** | `ocaml-auto-compact-fp` | `ocaml-auto-compact-fp-falign` |

Cross-benchmark wall-time summary (`plots/full/summary_stats.txt`, n=29):

| runtime | avg | median | min | max |
|---|---|---|---|---|
| ocaml-5.5 | 1.000x | 1.000x | 1.000x | 1.000x |
| ocaml-5.5-fp | 1.025x | 1.009x | 0.873x | 1.333x |
| ocaml-5.5-falign | 0.994x | 1.000x | 0.569x | 1.333x |
| ocaml-5.5-fp-falign | 1.023x | 1.011x | 0.874x | 1.333x |
| ocaml-auto-compact | 0.996x | 1.000x | 0.854x | 1.257x |
| ocaml-auto-compact-fp | 1.029x | 1.012x | 0.926x | 1.257x |
| ocaml-auto-compact-falign | 0.990x | 1.000x | 0.564x | 1.251x |
| ocaml-auto-compact-fp-falign | 1.027x | 1.007x | 0.836x | 1.255x |

## Tier B -- auto-compaction's own effect, isolated per codegen config

The key question this experiment was set up to answer: **does fp and/or
falign change how much auto-compaction costs?** Four 2-runtime comparisons
(`plots/group-*/`), each holding fp/falign fixed:

| group | a | b | wall avg | wall median | wall range |
|---|---|---|---|---|---|
| baseline | ocaml-5.5 | ocaml-auto-compact | 0.996x | 1.000x | 0.403x |
| fp | ocaml-5.5-fp | ocaml-auto-compact-fp | 1.008x | 1.002x | 0.499x |
| falign | ocaml-5.5-falign | ocaml-auto-compact-falign | 0.999x | 1.000x | 0.501x |
| fp+falign | ocaml-5.5-fp-falign | ocaml-auto-compact-fp-falign | 1.006x | 1.000x | 0.499x |

**Answer: no.** Auto-compaction's median cost is 1.000-1.002x in every
codegen configuration -- fp and falign do not change how much
auto-compaction costs. The compaction *counts* themselves are byte-for-byte
identical across all four auto-compact variants (avg 924, max 26806,
matching TASK 1's independently-confirmed 26,806 figure exactly) --
confirming fp/falign are pure codegen options that don't touch GC/compactor
behavior at all, only the auto-compact patch does.

In every group, the single benchmark driving both the max ratio (~1.25x)
and virtually all of the range is `owl_gc` -- exactly the one real cost
TASK 1/2 already identified (compaction-induced root-rescan at the
compiled-in `O=500` default, fixed by the `O=700-1000` recommendation both
tasks converged on). The group-min values (~0.75-0.85x) are noise from two
near-zero-wall-time benchmarks (`goblint` ~0.35-0.41s, `infer_default`
~0.03-0.04s), not real signal.

## Tier A -- fp and falign's own effects (independent of auto-compaction)

Reading straight down the full-suite table (`ocaml-5.5` as reference):

- **falign alone** (`ocaml-5.5` -> `ocaml-5.5-falign`): avg 0.994x, median
  1.000x -- a wash for the typical benchmark, exactly reproducing
  `../compactor-comparison-falign/results.md`'s finding on this same
  24(+)-benchmark suite.
- **fp alone** (`ocaml-5.5` -> `ocaml-5.5-fp`): avg 1.025x, median 1.009x --
  a small, consistent ~1-2.5% overhead, as expected from the extra
  push/pop-rbp prologue/epilogue `--enable-frame-pointers` adds to every
  function call. This axis hadn't been measured on this patch/suite before
  this experiment.
- **fp+falign together** (1.023x avg / 1.011x median) tracks fp alone
  closely -- the two costs don't compound or cancel in aggregate.

## Deep dive: `eio_fiber_stream`'s fp cost is real, not noise

The full-suite table shows `eio_fiber_stream` swinging from 2.77s to
3.09s across the 8 cells -- initially assumed to be measurement noise
(TASK 2 had inferred its harness-observed swings didn't reproduce under
perf, for a different runtime comparison). A follow-up investigation with
pinned, repeated measurement (`taskset` + ASLR off, `perf stat -r 30`)
found this specific swing is **not noise**: it reproduces at ±0.02% stddev
over 30 reps and is driven entirely by frame pointers (`ocaml-5.5-fp` and
`ocaml-auto-compact-fp` land on identical instruction counts and wall
times -- auto-compaction contributes nothing). fp alone costs this
benchmark +9.7% instructions / +5.2% wall time here, well above the
~1-2.5% suite median above, because a differential flamegraph shows the
extra instructions concentrated almost entirely in `caml_ml_mutex_lock`/
`unlock` (+65% / OCaml-runtime C functions that gain a frame-pointer
prologue on every call) -- tiny, hot functions called millions of times by
this benchmark's 4-producer/4-consumer design, so the fixed per-call fp
tax dominates far more here than on compute-bound benchmarks. Full
write-up, decomposition table, and interactive flamegraphs:
`../eio-deep-dive/{results.md,report.html}`.

## Notable interaction: `frama_c_eva_sqlite`

The one benchmark where fp and falign visibly interact rather than acting
independently:

| runtime | wall time (s) |
|---|---|
| ocaml-5.5 | 18.05 |
| ocaml-5.5-fp | 19.98 |
| ocaml-5.5-falign | **10.27** |
| ocaml-5.5-fp-falign | 21.33 |

falign *alone* is a dramatic **-43%** for this benchmark specifically (not
representative of the suite median above) -- but adding fp on top of
falign erases the entire speedup and lands *slower* than plain stock
(+18%). The auto-compact runtimes show the identical pattern (18.12 / 21.83
/ **10.18** / 21.70), confirming this is a codegen/instruction-layout
interaction independent of the auto-compaction patch. Plausibly an
icache-alignment effect specific to frama-c's EVA analyzer's code shape
(similar in kind to `ocamlc_self_compile`'s large, consistent falign
benefit noted in the prior falign report) -- not investigated further here,
flagged for anyone tuning frama-c specifically.

## Bottom line

For the auto-compaction patch: **falign and frame-pointers are both
orthogonal to auto-compaction's cost** -- the patch costs the same
(dominated entirely by `owl_gc`, already understood and already have a
fix recommendation from TASK 1) regardless of which of the 4 codegen
configurations it's built with. Frame pointers add a small, independent
~1-2.5% tax of their own (unsurprising, matches their known runtime cost
elsewhere); falign is a wash except for isolated per-benchmark swings
(`frama_c_eva_sqlite`, `ocamlc_self_compile`) that pre-date and are
unrelated to this patch.

## Files

- `plots/full/` -- 8-runtime heatmaps (cells show both ratio and absolute
  value, e.g. `+2.0% (10.2s)`, baseline column as `10.0s (ref)`), plus
  `wall_time_table.txt` / `max_rss_table.txt` (the same numbers as plain
  text) and `summary_stats.txt` (cross-benchmark aggregate ratio stats).
- `plots/group-{baseline,fp,falign,fp-falign}/` -- the four Tier-B
  within-group comparisons, same file set as above.
- `worklog.md` -- full narrative, including the two pre-existing
  environment-bug classes found and the gap-fill fix.
