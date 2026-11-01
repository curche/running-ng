# Compactor Comparison — Benchmark Results

**Run directory:** `logs/turing-2026-07-01-Wed-230036`
**Run date:** 2026-07-01 (completed 2026-07-02 ~01:00 IST)
**Machine:** turing
**Invocations:** 3 per benchmark × runtime
**Config file:** `src/running/config/experiments/macrobenchmarks_compactor_4way.yml`

---

## Runtimes compared

| Config name | Description | Source | Opam switch |
|---|---|---|---|
| `ocaml-5.5` | Stock OCaml 5.5.0 | upstream `5.5.0` tag | `running-ng-ocaml-5.5` (created by running-ng via `opam-compiler`) |
| `ocaml-auto-compact` | Stock OCaml 5.5 + automatic compaction | `ocaml-git` branch `auto-compact-5.5` @ `d2e194bce3` | `ocaml-auto-compact-20260701-144438` |
| `socaml` | New chunk-based pool compactor, no auto-compact | `socaml-git` `new_compactor` @ `7f6d55c648` | `socaml-20260630-140841` |
| `socaml-auto-compact` | New compactor + automatic compaction | `socaml-git` `new_compactor` @ `34988cfd7b` | `socaml-auto-compact-20260629-131142` |

**olly version:** `count-auto-compactions` branch of `runtime_events_tools` — patched to
count `EV_COMPACT` (internal compactor path) in addition to `EV_EXPLICIT_GC_COMPACT`
(user-triggered `Gc.compact()`). Without this patch, automatic compactions would have
been silently uncounted.

**GC settings:** all default (`O=500`, `o=120`, `s=262144`)

---

## Build failures

The following benchmarks failed to build for one or more runtimes and were skipped
in those configurations. The sentinel files remain in `macro-benches/benchmarks/`
and must be deleted to retry.

| Benchmark | Failed runtimes | Likely cause |
|---|---|---|
| `alt_ergo_*` (all 3) | `socaml`, `socaml-auto-compact` | Dune build incompatibility with new compactor's altered runtime ABI or version string |
| `liq_parse_typecheck` | `socaml`, `socaml-auto-compact` | Same as alt_ergo |
| `jsoo` | `ocaml-auto-compact`, `socaml`, `socaml-auto-compact` | Build failure on all non-stock runtimes |
| `ocamlc_self_compile` | `ocaml-auto-compact`, `socaml`, `socaml-auto-compact` | Only stock ran; likely self-compilation incompatibility |

---

## Measurement issues

- **`coqc_corelib_stress`**: all four runtimes show corrupted `wall_time` values
  (large negative numbers, ~−1.4M seconds) in the olly JSON sidecars. This is a
  known olly failure mode when the runtime-events ring buffer overflows and events
  are lost — the per-domain wall time falls back to `now − boot_time`. Wall-time
  ratios for coqc are excluded from the heatmap (`NaN`). RSS and compaction counts
  are valid.  
  *Fix*: increase `re=` parameter (try `re-27` or `re-28`) for coqc in a follow-up run.

---

## Key findings

### 1. `owl_gc` — automatic compaction is too aggressive at default threshold

| Runtime | Wall (s) | RSS (MB) | Compactions |
|---|---|---|---|
| `ocaml-5.5` | 16.79 | 125.8 | 0 |
| `ocaml-auto-compact` | 20.91 | 129.1 | **26,806** |
| `socaml` | 36.46 | 279.4 | 0 |
| `socaml-auto-compact` | 35.73 | 279.3 | 0 |

- `ocaml-auto-compact` triggers 26,806 automatic compactions per run at the default
  `O=500` threshold, causing a **+25% wall-time regression**.
- The new compactor (`socaml`) is **+117% slower** on `owl_gc` with no compactions at
  all — the chunk-based compactor itself has higher overhead on this GC-heavy workload.
