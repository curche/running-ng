# Setup

This experiment reuses infrastructure already present on this machine from
TASK 0-2 (see `../../../pplacer-workdir/PLAN.md`). Nothing below needs to be
redone if that infrastructure is already in place -- listed here so this
directory is a complete record of what reproduction requires.

## Prerequisites (already satisfied on this machine)

- **opam** (2.3+ preferred) with a working root at `~/.opam`.
- **`running-ng-tools`** opam switch (or any switch with `dune`+`ocamlfind`
  on PATH) -- created automatically by `run_ocaml_bench_gc_sweep.sh` if
  missing.
- **`runtime_events_tools`** (olly) checked out at `~/git/runtime_events_tools`
  (or set `OLLY_DIR`), built automatically by the run script if not already
  built. Must be at or past commit `977e33b6dea5e3bbcf13557a31513b11dfbfc4d5`
  (`max_rss_kb` in `olly gc-stats --json`).
- **`macro-benches`** checked out at `~/git/macro-benches` (or set
  `RUNNING_MACRO_BENCH_DIR`), with `duniverse/` pulled and `vendor/`
  populated (`make setup` in that directory -- see its own README).
- **`perf`** usable without root (`perf_event_paranoid <= 1`, ideally `-1`)
  for the `perf_grp1` modifier (`task-clock,page-faults,cycles,instructions`).
- Python 3 with `numpy` + `matplotlib` for `plot_results.py` (already used
  successfully by `../compactor-comparison-falign/plot_results.py`).
- Network access to `github.com/ocaml/ocaml` and `github.com/curche/ocaml`
  (opam-compiler pulls compiler sources from there).

## What's new for this experiment

The only new build work is 4 opam switches that don't exist yet:

- `running-ng-ocaml-5.5-fp`
- `running-ng-ocaml-5.5-fp-falign`
- `running-ng-ocaml-auto-compact-fp`
- `running-ng-ocaml-auto-compact-fp-falign`

These are **not** built manually -- `make smoke` (or `make run`) triggers
running-ng's lazy switch creation (`opam compiler create <src> --switch
<name> --configure-command "./configure --enable-frame-pointers [...]"`)
the first time each runtime is referenced. Expect the first `make smoke` to
take a while (compiling 4 OCaml compilers from source, ~10-20 min each
depending on machine).

Check current switches at any time:

```
opam switch list | grep running-ng-ocaml
```

The other 4 cells (`ocaml-5.5`, `ocaml-5.5-falign`, `ocaml-auto-compact`,
`ocaml-auto-compact-falign`) reuse the switches already built for
`../compactor-comparison/` and `../compactor-comparison-falign/` -- verified
present in `opam switch list` before this experiment was set up.

## Hardware this was calibrated on

28 cores, 30 GB RAM (per `../perf-slowdown-analysis/TASK2-PLAN.md`). The
`re-25|md-2` runtime-events ring size and per-benchmark iteration counts in
`macro_base.yml` are tuned for this machine; see that file's inline comments
("Iteration counts") if porting to different hardware.
