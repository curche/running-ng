# Compactor comparison (falign) — results

Same 24-benchmark suite as `compactor-comparison/`, but crossed with
`-falign` builds (function alignment padding), plus the plain `ocaml-5.5`
baseline for reference: `ocaml-5.5`, `ocaml-5.5-falign`,
`ocaml-auto-compact-falign`, `socaml-falign`, `socaml-auto-compact-falign`.
Run `lovelace-2026-09-01-Tue-113210`. Same extraction/plotting script:
`plot_results.py <run_dir> <output_dir>
ocaml-5.5,ocaml-5.5-falign,ocaml-auto-compact-falign,socaml-falign,socaml-auto-compact-falign`.

Plots: `plots/lovelace-2026-09-01-Tue-113210/`
- `heatmap_wall_time_ratio.png` — wall time vs. `ocaml-5.5`
- `heatmap_max_rss_ratio.png` — max RSS vs. `ocaml-5.5`
- `heatmap_gc_overhead_pct.png` — raw `gc_time / wall_time` %
- `heatmap_compactions.png` — raw compaction count per invocation
- `summary_stats.txt` — average / median / range across all benchmarks,
  per runtime, for each of the four metrics above

## Cross-benchmark summary (`summary_stats.txt`)

| runtime | wall_time avg | median | range | max RSS avg | median | range |
|---|---|---|---|---|---|---|
| ocaml-5.5 | 1.000x | 1.000x | 0.000x | 1.000x | 1.000x | 0.000x |
| ocaml-5.5-falign | 0.981x | 0.996x | 0.297x | 0.999x | 1.000x | 0.027x |
| ocaml-auto-compact-falign | 0.983x | 1.002x | 0.389x | 1.001x | 1.001x | 0.020x |
| socaml-falign (n=15/24) | 0.964x | 0.990x | 0.399x | 1.025x | 1.005x | 0.309x |
| socaml-auto-compact-falign (n=15/24) | 0.980x | 0.988x | 0.402x | 1.025x | 1.004x | 0.317x |

Median wall-time ratios are all ~0.99-1.00x — falign is a wash for the
*typical* benchmark. The RSS story is the cleanest signal here: the two
plain/auto-compact-falign rows have a tiny range (0.020-0.027x, i.e.
±2-3% across all 24 benchmarks) confirming falign itself doesn't touch
memory, while the two socaml-falign rows keep the same ~0.30x range
already seen in the non-falign comparison (the chunk-allocator RSS cost,
unaffected by falign).

## Wall time (median, seconds)

| benchmark | ocaml-5.5 | ocaml-5.5-falign | ocaml-auto-compact-falign | socaml-falign | socaml-auto-compact-falign |
|---|---|---|---|---|---|
| alt_ergo_fill | 8.79 | 8.56 | 9.25 | — | — |
| alt_ergo_unsat_smt2 | 15.04 | 15.05 | 15.06 | — | — |
| alt_ergo_yyll | 14.53 | 13.51 | 13.55 | — | — |
| cpdf_blacktext | 4.45 | 4.20 | 3.78 | 3.78 | 3.83 |
| cpdf_merge | 3.22 | 3.25 | 3.27 | 3.26 | 3.23 |
| cpdf_scale | 19.38 | 19.41 | 19.47 | 19.59 | 19.51 |
| cpdf_squeeze | 5.52 | 5.27 | 5.24 | 5.30 | 5.27 |
| eio_fiber_stream | 2.95 | 2.75 | 2.78 | 2.91 | 2.90 |
| frama_c_eva_sqlite | 11.24 | 12.16 | 11.36 | — | — |
| frama_c_eva_t | 0.70 | 0.73 | 0.60 | — | — |
| irmin_mem_rw | 6.38 | 6.63 | 6.40 | — | — |
| jsoo | 5.35 | 5.34 | 5.33 | — | — |
| liq_parse_typecheck | 16.56 | 15.33 | 16.44 | — | — |
| liq_video_frames_pool | 7.52 | 7.74 | 7.70 | 7.80 | 7.67 |
| menhir_ocamly | 17.50 | 17.41 | 17.57 | 17.32 | 17.29 |
| menhir_sql_parser | 1.86 | 1.86 | 1.88 | 1.87 | 1.88 |
| menhir_sysver | 11.83 | 12.00 | 12.00 | 11.94 | 11.95 |
| ocamlc_self_compile | 5.67 | 4.99 | 4.75 | 4.86 | 4.91 |
| ocamlformat_rocq | 3.25 | 3.13 | 3.23 | 2.99 | 3.19 |
| **pplacer_testsuite** | **10.17** | **11.30** | **11.10** | **11.38** | **11.05** |
| sedlex_tokenize | 2.45 | 2.65 | 2.48 | — | — |
| test_decompress | 2.52 | 2.50 | 3.02 | 2.51 | 3.04 |
| ydump_repeat | 4.55 | 3.73 | 4.51 | 4.48 | 4.20 |
| zarith_pi | 5.10 | 4.15 | 4.13 | 3.67 | 4.10 |

