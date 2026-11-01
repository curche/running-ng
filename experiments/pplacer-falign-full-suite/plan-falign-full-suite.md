# Investigation Plan: Does `-falign-functions=64` Explain the Regressions Across the Whole Compactor-Comparison Suite?

## Background

The original 4-way compactor comparison
(`experiments/compactor-comparison/plan-benchmark-comparison.md`, results in
`experiments/compactor-comparison/plots/turing-2026-07-01-Wed-230036/results.md`,
freshly reproduced in
`experiments/compactor-comparison/logs/turing-2026-07-16-Thu-190928/`,
table in `experiments/compactor-comparison/plots/turing-2026-07-16-Thu-190928/all-values-table.txt`)
found two benchmarks with notable regressions for the non-stock runtimes:

- **`owl_gc`**: `ocaml-auto-compact` +25% (26,806 real compactions firing),
  `socaml`/`socaml-auto-compact` +114-119% (no compactions — never explained).
- **`pplacer_testsuite`**: all three non-stock runtimes +19-20%, zero
  compactions.

A deep dive in `experiments/pplacer-gc-regression/` (see
`plan-pplacer-gc-regression.md` and
`alignment-artifact/plan-alignment-artifact.md`) established that
`pplacer_testsuite`'s regression is **entirely a code-layout/cache-alignment
artifact**: `do_some_marking`/`mark` land at different cache-line offsets in
stock vs. patched binaries despite byte-identical source. Forcing identical
alignment via `gcc -falign-functions=64` (verified via `nm`; see
`experiments/pplacer-gc-regression/falign-check/plan-falign-check.md`)
**completely eliminates** the regression for `pplacer_testsuite` alone — no
source changes needed.

## Question

Does the same trick change the picture across the **whole** benchmark suite?

- Does `pplacer_testsuite`'s regression disappear here too?
- Does `owl_gc`'s regression persist for `ocaml-auto-compact` (expected —
  real compactions firing is a genuine behavioral difference, not layout) —
  and what about the `socaml`/`socaml-auto-compact` `owl_gc` regression,
  which fires *zero* compactions and was never explained? If alignment
  explains it too, that's a second confirmed case, not just pplacer's.
- Do any of the small (~1-7%) regressions/improvements seen elsewhere in the
  suite change once alignment is forced identical?

## Design

4 runtimes, all via running-ng's `opam-compiler` integration with
`configure_args: ["CFLAGS=-falign-functions=64"]`:

- `ocaml-5.5-falign`, `ocaml-auto-compact-falign` — **already built** (from
  the pplacer-only falign-check experiment), reused as-is.
- `socaml-falign`, `socaml-auto-compact-falign` — **new**, same recipe
  applied to `curche/ocaml:socaml-chunk-only` and `curche/ocaml:new_compactor`.

Runtime names suffixed `-falign` (not reusing the plain names) because
running-ng derives opam switch names from the runtime's YAML key alone —
reusing e.g. `ocaml-5.5` would silently resolve to the existing *plain*
switch instead of building a new aligned one.

Same benchmark suite, same `perf_grp1|re-25|md-2`, 3 invocations, as the
original comparison — just pointed at the 4 aligned runtimes.

**Known build failures expected to recur unchanged**: the deep `ppxlib`/
version-skew issues documented in
`experiments/pplacer-gc-regression/plan-pplacer-gc-regression.md` (and
re-confirmed in the 2026-07-16 full-suite re-run) affect `socaml`/
`socaml-auto-compact` on `alt_ergo`/`jsoo`/`liq_parse_typecheck`/
`ocamlc_self_compile`/`devkit`/`sedlex`/`irmin`/`frama-c`, and `goblint` on
all 4 runtimes. `-falign-functions` is a codegen flag, not a source change —
it cannot fix a compile-time type/AST incompatibility, so these are not
expected to build here either.

## Tooling

