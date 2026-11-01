# Investigation Plan: Re-run the Full Compactor Comparison with `-falign-functions=64`

## Background

The original 4-way compactor comparison
(`experiments/compactor-comparison/plan-benchmark-comparison.md`, results in
`plots/turing-2026-07-01-Wed-230036/results.md`, freshly reproduced in
`logs/turing-2026-07-16-Thu-190928/`) found two benchmarks with notable
regressions for the non-stock runtimes:

- **`owl_gc`**: `ocaml-auto-compact` +25% (26,806 real compactions firing),
  `socaml`/`socaml-auto-compact` +114-119% (no compactions — a genuine
  chunk-allocator overhead, not yet explained).
- **`pplacer_testsuite`**: all three non-stock runtimes +19-20%, zero
  compactions.

A deep dive in `experiments/pplacer-gc-regression/` established that
`pplacer_testsuite`'s regression is **entirely a code-layout/cache-alignment
artifact**: `do_some_marking`/`mark` land at different cache-line offsets in
stock vs. patched binaries despite byte-identical source, and forcing
identical alignment via `gcc -falign-functions=64` (see
`experiments/pplacer-gc-regression/falign-check/`) **completely eliminates**
the regression — no source changes needed.

## Question

Does the same trick change the picture across the **whole** benchmark suite,
not just `pplacer_testsuite`? Specifically:
- Does `pplacer_testsuite`'s regression disappear here too (expected — same
  mechanism, same binaries in principle, though this run uses fresh
  `-falign` switches rather than the exact ones from the pplacer-only
  investigation).
- Does `owl_gc`'s regression persist for `ocaml-auto-compact` (expected —
  real compactions firing is a genuine behavioral difference, not a layout
  coincidence) and for `socaml`/`socaml-auto-compact` (unknown — this one
  was never explained, worth checking if it's *also* alignment-driven).
- Do any of the small (~1-7%) regressions/improvements seen elsewhere in the
  suite (e.g. `eio_fiber_stream` +6-7% for socaml variants) change once
  alignment is forced?

## Design

New switches, all via running-ng's `opam-compiler` integration with
`configure_args: ["CFLAGS=-falign-functions=64"]` (confirmed working — see
`experiments/pplacer-gc-regression/falign-check/plan-falign-check.md` for
how this flag was discovered and verified via `nm`):

- `ocaml-5.5-falign`, `ocaml-auto-compact-falign` — **already built** from
  the pplacer-only falign-check experiment, reused here.
- `socaml-falign`, `socaml-auto-compact-falign` — **new**, same recipe
  applied to `curche/ocaml:socaml-chunk-only` and `curche/ocaml:new_compactor`.

Runtime names are suffixed `-falign` (not reusing the plain names) because
running-ng derives opam switch names from the runtime's YAML key alone —
reusing e.g. `ocaml-5.5` would silently resolve to the existing *plain*
switch instead of building a new aligned one.

Config: `src/running/config/experiments/macrobenchmarks_compactor_4way_falign.yml`
— same benchmark suite, same `perf_grp1|re-25|md-2`, 3 invocations, as the
original comparison, just pointed at the 4 aligned runtimes.

Known build failures (deep `ppxlib`/version-skew issues documented in
`experiments/pplacer-gc-regression/plan-pplacer-gc-regression.md` and
re-confirmed in the 2026-07-16 full-suite re-run) will very likely recur
identically for `socaml-falign`/`socaml-auto-compact-falign` on
`alt_ergo`/`jsoo`/`liq_parse_typecheck`/`ocamlc_self_compile`/`devkit`/
`sedlex`/`irmin`/`frama-c` — the `-falign-functions` flag doesn't touch
source compatibility, so this isn't expected to fix anything there. `goblint`
similarly not expected to build for any of the 4.

## Tooling

- Config: `src/running/config/experiments/macrobenchmarks_compactor_4way_falign.yml`.
- `Makefile` in this folder (`make validate` / `make run` / `make summarize` / `make clean`).
- Logs: `experiments/compactor-comparison/falign-check/logs/`.
- Plots: `experiments/compactor-comparison/falign-check/plots/` (adapted
  `plot_results.py` for the `-falign` runtime names).

## Results

_(filled in once the run completes)_

## Conclusion

_(filled in once the run completes)_