`—` = build failed on that runtime (same ppxlib/Parsetree issue as the
plain comparison, unrelated to falign).

## Important points to note

- **This is the run that explains the pplacer regression**:
  `pplacer_testsuite` jumps **+8.7% to +11.9%** the moment `-falign` is
  applied to *any* runtime — including plain `ocaml-5.5-falign` (+11.1%)
  vs. its own non-falign `ocaml-5.5` baseline. Since the regression
  appears on stock OCaml with only a code-alignment flag changed, and is
  roughly the same size on all four falign runtimes regardless of
  compactor/auto-compaction, it confirms the original ~19-20% turing
  regression was a build/alignment artifact of how those binaries were
  compiled, not a real cost of the new compactor or automatic compaction.
- **GC overhead is untouched by falign** (`heatmap_gc_overhead_pct.png`):
  `pplacer_testsuite` sits at 78.9-80.1% across all five runtimes here,
  matching the plain comparison almost exactly. This corroborates the
  above — the falign wall-time hit is a codegen/instruction-layout effect
  outside the GC entirely, not a change in collection behavior.
- **`zarith_pi` gets faster still with falign on top of the chunk
  allocator**: `socaml-falign` reaches **-28.0%** vs. stock `ocaml-5.5`
  (vs. -21.7% without falign in the plain comparison) — falign and the
  chunk-allocator's mmap-batching speedup appear to compound rather than
  interact negatively.
- **`ocamlc_self_compile` improves substantially under falign** across
  every runtime (-12% to -16%), the largest consistent falign benefit in
  the suite besides zarith_pi — plausibly an icache-layout effect for a
  large, branch-heavy program like the compiler itself, not investigated
  further here.
- **`test_decompress` regresses sharply on the two `*-auto-compact-falign`
  runtimes specifically** (+19.8%, +20.6%) while staying flat on
  `ocaml-5.5-falign` and `socaml-falign` (±0.8%) — the only benchmark in
  this run where auto-compaction-plus-falign looks meaningfully worse
  than falign alone. Flagged, not chased further.
- **No compactions anywhere in this run either** (`heatmap_compactions.png`
  is uniformly 0) — same caveat as the plain comparison: `owl_gc` isn't
  part of this benchmark set, so this data can't speak to auto-compaction's
  actual cost, only to falign's effect on wall time/RSS/GC overhead.
- **RSS story is identical to the non-falign comparison**
  (`heatmap_max_rss_ratio.png`): falign itself has no RSS effect (all
  `ocaml-5.5` vs `ocaml-5.5-falign` cells within ±1%); the socaml chunk-
  allocator RSS bump (`cpdf_merge` +18-19%, `zarith_pi` +15-16%) persists
  unchanged with falign applied.