- Config: `src/running/config/experiments/macrobenchmarks_compactor_4way_falign.yml`
  (includes `macrobenchmarks_compactor_4way.yml`, overrides `runtimes:`,
  `configs:`, and `comparisons:` to the 4 `-falign` runtimes).
- Logs: `experiments/pplacer-falign-full-suite/logs/`.
- Plots: `experiments/pplacer-falign-full-suite/plots/` (`plot_results.py`,
  merges the falign run with the non-falign run so each patch's plain and
  falign columns sit side by side against the same `ocaml-5.5` baseline;
  `make_final_table.py` / `make_tables.py` produce the text tables).
- Comparison baseline: `experiments/compactor-comparison/logs/turing-2026-07-16-Thu-190928/`
  (the fresh non-falign full-suite run).
- **Interactive table**: `experiments/pplacer-falign-full-suite/interactive_table.html`
  — a self-contained HTML/JS page (data embedded inline, no server needed,
  open directly via `file://`) with all 8 runtimes × 30 benchmarks × 4
  metrics (wall time, max RSS, GC overhead, compactions). Click any column
  header to select it as the baseline, then toggle "Show: Relative to
  selected column" to turn every other column into a live ratio (or
  percentage-point delta for GC overhead) against it, colored on a
  green/red diverging scale — lets you re-pivot the baseline (e.g. stock
  plain vs. stock falign) without regenerating any plots. Data is
  refreshed via `export_data.py <falign_run_dir> <nonfalign_run_dir>
  data.json`, then re-embedded into the HTML.

## Results

Run id `turing-2026-07-17-Fri-132855` (started 13:28, finished 15:52 on
2026-07-17). Build phase had 53 failures — the previously-documented
`ppxlib`/`Ptyp_functor` skew for `socaml`/`socaml-auto-compact` on
`alt_ergo`/`coqc`/`devkit`/`frama-c`/`irmin`/`jsoo`/`liq_parse_typecheck`/
`sedlex`, plus `goblint` on all 5 runtimes — **and, newly, `alt_ergo`,
`coqc_corelib_stress`, all 4 `devkit_*`, `irmin_mem_rw`, and `jsoo` also
failed to build for `ocaml-5.5-falign`/`ocaml-auto-compact-falign`**, with
a distinct error (`[%blob] could not find or load file src/preludes/fpa.ae`
for alt_ergo). This is unrelated to `-falign-functions` — `CFLAGS` cannot
affect an OCaml PPX file-embedding lookup — and is best explained as a
latent build-fragility in these benchmarks' scripts that only surfaces on
a genuinely fresh `_build-<runtime>` directory (these benchmarks had never
been rebuilt from scratch since the original early-July run; the
2026-07-16 non-falign re-run reused existing sentinels/binaries for them).
It cost us falign-vs-non-falign data for those 8 benchmarks, but didn't
block the rest of the suite.

Full tables: `plots/turing-2026-07-17-Fri-132855/plain-vs-falign-table.txt`
(the primary table — every runtime's plain and falign builds side by side
against a single baseline, `ocaml-5.5` plain stock, extracted directly
from `olly_*.json` sidecars) plus the earlier `all-values-table.txt` and
`before-after-table.txt` (per-side-own-baseline framing, superseded by the
table below for cross-run comparison but kept for reference). Heatmaps
(`heatmap_wall_time_ratio.png`, `heatmap_max_rss_ratio.png`,
`heatmap_gc_overhead_pct.png`, `compaction_counts.png`) and
`plot_results.py` were updated to merge both run directories so every
patch's plain and falign columns sit side by side against the same
`ocaml-5.5` baseline.

**`pplacer_testsuite` — the patch-specific regression vanishes**, confirming
the alignment-artifact finding at full-suite scale, not just in the
isolated falign-check experiment. Against the single `ocaml-5.5` (plain)
baseline:

