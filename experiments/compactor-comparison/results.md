# Compactor comparison — results

4-way comparison of `ocaml-5.5` (stock) vs. `ocaml-auto-compact` (auto
compaction only) vs. `socaml` (chunk-based pool allocator only) vs.
`socaml-auto-compact` (both). Run `lovelace-2026-09-01-Tue-095724`, 24
benchmarks with usable `olly` GC-stats sidecars (median of invocations
per cell). Extraction/plotting: `plot_results.py <run_dir> <output_dir>
ocaml-5.5,ocaml-auto-compact,socaml,socaml-auto-compact` (reads the
`olly_*.json` sidecars directly).

Plots: `plots/lovelace-2026-09-01-Tue-095724/`
- `heatmap_wall_time_ratio.png` — wall time vs. `ocaml-5.5`
- `heatmap_max_rss_ratio.png` — max RSS vs. `ocaml-5.5`
- `heatmap_gc_overhead_pct.png` — raw `gc_time / wall_time` %
- `heatmap_compactions.png` — raw compaction count per invocation
- `summary_stats.txt` — average / median / range across all benchmarks,
  per runtime, for each of the four metrics above (excludes benchmarks
  that failed to build on a given runtime; `n=.../24` notes how many
  contributed)

## Cross-benchmark summary (`summary_stats.txt`)

| runtime | wall_time avg | median | range | max RSS avg | median | range |
|---|---|---|---|---|---|---|
| ocaml-5.5 | 1.000x | 1.000x | 0.000x | 1.000x | 1.000x | 0.000x |
| ocaml-auto-compact | 0.991x | 0.998x | 0.367x | 1.001x | 1.000x | 0.050x |
| socaml (n=15/24) | 0.982x | 0.997x | 0.336x | 1.026x | 1.002x | 0.297x |
| socaml-auto-compact (n=15/24) | 0.985x | 0.993x | 0.397x | 1.028x | 1.013x | 0.299x |

The **median** wall-time ratio sits at ~0.99-1.00x for every non-stock
runtime — the typical benchmark is unaffected. The **range** (up to 0.40x,
i.e. a 40-percentage-point spread between the best- and worst-case
benchmark) shows the per-benchmark heatmap is doing real work: averages
and medians alone would hide both `zarith_pi`'s -22% win and `eio_fiber_
stream`'s +22% outlier on `socaml-auto-compact`. `gc_overhead` and
`compactions` summaries are in the txt file; compactions average/median/
range are all exactly 0 for every runtime here (see heatmap note above).

## Wall time (median, seconds)

| benchmark | ocaml-5.5 | ocaml-auto-compact | socaml | socaml-auto-compact |
|---|---|---|---|---|
| alt_ergo_fill | 9.11 | 8.67 | — | — |
| alt_ergo_unsat_smt2 | 15.06 | 15.04 | — | — |
| alt_ergo_yyll | 14.54 | 14.42 | — | — |
| cpdf_blacktext | 3.78 | 3.79 | 3.77 | 3.75 |
| cpdf_merge | 3.22 | 3.21 | 3.21 | 3.22 |
| cpdf_scale | 22.36 | 21.56 | 22.03 | 22.05 |
| cpdf_squeeze | 5.99 | 5.95 | 6.08 | 6.02 |
| eio_fiber_stream | 2.87 | 2.89 | 2.89 | 3.51 |
| frama_c_eva_sqlite | 10.16 | 12.11 | — | — |
| frama_c_eva_t | 0.61 | 0.60 | — | — |
| irmin_mem_rw | 7.61 | 7.61 | — | — |
| jsoo | 4.84 | 4.78 | — | — |
| liq_parse_typecheck | 15.47 | 15.46 | — | — |
| liq_video_frames_pool | 7.09 | 7.23 | 7.07 | 7.20 |
| menhir_ocamly | 17.24 | 17.15 | 17.13 | 17.12 |
| menhir_sql_parser | 1.88 | 1.86 | 1.86 | 1.84 |
| menhir_sysver | 11.80 | 11.90 | 11.92 | 11.80 |
| ocamlc_self_compile | 4.76 | 4.83 | 5.33 | 4.98 |
| ocamlformat_rocq | 3.15 | 3.22 | 3.02 | 3.15 |
| pplacer_testsuite | 10.20 | 10.16 | 10.43 | 9.85 |
| sedlex_tokenize | 2.85 | 2.35 | — | — |
| test_decompress | 3.04 | 3.05 | 2.83 | 2.51 |
| ydump_repeat | 4.53 | 3.75 | 4.19 | 3.74 |
| zarith_pi | 4.71 | 4.82 | 3.69 | 4.30 |

`—` = build failed on that runtime at the time of this run (`alt_ergo_*`,
`frama_c_*`, `irmin_mem_rw`, `jsoo`, `liq_parse_typecheck`, `sedlex_tokenize`
on `socaml`/`socaml-auto-compact` — the ppxlib/Parsetree mismatch fixed in
`auto-compact-tuning`'s Phase 10; this run predates that fix).

## Important points to note

- **`pplacer_testsuite` does NOT show the ~19-20% regression reported on
  turing** in this plain (non-falign) run — deltas are all within ±3.4%.
  This is the finding that motivated the falign experiment
  (`compactor-comparison-falign/`): the original regression turns out to
  be a code-alignment artifact of the build, not a real cost of either
  the new compactor or auto-compaction.
- **`zarith_pi` is genuinely faster on both `socaml` variants**: -21.7%
  on `socaml`, -8.7% on `socaml-auto-compact` (vs. stock), fully
  explained by the chunk-based allocator batching `mmap` calls instead of
  issuing one per 32KB pool — this benchmark's allocation churn is
  extreme enough that syscall batching alone accounts for the speedup
  (see `auto-compact-tuning/worklog.md` for the source-level trace).
- **That speedup has a memory cost**: `heatmap_max_rss_ratio.png` shows
  `zarith_pi` and `cpdf_merge` at +15-19% RSS on both socaml variants vs.
  stock — the 8MB chunk granularity over-allocates for smaller heaps.
  Most other benchmarks are within ±5% RSS regardless of runtime.
- **No benchmark in this suite ever compacts** (`heatmap_compactions.png`
  is uniformly 0) — `owl_gc`, the one benchmark that does compact under
  auto-compaction, isn't part of this 24-benchmark set (added to
  macro-benches later). This comparison alone can't show auto-compaction's
  cost; see `auto-compact-tuning/worklog.md` Phase 1-2 for that.
- **`liq_video_frames_pool` and `pplacer_testsuite` have the highest GC
  overhead in the suite** (89.2-89.3% and 80.2-80.4% respectively,
  `heatmap_gc_overhead_pct.png`), both completely flat across all four
  runtimes — large, real GC costs that are unrelated to compaction or
  the chunk allocator.
- **`eio_fiber_stream` on `socaml-auto-compact` (3.51s) looks like an
  outlier** vs. the other three runtimes (~2.87-2.89s, +22.3%) — not
  investigated further here; flagged for follow-up if this benchmark
  becomes relevant to future tuning work.
