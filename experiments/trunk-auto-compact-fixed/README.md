# trunk-auto-compact-fixed

Fixed re-run of `../trunk-auto-compact-comparison/`: 12/29 benchmarks
failed to build on both trunk runtimes there (a ppxlib/`ast_506.ml` gap --
see `worklog.md`); fixed, and the full 5-runtime x full-suite sweep
re-run with full coverage (29/29, except `ocaml-auto-compact-trunk` at
28/29 -- see `worklog.md` for the one remaining, narrow gap).

Same 5 runtimes as before, per instruction ("the current set of 5 variants
should be enough"): `ocaml-5.5`, `ocaml-auto-compact`, `ocaml-5.5.1`,
`ocaml-trunk`, `ocaml-auto-compact-trunk`.

## Reproducing

```
make run    # full 5-runtime x full-suite x 3-invocation sweep
make plot   # 5-way heatmaps + tables from the `run` log directory
```

or `make all` for both in sequence.

## Files

- `config.yml` -- the running-ng experiment config (5 runtimes, full suite,
  same comparisons as `../trunk-auto-compact-comparison/config.yml`).
- `Makefile` -- reproduction commands.
- `plot_results.py` -- heatmap/table/summary-stats generator, copied
  unmodified from `../fp-falign-autocompact/plot_results.py` (generic over
  an arbitrary comma-separated runtime list; cells show both ratio and
  absolute value, baseline column shown as `<value> (ref)`).
- `logs/full/` -- raw running-ng output from `make run`.
- `plots/full/` -- heatmaps + `wall_time_table.txt` / `max_rss_table.txt` /
  `summary_stats.txt` from `make plot`.
- `worklog.md` -- what was actually done/observed fixing the build gap.
- `results.md` -- final write-up with the four heatmaps embedded.
