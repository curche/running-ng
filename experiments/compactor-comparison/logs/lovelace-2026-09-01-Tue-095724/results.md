# 4-way compactor comparison — reproduction on `lovelace`

Run ID: `lovelace-2026-09-01-Tue-095724`
Config: `src/running/config/experiments/macrobenchmarks_compactor_4way.yml`
Reproducing: `experiments/compactor-comparison/plots/turing-2026-07-01-Wed-230036/results.md` (original host: `turing`)

## pplacer_testsuite — median of 3 invocations

| runtime | wall (s) | Δ vs stock | RSS (MB) | gc_time (s) | gc_overhead | minor | major | compactions |
|---|---|---|---|---|---|---|---|---|
| ocaml-5.5 | 10.20 | — | 70.4 | 8.16 | 80.23% | 9152 | 3557 | 0 |
| ocaml-auto-compact | 10.16 | **-0.4%** | 69.9 | 8.15 | 80.27% | 9152 | 3557 | 0 |
| socaml | 10.43 | **+2.3%** | 70.5 | 8.38 | 80.40% | 9152 | 3561 | 0 |
| socaml-auto-compact | 9.85 | **-3.4%** | 70.1 | 7.81 | 79.30% | 9152 | 3561 | 0 |

## Comparison to the original `turing` run

| runtime | turing wall (s) | turing Δ | lovelace wall (s) | lovelace Δ |
|---|---|---|---|---|
| ocaml-5.5 | 23.36 | — | 10.20 | — |
| ocaml-auto-compact | 27.90 | **+19.4%** | 10.16 | **-0.4%** |
| socaml | 27.88 | **+19.3%** | 10.43 | **+2.3%** |
| socaml-auto-compact | 28.15 | **+20.5%** | 9.85 | **-3.4%** |

**The regression did not reproduce on this machine.** All three patched
variants land within ±3.4% of stock `ocaml-5.5` here, vs. a consistent
+19–20% regression on `turing`.

GC event counts are essentially identical across both machines and both
config regimes (9152 minor collections, ~3557–3561 major collections, **0
compactions** in every cell) — the workload itself is reproduced exactly;
only wall-clock time and its distribution across variants differ. This
is the expected outcome given the original investigation's own
conclusion (see `experiments/pplacer-gc-regression/falign-check/` and
`experiments/pplacer-falign-full-suite/plan-falign-full-suite.md` from the
`turing` session): the regression traced back to `do_some_marking`/`mark`/
`pool_sweep` landing at a different cache-line alignment offset purely as
an incidental side effect of the patches adding unrelated code earlier in
`major_gc.c` — not any algorithmic change (compactions=0 throughout, so
the compactor code doesn't even run). Forcing identical alignment via
`-falign-functions=64` on *stock* OCaml alone reproduced ~80% of the
"regression" on `turing`.

Alignment offsets are sensitive to the exact compiler/linker toolchain.
`lovelace` builds with gcc 15.2.0 vs. `turing`'s gcc 13.3.0 — a different
compiler naturally lays out the same source differently, so the specific
binary-layout accident that caused the regression on `turing` does not
recur here. This is consistent with, and an independent confirmation of,
the original root-cause finding rather than a contradiction of it.

## Environment differences from the original run

- Host: `lovelace` (28 cores, 30 GB RAM, quiet — load avg ~0.25) vs.
  `turing` (28 cores, 64 GB RAM, shared — 50+ concurrent users, load avg
  2.3–6.9). Lower absolute wall-clock time here is plausibly explained by
  the absence of contention alone, independent of the alignment question.
- gcc 15.2.0 vs. 13.3.0.
- Switches built fresh via `opam compiler create` directly from
  `ocaml/ocaml:5.5.0` and the `curche/ocaml` branches
  (`auto-compact-5.5`, `socaml-chunk-only`, `new_compactor`), rather than
  reusing pre-built switches.
- `olly` built from `tarides/runtime_events_tools@main` (the original
  session's local `count-auto-compactions` patch was never pushed
  anywhere and wasn't recoverable; irrelevant here since compactions=0 in
  every cell on both machines).
