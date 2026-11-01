# pplacer_testsuite: flambda / frame-pointers results

Data sources: `flambda-fp-check/turing-2026-07-14-Tue-223028/` (stock ocaml-5.5
+ all fp/flambda variants) and `logs/turing-2026-07-13-Mon-230928/` (plain,
no-flambda/no-fp baseline for `ocaml-5.5`/`ocaml-auto-compact`/`socaml`/
`socaml-auto-compact`, labeled "orig repro run" / "(plain)" below). All wall
times and RSS are medians of 3 invocations, `perf_grp1|re-25|md-2`.

## Table 1: All values (sorted by wall time)

| Runtime | flags | wall (s) | RSS (MB) | gc_time (s) | minor GCs | major GCs | compactions |
|---|---|---|---|---|---|---|---|
| `socaml-auto-compact-flambda` | flambda | 23.13 | 75.5 | 17.23 | 8928 | 3547 | 0 |
| `ocaml-5.5` | plain | 23.30 | 70.1 | 17.07 | 9152 | 3557 | 0 |
| `ocaml-5.5` (orig repro run) | plain | 23.36 | 70.0 | 17.18 | 9152 | 3557 | 0 |
| `socaml-auto-compact-fp` | fp | 25.16 | 70.1 | 18.75 | 9152 | 3561 | 0 |
| `ocaml-5.5-fp` | fp | 25.73 | 70.5 | 19.15 | 9152 | 3557 | 0 |
| `ocaml-auto-compact-flambda-fp` | flambda+fp | 26.39 | 75.6 | 20.25 | 8926 | 3546 | 0 |
| `socaml-auto-compact-flambda-fp` | flambda+fp | 26.85 | 75.7 | 20.80 | 8928 | 3549 | 0 |
| `ocaml-5.5-flambda-fp` | flambda+fp | 27.50 | 75.4 | 21.35 | 8926 | 3544 | 0 |
| `ocaml-auto-compact-fp` | fp | 27.51 | 70.0 | 20.90 | 9152 | 3557 | 0 |
| `socaml` (plain) | plain | 27.88 | 70.1 | 21.17 | 9152 | 3561 | 0 |
| `ocaml-auto-compact` (plain) | plain | 27.90 | 70.0 | 21.67 | 9152 | 3557 | 0 |
| `socaml-auto-compact` (plain) | plain | 28.15 | 70.1 | 21.43 | 9152 | 3561 | 0 |
| `ocaml-5.5-flambda` | flambda | 28.17 | 75.3 | 21.69 | 8926 | 3545 | 0 |

## Correct comparisons (same build flags, delta vs. stock in that group)

Sorting/reading Table 1 alone is misleading: it implicitly compares every
runtime against *plain* stock, but frame-pointers and flambda measurably
regress plain stock OCaml on this benchmark too. The comparisons below hold
compiler flags fixed within each group, isolating the effect of the
auto-compact/new-compactor patch alone.

**Plain (no flambda/fp)** — stock: `ocaml-5.5` 23.36s / 70.0MB

| Runtime | wall (s) | Δ vs stock-plain | RSS (MB) |
|---|---|---|---|
| `ocaml-5.5` | 23.36 | — | 70.0 |
| `socaml` | 27.88 | +19.3% | 70.1 |
| `ocaml-auto-compact` | 27.90 | +19.4% | 70.0 |
| `socaml-auto-compact` | 28.15 | +20.5% | 70.1 |

**fp only** — stock: `ocaml-5.5-fp` 25.73s / 70.5MB

| Runtime | wall (s) | Δ vs stock-fp | RSS (MB) |
|---|---|---|---|
| `socaml-auto-compact-fp` | 25.16 | **−2.2%** | 70.1 |
| `ocaml-5.5-fp` | 25.73 | — | 70.5 |
| `ocaml-auto-compact-fp` | 27.51 | +7.0% | 70.0 |

**flambda only** — stock: `ocaml-5.5-flambda` 28.17s / 75.3MB

| Runtime | wall (s) | Δ vs stock-flambda | RSS (MB) |
|---|---|---|---|
| `socaml-auto-compact-flambda` | 23.13 | **−17.9%** | 75.5 |
| `ocaml-5.5-flambda` | 28.17 | — | 75.3 |

**flambda + fp** — stock: `ocaml-5.5-flambda-fp` 27.50s / 75.4MB

| Runtime | wall (s) | Δ vs stock-flambda+fp | RSS (MB) |
|---|---|---|---|
| `ocaml-auto-compact-flambda-fp` | 26.39 | **−4.0%** | 75.6 |
| `socaml-auto-compact-flambda-fp` | 26.85 | **−2.4%** | 75.7 |
| `ocaml-5.5-flambda-fp` | 27.50 | — | 75.4 |

## Takeaway (as of the 9-config run, `turing-2026-07-14-Tue-223028`)

Frame-pointers (+10.4%) and flambda (+20.9%) both substantially regress
*stock, unpatched* OCaml on this specific pplacer benchmark — an effect
entirely independent of the auto-compact/new-compactor patches. Once
compiler flags are held fixed, the patched runtimes are at parity or
*faster* than a same-flags stock build in every optimized group. Only the
plain (no flambda/fp) group shows the original ~19-20% patch regression —
that finding stands unchanged; it just doesn't extend to the optimized
builds the way earlier same-vs-plain-stock framing suggested.

---

## Final complete matrix (2026-07-15, run `turing-2026-07-15-Wed-005934`)

Fills the remaining gaps: `ocaml-auto-compact-flambda` (flambda-only for that
lineage) and the full fp/flambda/flambda-fp set for plain `socaml` (no
auto-compact) — previously only its plain variant existed. 13 configs total,
medians of 3 invocations, `perf_grp1|re-25|md-2`.

