# worklog -- fp-falign-autocompact (TASK 3)

Append-only. Follows the TASK 1/2 convention (see
`../auto-compact-tuning/worklog.md`, `../perf-slowdown-analysis/worklog.md`).

## Phase 0 -- setup

- Scoped per user decision: auto-compaction patch only (not socaml chunk
  allocator, already covered in TASK 1/2); full macro-benches suite (not a
  representative subset).
- Confirmed via `opam switch list` that 4 of the 8 needed switches already
  exist (`running-ng-ocaml-5.5`, `running-ng-ocaml-5.5-falign`,
  `running-ng-ocaml-auto-compact`, `running-ng-ocaml-auto-compact-falign`),
  built for `../compactor-comparison/` and `../compactor-comparison-falign/`.
- Confirmed running-ng's `OCaml` runtime type builds switches lazily
  (`running/runtime.py:_ensure_switch`) keyed on `running-ng-<name>`, so
  reusing the exact same runtime names in `config.yml` means the 4 existing
  switches are picked up unchanged and only the 4 new frame-pointer variants
  get built.
- Confirmed `--enable-frame-pointers` is a supported OCaml configure flag
  (already used in `running-ng/src/running/config/experiments/
  fp_flambda_macrobenchmarks.yml` for a prior, unrelated 5.4.1 fp/flambda
  sweep) and appears in the auto-compact fork's `configure.ac`.
- Wrote `config.yml` (8 runtimes, full suite, Tier A + Tier B comparisons),
  `config-smoke.yml` (4-benchmark/1-invocation reduction for a fast switch-
  build + sanity pass), `Makefile`, `README.md`, `SETUP.md`, this worklog.
- Copied `plot_results.py` from `../compactor-comparison-falign/` unmodified
  (already generic over an arbitrary runtime list via CLI args).

## Phase 0 (cont.) -- `make smoke` result

Run id `lovelace-2026-09-09-Wed-172600`. All 4 new opam switches
(`running-ng-ocaml-5.5-fp`, `running-ng-ocaml-5.5-fp-falign`,
`running-ng-ocaml-auto-compact-fp`, `running-ng-ocaml-auto-compact-fp-falign`)
built cleanly from source via `opam compiler create ... --configure-command
"./configure --enable-frame-pointers [...]"` -- no errors, confirmed present
in `opam switch list` afterward alongside the 4 pre-existing switches (8/8).
All 4 smoke benchmarks (`zarith_pi`, `owl_gc`, `pplacer_testsuite`,
`cpdf_squeeze`) built and ran on all 8 runtimes with no build failures or
timeouts (scanned log for error/fail/traceback -- only benign compiler
warnings in vendored C stubs and a pre-existing dune-project typo warning
unrelated to this experiment). 32/32 expected `olly_*.json` sidecars
present (4 benchmarks x 8 runtimes x 1 invocation).

Ran `plot_results.py` against the smoke run as an end-to-end pipeline check
(output discarded, not committed): ratios and stats compute correctly for
all 8 columns, and critically `ocaml-auto-compact*`'s owl_gc compaction
count peaks at exactly **26,806** -- matching TASK 1's independently
confirmed original-machine figure (see `../auto-compact-tuning/worklog.md`)
almost exactly, and identical across all 4 auto-compact variants (fp/falign
don't change *how many* times it compacts, only wall-clock/codegen --
consistent with expectations). Stock variants show 0 compactions
throughout, also as expected. This cross-check gives good confidence the
harness, switches, and metric extraction are all correct before committing
to the full run.