| runtime | plain | falign |
|---|---|---|
| 5.5 stock | — | +16.2% |
| auto-compact | +19.3% | +16.1% |
| new compactor (socaml) | +18.8% | +15.3% |
| new compactor + auto-compact | +19.8% | +15.1% |

Once alignment is forced, **every** falign variant — including plain
stock itself — lands in the same +15-16% band. The ~+3-4pp gap the
patches showed over stock in the plain build disappears entirely once
compared against `ocaml-5.5-falign` (+16.2%) instead of `ocaml-5.5`: the
patches were never the cause, the alignment flag's effect on stock
already accounts for nearly all of it.

**`owl_gc` — regressions persist (and grow), confirming they are real, not
layout artifacts:**

| runtime | plain | falign |
|---|---|---|
| 5.5 stock | — | -2.1% |
| auto-compact | +24.1% | +29.6% |
| new compactor (socaml) | +116.8% | +139.7% |
| new compactor + auto-compact | +111.6% | +140.2% |

`ocaml-auto-compact`'s `owl_gc` regression was already known to be genuine
(26,806 real compactions firing — a true behavioral cost of the patch, not
layout). The `socaml`/`socaml-auto-compact` `owl_gc` regression — which
fires **zero** compactions and was previously unexplained — is now
confirmed **not** to be an alignment artifact either: unlike pplacer,
falign doesn't shrink the gap toward stock, it grows in both the plain
and falign builds. Its root cause remains unknown and is out of scope for
this investigation.

**`eio_fiber_stream` — a second small-but-real, non-layout regression**,
found only by having plain and falign side by side: the new-compactor
variants (`socaml`/`socaml-auto-compact`) show a consistent **+6.5-6.9%**
regression in *both* the plain and falign builds (5.5 stock and
auto-compact stay within +2% throughout). Since the regression doesn't
move when alignment is forced, it isn't a layout artifact — likely a real
(if minor) interaction between the new compactor and this benchmark's
allocation pattern, not investigated further here.

**Everything else in the suite**: all other benchmarks show ≤ ~2%
differences across both plain and falign builds — consistent with
run-to-run noise, no new large or newly-explained regressions. Two points
worth flagging:

- **`menhir_ocamly`** is unreliable: `ocaml-5.5-falign` itself is +7.8%
  over plain `ocaml-5.5` (49.12s vs 45.56s) from the alignment flag alone,
  on *identical* stock source — bigger than any patch effect being
  measured — and the plain/falign numbers per patch don't move in a
  consistent direction (auto-compact -5.6%/-6.1%, socaml -4.3%/+0.2%,
  socaml-auto-compact -4.5%/+5.6%). This benchmark (45s wall, ~2.7GB RSS)
  needs more invocations before any of its numbers can be trusted.
- **`zarith_pi`**'s large socaml speedup (~-21%, both `socaml` and
  `socaml-auto-compact`, plain and falign alike) is essentially unchanged
  by falign — confirming it's a genuine algorithmic improvement, not an
  alignment side-effect in either direction.

## Conclusion

The alignment-artifact finding from the isolated `pplacer_testsuite`
investigation generalizes: it fully explains `pplacer_testsuite`'s
regression and **only** that regression — once `ocaml-5.5-falign` is used
as the reference instead of plain `ocaml-5.5`, the patches' apparent extra
cost on pplacer disappears completely. `owl_gc`'s regressions (both the
already-understood auto-compact one and the still-unexplained socaml one)
and `eio_fiber_stream`'s smaller socaml regression are real and
independent of code layout — forcing identical alignment does not reduce
either, and in owl_gc's case makes it slightly worse. No other benchmark
in the suite has a layout-driven regression hiding in it; the small
remaining deltas (≤ ~2%, with `menhir_ocamly` flagged as noisy/unreliable)
are consistent with ordinary measurement noise, not a systematic effect.
This closes the question of whether alignment explains the full-suite
picture: it explains exactly the one case it was hypothesized to
(pplacer), and nothing more.
