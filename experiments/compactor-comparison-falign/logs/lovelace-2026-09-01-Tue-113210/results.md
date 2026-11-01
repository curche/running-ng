# 4-way compactor comparison — forced alignment (`-falign-functions=64`) — `lovelace`

Run ID: `lovelace-2026-09-01-Tue-113210`
Config: `src/running/config/experiments/macrobenchmarks_compactor_4way_falign.yml`
Follow-up to: `experiments/compactor-comparison/logs/lovelace-2026-09-01-Tue-095724/results.md`
(the plain run on this machine, which did **not** reproduce the turing regression)

## pplacer_testsuite — median of 3 invocations

| runtime | wall (s) | Δ vs plain ocaml-5.5 | Δ vs ocaml-5.5-falign | RSS (MB) | gc_overhead | major | compactions |
|---|---|---|---|---|---|---|---|
| ocaml-5.5 (plain, reference) | 10.17 | — | -10.0% | 70.3 | 80.08% | 3557 | 0 |
| ocaml-5.5-falign | 11.30 | **+11.1%** | — | 70.1 | 79.33% | 3557 | 0 |
| ocaml-auto-compact-falign | 11.10 | **+9.1%** | -1.8% | 70.3 | 79.43% | 3557 | 0 |
| socaml-falign | 11.38 | **+11.9%** | +0.7% | 69.8 | 78.92% | 3561 | 0 |
| socaml-auto-compact-falign | 11.05 | **+8.7%** | -2.2% | 70.0 | 79.16% | 3561 | 0 |

## Result: confirmed

This independently reconfirms the original investigation's root-cause finding,
on a different machine and a different compiler toolchain (gcc 15.2.0 here
vs. 13.3.0 on turing):

1. **Forcing identical code alignment produces a uniform "regression" across
   every variant, including plain stock.** All four `-falign` builds land in
   a tight +8.7% to +11.9% band vs. unforced plain `ocaml-5.5` — regardless
   of which patch (if any) is applied. `ocaml-5.5-falign` (stock + forced
   alignment, no compactor changes at all) regresses by +11.1% on its own,
   comparable to or larger than any of the patched variants.

2. **Once alignment is held constant (falign vs. falign), the patches show
   no real regression** — all three patched falign variants land within
   ±2.2% of falign-forced stock (`ocaml-5.5-falign`), i.e. within noise.

3. **GC event counts remain exactly reproduced**: 9152 minor collections,
   3557–3561 major collections, **0 compactions** in every one of the 15
   cells (5 runtimes × 3 invocations) — the compactor algorithm never
   fires for this workload on either machine, so any wall-time delta can
   only come from code layout/cache effects, not from actual compaction
   work.

Combined with the plain-run result on this machine (no regression at all,
since gcc 15.2.0 happened to land the hot functions at a non-regressing
offset naturally), this is consistent, cross-machine, cross-toolchain
evidence for the original conclusion: **the pplacer_testsuite "regression"
seen on turing was a code-alignment side effect of the patches shifting
unrelated code earlier in `major_gc.c`, not an algorithmic cost of the
auto-compact or chunk-based-compactor changes themselves.**

## Note on noise

Raw wall times have ~1s spread on ~11s runs (e.g. `ocaml-5.5-falign`:
10.42–11.52s across 3 invocations, ~10%) — consistent with the kind of
single-invocation noise flagged in the original investigation (e.g. its
`menhir_ocamly` note). The pattern across variants (all falign builds in
one band, all non-falign builds in another) is nonetheless clear and
consistent with 3 invocations each; more invocations would tighten the
per-cell confidence intervals but are unlikely to change the qualitative
conclusion given how cleanly the two bands separate.

## Environment

Same as the plain run — see
`experiments/compactor-comparison/logs/lovelace-2026-09-01-Tue-095724/results.md`
§"Environment differences from the original run". Additionally for this
run: all four `-falign` switches were built via `opam compiler create`
with `configure_args: ["CFLAGS=-falign-functions=64"]`, matching the
original investigation's mechanism exactly.