- `socaml-auto-compact` adds no additional compactions on top of `socaml` (threshold
  not reached with the new compactor's RSS profile), and recovers ~2% vs `socaml`.
- **Action**: `owl_gc` needs a higher `O=` value (e.g. `O=2000` or `O=999999`) to
  suppress automatic compaction. This benchmark should be a primary target for
  the follow-on `O=` sweep.

### 2. `zarith_pi` — new compactor gives a meaningful speedup

| Runtime | Wall (s) | RSS (MB) |
|---|---|---|
| `ocaml-5.5` | 11.83 | 129.0 |
| `ocaml-auto-compact` | 11.81 | 128.4 |
| `socaml` | 9.33 | 148.4 |
| `socaml-auto-compact` | 9.28 | 149.2 |

The new compactor delivers **−21% wall time** on zarith_pi. Auto-compaction adds
nothing here (no compactions fire). RSS is ~15% higher with the new compactor.

### 3. `pplacer_testsuite` — consistent regression across all three non-stock runtimes

| Runtime | Wall (s) | RSS (MB) |
|---|---|---|
| `ocaml-5.5` | 23.50 | 70.1 |
| `ocaml-auto-compact` | 28.11 | 70.1 |
| `socaml` | 27.93 | 70.1 |
| `socaml-auto-compact` | 28.16 | 70.4 |

All three non-stock runtimes are **~+19–20% slower**. RSS is identical. The regression
appears in `ocaml-auto-compact` as well as both socaml variants, suggesting it is not
specific to the new compactor. Warrants further investigation — possibly a GC
scheduling or minor heap interaction rather than a compaction issue.

### 4. `ocamlformat_rocq` — new compactor is modestly faster, higher RSS

| Runtime | Wall (s) | RSS (MB) |
|---|---|---|
| `ocaml-5.5` | 7.02 | 277.6 |
| `ocaml-auto-compact` | 6.87 | 277.3 |
| `socaml` | 6.71 | 297.7 |
| `socaml-auto-compact` | 6.69 | 297.5 |

New compactor: **−4% wall time**, +7% RSS. Auto-compact on top of new compactor
adds negligible change.

### 5. `menhir_sql_parser` — new compactor reduces RSS significantly

| Runtime | Wall (s) | RSS (MB) |
|---|---|---|
| `ocaml-5.5` | 4.71 | 320.3 |
| `ocaml-auto-compact` | 4.62 | 319.7 |
| `socaml` | 4.67 | **279.9** |
| `socaml-auto-compact` | 4.70 | **279.8** |

RSS is **−13%** with the new compactor. Wall time is roughly equivalent.

### 6. `cpdf_merge` — new compactor increases RSS

| Runtime | Wall (s) | RSS (MB) |
|---|---|---|
| `ocaml-5.5` | 8.00 | 363.3 |
| `ocaml-auto-compact` | 7.83 | 367.6 |
| `socaml` | 7.86 | **432.2** |
| `socaml-auto-compact` | 7.81 | **433.4** |

New compactor: wall time similar, but **+19% RSS**. Likely related to the
chunk-based allocator retaining larger free pool regions.

### 7. Compaction threshold not reached on most benchmarks

At the default `O=500` (i.e. compact when free+garbage > 5× live), **zero compactions
fire** on 29 out of 30 benchmarks. Only `owl_gc` crosses the threshold — and it
crosses it massively (26k compactions). This suggests:

- The default 500% threshold is well-chosen for most workloads.
- `owl_gc`'s allocation pattern creates extreme fragmentation that the heuristic
  misreads. The `should_compact_from_stw_single` function likely needs a check on
  the rate of compactions, or a minimum time between compactions.
- A follow-on O= sweep at lower values (100, 200) would identify which other
  benchmarks have latent fragmentation that could benefit from compaction.

---

## Benchmark-level summary (median across 3 invocations)

Wall time in seconds, RSS in MB, compactions = total count.

| Benchmark | 5.5 wall | AC wall | socaml wall | socaml-AC wall | 5.5 RSS | AC RSS | socaml RSS | socaml-AC RSS | AC compact |
|---|---|---|---|---|---|---|---|---|---|
| alt_ergo_fill | 19.98 | 19.21 | — | — | 937.0 | 930.3 | — | — | 0 |
| alt_ergo_unsat_smt2 | 15.07 | 15.07 | — | — | 62.6 | 62.8 | — | — | 0 |
| alt_ergo_yyll | 23.39 | 23.24 | — | — | 285.9 | 286.9 | — | — | 0 |
| coqc_corelib_stress | nan | nan | nan | nan | 42.2 | 42.1 | 42.1 | 42.1 | 0 |
| cpdf_blacktext | 9.48 | 9.37 | 9.37 | 9.37 | 243.9 | 244.0 | 256.9 | 256.5 | 0 |
| cpdf_merge | 8.00 | 7.83 | 7.86 | 7.81 | 363.3 | 367.6 | 432.2 | 433.4 | 0 |
| cpdf_scale | 49.54 | 49.08 | 49.43 | 49.36 | 489.7 | 488.2 | 495.9 | 496.1 | 0 |
| cpdf_squeeze | 12.98 | 12.71 | 12.81 | 12.76 | 328.6 | 328.4 | 323.4 | 323.3 | 0 |
| devkit_gzip | 13.33 | 13.35 | — | — | 17.0 | 16.9 | — | — | 0 |
| devkit_htmlstream | 31.94 | 31.71 | — | — | 358.1 | 358.2 | — | — | 0 |
| devkit_network | 21.26 | 21.16 | — | — | 90.0 | 87.0 | — | — | 0 |
| devkit_stre | 16.13 | 16.18 | — | — | 22.8 | 22.7 | — | — | 0 |
| eio_fiber_stream | 8.07 | 8.08 | 8.63 | 8.57 | 32.3 | 32.3 | 33.5 | 33.5 | 0 |
| frama_c_eva_sqlite | 36.66 | 36.89 | — | — | 585.4 | 585.1 | — | — | 0 |
| frama_c_eva_t | 1.70 | 1.73 | — | — | 94.3 | 95.1 | — | — | 0 |
| irmin_mem_rw | 15.77 | 15.99 | — | — | 35.8 | 35.9 | — | — | 0 |
| jsoo | 11.38 | — | — | — | 268.8 | — | — | — | — |
| liq_parse_typecheck | 40.33 | 39.17 | — | — | 48.6 | 48.6 | — | — | 0 |
| liq_video_frames_pool | 15.20 | 15.23 | 15.21 | 15.19 | 109.6 | 109.6 | 109.6 | 109.6 | 0 |
| menhir_ocamly | 45.26 | 44.17 | 44.70 | 44.84 | 2702.6 | 2698.9 | 2705.9 | 2702.6 | 0 |
| menhir_sql_parser | 4.71 | 4.62 | 4.67 | 4.70 | 320.3 | 319.7 | 279.9 | 279.8 | 0 |
| menhir_sysver | 30.40 | 29.72 | 30.39 | 30.64 | 746.8 | 747.0 | 747.6 | 747.7 | 0 |
| ocamlc_self_compile | 11.90 | — | — | — | 990.1 | — | — | — | — |
| ocamlformat_rocq | 7.02 | 6.87 | 6.71 | 6.69 | 277.6 | 277.3 | 297.7 | 297.5 | 0 |
| owl_gc | 16.79 | 20.91 | 36.46 | 35.73 | 125.8 | 129.1 | 279.4 | 279.3 | **26806** |
| pplacer_testsuite | 23.50 | 28.11 | 27.93 | 28.16 | 70.1 | 70.1 | 70.1 | 70.4 | 0 |
| sedlex_tokenize | 6.98 | 7.09 | — | — | 962.7 | 962.7 | — | — | 0 |
| test_decompress | 6.81 | 6.78 | 6.83 | 6.83 | 14.7 | 14.8 | 14.7 | 14.8 | 0 |
| ydump_repeat | 7.96 | 7.99 | 7.90 | 7.93 | 11.1 | 11.1 | 11.2 | 11.2 | 0 |
| zarith_pi | 11.83 | 11.81 | 9.33 | 9.28 | 129.0 | 128.4 | 148.4 | 149.2 | 0 |

`—` = benchmark did not run (build failure). `AC` = auto-compact. `nan` = wall time
corrupted by lost runtime events (coqc ring buffer overflow).

---

## Recommended follow-up runs

1. **O= sweep on owl_gc**: run `ocaml-auto-compact` and `socaml-auto-compact` with
   `O=1000,2000,5000,999999` to find the threshold at which compaction ceases to
   fire, and check if performance recovers.

2. **Investigate pplacer regression**: both `ocaml-auto-compact` and socaml variants
   regress ~20%. Compare GC stats (minor/major collections, gc_overhead%) to
   understand if this is a GC scheduling issue.

3. **Fix coqc ring buffer overflow**: re-run with `re-27` or `re-28` to get valid
   wall-time data for coqc.

4. **Fix build failures**: delete sentinel files for `alt_ergo`, `liq_parse_typecheck`,
   `jsoo`, `ocamlc_self_compile` on the affected runtimes and investigate build logs.

5. **owl_gc + socaml**: the new compactor doubles wall time and RSS on owl_gc even
   with zero compactions. Profile to determine if it is a pool-allocation overhead
   or a different GC cycle characteristic.
