# fp-falign-autocompact -- TASK 3

2x2x2 factorial comparison against stock `ocaml-5.5`, for the auto-compaction
patch specifically (not the socaml chunk allocator, which was already
investigated separately in TASK 1/2 -- see `../../../pplacer-workdir/PLAN.md`
and `../../../pplacer-workdir/TASK2-PLAN.md`).

Three independent binary knobs, all crossed:

- **auto-compaction**: off (stock) / on (`curche/ocaml:auto-compact-5.5`)
- **falign**: off / on (`CFLAGS=-falign-functions=64`)
- **frame pointers**: off / on (`--enable-frame-pointers`)

## The 8 cells

| | no falign | falign |
|---|---|---|
| **no fp, no auto-compact** | `ocaml-5.5` -- reference | `ocaml-5.5-falign` |
| **fp, no auto-compact** | `ocaml-5.5-fp` | `ocaml-5.5-fp-falign` |
| **no fp, auto-compact** | `ocaml-auto-compact` | `ocaml-auto-compact-falign` |
| **fp, auto-compact** | `ocaml-auto-compact-fp` | `ocaml-auto-compact-fp-falign` |

4 of the 8 opam switches already existed before this experiment (built for
`../compactor-comparison/` and `../compactor-comparison-falign/`): `ocaml-5.5`,
`ocaml-5.5-falign`, `ocaml-auto-compact`, `ocaml-auto-compact-falign`. The 4
frame-pointer cells are new and get built automatically the first time
`config.yml` runs (running-ng's `type: OCaml` runtime creates the opam switch
lazily via `opam compiler create ... --configure-command`; switch names are
`running-ng-<runtime-name>`, matching the existing ones exactly so nothing is
rebuilt unnecessarily).

## Comparisons

**Tier A** -- every one of the 7 non-reference cells vs. stock `ocaml-5.5`.

**Tier B** -- four *within-group* comparisons that isolate the
auto-compaction effect while holding falign/fp fixed, so we can tell whether
fp and/or falign change how much auto-compaction costs, rather than only
ever comparing back to plain stock:

| group | a | b |
|---|---|---|
| baseline | `ocaml-5.5` | `ocaml-auto-compact` |
| fp | `ocaml-5.5-fp` | `ocaml-auto-compact-fp` |
| falign | `ocaml-5.5-falign` | `ocaml-auto-compact-falign` |
| fp+falign | `ocaml-5.5-fp-falign` | `ocaml-auto-compact-fp-falign` |

## Reproducing

See `SETUP.md` for prerequisites. Then, from this directory:

```
make smoke        # fast sanity check + builds the 4 new switches
make run          # full 8-way sweep (hours)
make plot          # full 8-runtime heatmaps
make plot-groups   # per-Tier-B-group heatmaps
```

or `make all` to run everything in sequence.

## Files

- `config.yml` -- the running-ng experiment config (8 runtimes, full suite,
  Tier A + Tier B comparisons).
- `config-smoke.yml` -- reduced config (4 benchmarks, 1 invocation) that
  includes `config.yml`, used by `make smoke`.
- `Makefile` -- reproduction commands (see above).
- `plot_results.py` -- heatmap/summary-stats generator (copied from
  `../compactor-comparison-falign/plot_results.py`, unmodified -- already
  generic over an arbitrary comma-separated runtime list).
- `logs/` -- raw running-ng output (`smoke/`, `full/`) and `.log` files from
  each `make` target, populated by running the Makefile.
- `plots/` -- one subdirectory per `make plot*` target, each containing:
  - `heatmap_wall_time_ratio.png` / `heatmap_max_rss_ratio.png` -- cells show
    both the ratio and the absolute value, e.g. `+2.0% (10.2s)`, with the
    baseline column shown as plain `10.0s (ref)`.
  - `heatmap_gc_overhead_pct.png` / `heatmap_compactions.png` -- raw values.
  - `wall_time_table.txt` / `max_rss_table.txt` -- the same per-benchmark
    absolute-value + ratio numbers as the heatmaps, as plain text.
  - `summary_stats.txt` -- cross-benchmark *aggregate* ratio stats
    (avg/median/range), not per-benchmark.
- `worklog.md` -- running, append-only log of what was actually done/observed
  (TASK 1/2 convention).
- `results.md` -- final write-up (filled in once the full run completes).