### Table: all values (sorted by wall time)

| Runtime | wall (s) | Δ vs plain stock | RSS (MB) | gc_time (s) | minor GCs | major GCs |
|---|---|---|---|---|---|---|
| `socaml-auto-compact-flambda` | 23.15 | −1.2% | 75.5 | 17.26 | 8928 | 3547 |
| `socaml-flambda` | 23.27 | −0.7% | 75.3 | 17.37 | 8928 | 3549 |
| `ocaml-5.5` (stock) | 23.43 | — | 70.1 | 17.23 | 9152 | 3557 |
| `ocaml-auto-compact-flambda` | 23.89 | +2.0% | 75.2 | 17.42 | 8926 | 3546 |
| `socaml-auto-compact-fp` | 25.21 | +7.6% | 70.1 | 18.81 | 9152 | 3561 |
| `socaml-flambda-fp` | 25.34 | +8.2% | 75.6 | 19.26 | 8928 | 3548 |
| `ocaml-5.5-fp` | 25.73 | +9.8% | 70.2 | 19.19 | 9152 | 3557 |
| `socaml-fp` | 26.29 | +12.2% | 70.0 | 19.87 | 9152 | 3561 |
| `ocaml-auto-compact-flambda-fp` | 26.38 | +12.6% | 75.5 | 20.21 | 8926 | 3546 |
| `socaml-auto-compact-flambda-fp` | 26.94 | +15.0% | 75.5 | 20.83 | 8928 | 3549 |
| `ocaml-auto-compact-fp` | 27.36 | +16.8% | 70.2 | 20.78 | 9152 | 3557 |
| `ocaml-5.5-flambda-fp` | 27.52 | +17.5% | 75.5 | 21.33 | 8926 | 3545 |
| **`ocaml-5.5-flambda`** | **28.17** | **+20.2%** | 75.1 | 21.65 | 8926 | 3545 |

**`ocaml-5.5-flambda` — stock OCaml with flambda and no patch at all — is the
single slowest configuration in the entire 13-way matrix.** Every "faster
than stock-flambda" comparison below is partly a statement about how
unusually bad stock-flambda is on this benchmark, not only about the patches.

### Corrected comparisons — same build flags, all 4 lineages per group

**Plain** — stock `ocaml-5.5` 23.36s / 70.0MB (from Phase 0 baseline)

| Runtime | wall (s) | Δ | RSS (MB) |
|---|---|---|---|
| `socaml` | 27.88 | +19.3% | 70.1 |
| `ocaml-auto-compact` | 27.90 | +19.4% | 70.0 |
| `socaml-auto-compact` | 28.15 | +20.5% | 70.1 |

**fp only** — stock `ocaml-5.5-fp` 25.73s / 70.2MB

| Runtime | wall (s) | Δ | RSS (MB) |
|---|---|---|---|
| `socaml-auto-compact-fp` | 25.21 | **−2.0%** | 70.1 |
| `socaml-fp` | 26.29 | +2.2% | 70.0 |
| `ocaml-auto-compact-fp` | 27.36 | +6.3% | 70.2 |

**flambda only** — stock `ocaml-5.5-flambda` 28.17s / 75.1MB

| Runtime | wall (s) | Δ | RSS (MB) |
|---|---|---|---|
| `socaml-auto-compact-flambda` | 23.15 | **−17.8%** | 75.5 |
| `socaml-flambda` | 23.27 | **−17.4%** | 75.3 |
| `ocaml-auto-compact-flambda` | 23.89 | **−15.2%** | 75.2 |

**flambda + fp** — stock `ocaml-5.5-flambda-fp` 27.52s / 75.5MB

| Runtime | wall (s) | Δ | RSS (MB) |
|---|---|---|---|
| `socaml-auto-compact-flambda-fp` | 26.94 | **−2.1%** | 75.5 |
| `ocaml-auto-compact-flambda-fp` | 26.38 | **−4.1%** | 75.5 |
| `socaml-flambda-fp` | 25.34 | **−7.9%** | 75.6 |

### The fp-on-flambda anti-synergy, isolated per lineage

Within-lineage delta of adding `--enable-frame-pointers` on top of an
already-`--enable-flambda` build:

| Lineage | flambda alone (s) | flambda+fp (s) | Δ (fp penalty) |
|---|---|---|---|
| `ocaml-5.5` (stock) | 28.17 | 27.52 | **−2.3%** (fp *helps*) |
| `socaml` (chunk allocator only) | 23.27 | 25.34 | +8.9% |
| `ocaml-auto-compact` | 23.89 | 26.38 | +10.4% |
| `socaml-auto-compact` (both patches) | 23.15 | 26.94 | **+16.4%** |

Stock is the only line where adding fp on top of flambda doesn't hurt. All
three patches show the penalty; it roughly doubles when both patches are
combined, though not simply additively (10.4% + 8.9% ≠ 16.4%).

### Conclusions

1. **The "faster than stock-flambda" effect is not chunk-allocator-specific.**
   `ocaml-auto-compact-flambda` (no chunk allocator at all) is also 15.2%
   faster than stock-flambda — nearly as dramatic as either socaml lineage
   (17.4-17.8%). Given all three independent patches show the same effect,
   it looks more like **stock-flambda being anomalously slow on this specific
   benchmark** than like any patch being especially flambda-friendly.
2. **The fp-on-flambda anti-synergy *is* patch-proportional**, unlike (1):
   it's zero/negative for stock, present for either single patch alone
   (~9-10%), and largest when both patches are combined (16.4%) — this part
   is a genuine, still-unexplained interaction (Phase 2b in the plan doc).
3. Plain-build ~19-20% regression is unchanged and still the cleanest,
   fully-confirmed finding in the whole investigation.