No `benchmarks:` block override needed for the full run (config.yml uses
macro_base.yml's full default, all 23 enabled suites); no timeout overrides
applied either (unlike the older `macrobenchmarks_compactor_4way_falign.yml`
which forced `macro-coq-monorepo.timeout: 300` -- that suite's build issues
are reported fixed since TASK 1, so left at macro_base's default 900s).

Proceeding to `make run` (full 8-runtime x full-suite x 3-invocation sweep).

## Phase 1 -- `make run` result + two pre-existing environment bugs found

Run id `lovelace-2026-09-09-Wed-174336`, ~2h wall (17:43-19:45). Exit 0, no
crashes. Data completeness: 221/256 (benchmark, runtime) cells got a
sidecar JSON with all 3 invocations. 35 cells missing, in two distinct,
unrelated classes -- neither caused by this experiment's config, both
pre-existing macro-benches/switch state:

**Class 1 -- suite-wide, all 8 runtimes (24 cells, NOT fixed):**
`devkit_htmlstream` / `devkit_stre` / `devkit_network` fail identically on
every runtime with `error while loading shared libraries: libpcre.so.1:
cannot open shared object file`. `ahrefs-devkit.build.sh` sets
`PKG_CONFIG_PATH` for the *build*-time pkg-config lookup of the vendored
PCRE1 (`vendor/pcre1-install/`) but never sets `LD_LIBRARY_PATH` for the
*run*-time dynamic linker, so the resulting binary can't find
`libpcre.so.1` at exec time. This affects every runtime equally (it's a
macro-benches build-script gap, orthogonal to falign/fp/auto-compact), so
it doesn't bias any Tier A/B comparison -- just leaves those 3 programs
uniformly "--". Not fixed here (would require editing
`ahrefs-devkit.build.sh` in the macro-benches repo, out of scope for a
comparison experiment). `devkit_gzip` (the suite's 4th program) doesn't
link against libpcre.so.1 at all and is unaffected.

**Class 2 -- stale build artifacts, 4 PRE-EXISTING switches only (11
cells, FIXED via `make gapfill`):** `frama_c_eva_t`, `frama_c_eva_sqlite`,
`jsoo`, `liq_video_frames_pool` (on `ocaml-5.5` and/or `ocaml-auto-compact`)
and `devkit_gzip` (on `ocaml-5.5-falign` and `ocaml-auto-compact-falign`)
all failed with "No such file or directory" pointing at a benchmark
wrapper script that referenced a binary dune never produced. Root cause:
these 4 switches (and their `_build-*` dirs) predate macro-benches fixes
applied over the following week -- the PCRE1 vendor build (~Sep 8), and
the jsoo/frama-c/infer/liq-video-frames benchmark additions themselves
(some as late as Sep 7). The wrapper script already existed from an
earlier, incomplete build attempt, so `benchmark.py`'s "already exists;
skipping build" check silently reused it instead of rebuilding -- and for
`devkit_gzip` specifically, a stale `duniverse/pcre-ocaml/lib/c_flags.sexp`
(2 bytes, `()`, dated Sep 1 -- i.e. discover.ml's own cached negative
result from *before* PCRE1 was vendored) meant dune never re-ran pcre
discovery even after the vendor fix landed, since neither the source nor
`PKG_CONFIG_PATH` are tracked dune inputs.

Telling confirmation: every one of the 11 gaps lands on one of the 4
switches that existed *before* this experiment (`ocaml-5.5`,
`ocaml-5.5-falign`, `ocaml-auto-compact`, `ocaml-auto-compact-falign`) --
never on the 4 fresh frame-pointer switches this experiment built today,
which have no stale state to inherit.

Fix applied (isolated to macro-benches working tree, not this repo):
deleted the 9 stale wrapper scripts (forces a real rebuild instead of a
skip) and the stale `duniverse/pcre-ocaml` dune-cache dir + `.build-failed`
sentinels for the 2 falign switches' devkit benchmarks. Wrote
`config-gapfill.yml` (standalone, 4 old runtimes x 6 programs, the exact
11 needed cells plus a handful of harmless redundant ones) and
`make gapfill` to rerun just the affected cells into `logs/gapfill/`; the
resulting `.log`/`olly_*.json` files use the identical naming scheme as
`make run`'s output, so once complete they get copied into the `make run`
run directory (`logs/full/lovelace-2026-09-09-Wed-174336/`) so
`plot_results.py` (which reads one run directory) sees the merged data
with no code changes.

## Phase 1 (cont.) -- `make gapfill` result + round 2

Round 1 (`lovelace-2026-09-09-Wed-203616`): 10/11 targeted cells fixed
cleanly (frama_c_eva_t/sqlite, jsoo, liq_video_frames_pool, infer_default
across ocaml-5.5/ocaml-auto-compact). `devkit_gzip` on the 2 falign
runtimes still failed -- same symptom, different cause: deleting only
`_build-*/default/duniverse/pcre-ocaml` had left dune's own incremental
digest database pointing at files that no longer existed on disk, so dune
threw a hard IO error (`open(.../c_library_flags.sexp): No such file or
directory`) instead of regenerating them. Fix: deleted the entire
`_build-ocaml-5.5-falign` / `_build-ocaml-auto-compact-falign` directories
(matching macro-benches' own `make clean` semantics) so dune starts from a
consistent state, re-cleared the sentinels, and reran with
`config-gapfill2.yml` / `make gapfill2` (run id
`lovelace-2026-09-09-Wed-205017`) -- both cells built and ran cleanly.

All successful gapfill cells copied (`.log` + `olly_*.json`) into the main
run directory `logs/full/lovelace-2026-09-09-Wed-174336/` (identical
naming scheme, so this is a plain file copy, no merge logic needed).

**Final completeness: 232/256 cells (90.6%).** Remaining 24 = exactly
`devkit_htmlstream` / `devkit_stre` / `devkit_network` x all 8 runtimes --
the Class 1 suite-wide `libpcre.so.1` runtime-linking bug described above,
which no rebuild fixes (it's missing `LD_LIBRARY_PATH` in the build
script, a macro-benches source change, out of scope here). Confirmed this
doesn't bias any comparison: every runtime is equally missing these 3
programs, so all ratios simply show "--" for them, exactly like the
build-failure convention already used in `../compactor-comparison/` and
`../compactor-comparison-falign/results.md`.

Proceeding to `make plot` and `make plot-groups`.

## Phase 2 -- plots + Makefile bug found and fixed

Hit a real bug in the first `make plot`/`plot-groups` pass: the Makefile
pointed `plot_results.py` at `logs/full` directly, but `runbms` writes into
a timestamped subdirectory under it (`logs/full/lovelace-.../`) -- so every
plot silently loaded "0 benchmarks" and rendered all-blank heatmaps/`--`
summary tables. Fixed by adding a `RUN_DIR := $(shell ls -td
$(HERE)/logs/full/*/ | head -1)` resolver to the Makefile and pointing all
`plot*` targets at it; reran `make plot plot-groups` and confirmed real
data (29 benchmarks x 8 runtimes, compaction count 26,806 matching TASK 1
exactly) -- see `results.md`.

## Phase 3 -- synthesis

Wrote `results.md`. Headline: auto-compaction's own cost is unchanged by
fp/falign (all four Tier-B group medians 1.000-1.002x, compaction counts
byte-identical across all four auto-compact variants) -- fp and falign are
orthogonal codegen options, not something that interacts with the patch.
fp alone costs a small, consistent ~1-2.5% (new measurement, not covered
by any prior task); falign alone reproduces the existing "wash for the
typical benchmark" finding from `../compactor-comparison-falign/`, with
one notable interaction found on `frama_c_eva_sqlite` (falign alone -43%,
fp+falign +18%) -- flagged, not chased further, as it's a per-benchmark
codegen/alignment effect independent of the auto-compact patch itself.

TASK 3 complete. Recap added to `../../../pplacer-workdir/PLAN.md`.

## Phase 4 -- absolute values alongside ratios

Follow-up ask: the ratio-only heatmaps and `summary_stats.txt` (aggregate
stats only) didn't expose per-benchmark absolute wall-time/RSS numbers
anywhere as a saved artifact -- `print_table()` printed them to stdout but
never wrote a file. Extended `plot_results.py`:
- `plot_ratio_heatmap` now takes `unit`/`value_fmt` and renders each cell
  as `+2.0% (10.2s)` (baseline column: `10.0s (ref)`), not just the
  percentage.
- New `write_metric_table_txt()` saves the equivalent per-benchmark table
  as plain text -- `wall_time_table.txt` and `max_rss_table.txt` in every
  `plots/*/` directory, alongside the existing (aggregate-only)
  `summary_stats.txt`.

Reran `make plot plot-groups` with the updated script; verified both the
new heatmap annotations and the new txt tables render correctly (spot
checked `plots/full/heatmap_wall_time_ratio.png` and
`plots/group-fp/heatmap_max_rss_ratio.png` visually). `results.md` and
`README.md` updated to describe the new files.

## Phase 5 -- eio_fiber_stream deep dive (follow-up)

User flagged `eio_fiber_stream`'s spread across the 8-way table as odd;
asked for a pinned/noise-reduced perf + flamegraph-diff + off-CPU
investigation. Spun this out into a sibling experiment,
`../eio-deep-dive/`, rather than cramming it into this folder (different
tooling -- perf record/stat, FlameGraph, no running-ng harness involved).
Finding: the swing is real (fp-driven, ±0.02% reproducible once pinned),
not noise -- see that folder's `results.md`/`worklog.md` for the full
investigation (including two environment bugs found and fixed along the
way: perf record crashing the benchmark via an `io_uring`/`RLIMIT_MEMLOCK`
collision, and the harness's unpinned/DVFS-exposed measurement being part
of the original spread). Added a summary + cross-reference to this file's
`results.md`.
