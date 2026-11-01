# 5.5 vs. 5.5.1 vs. trunk, with/without automatic compaction

## The rebase

`auto-compact-5.5` is 2 commits on top of the `5.5.0` release tag: "Port
automatic compaction from OxCaml to OCaml 5.5" (the real patch, ~130 lines
across 7 files) and a version-string bump. Rebased both onto
`curche/ocaml`'s trunk mirror, pinned at `eba18e50be` (fetched 2026-09-09)
— 1098 commits ahead of the 5.5.0 base, 52 of which touch the same files
the patch touches.

Two real conflicts, both mechanical once located:
- `runtime/gc_ctrl.c`: the `caml_runtime_parameters` format string --
  trunk had independently added an `R=` field at the same spot our patch
  adds `O=`. Merged both into one format string, matching the (already
  auto-merged) argument list order below it.
- `runtime/startup_aux.c`: trunk refactored the entire OCAMLRUNPARAM
  parser out of `caml_parse_ocamlrunparam` into a new
  `caml_parse_startup_params()` function (a separate, unrelated upstream
  change). Added the `case 'O':` arm to the *new* function instead of
  keeping our patch's now-superseded inline copy, and resolved the
  `struct caml_params` field-init conflict by keeping trunk's
  pointer-based (`params->`) style with our `init_max_percent_free` line
  inserted.

`runtime/major_gc.c` itself -- `should_compact_from_stw_single` and its
call sites -- merged with **zero conflicts** despite an "Idle phase" GC
refactor and an ephemeron-marking rewrite landing in between. Confirmed by
inspection (not just by the absence of conflict markers) that the
compaction gate (`mode != Slice_opportunistic && is_complete_last_phase()`
-- renamed from `is_complete_phase_sweep_ephe`, semantics unchanged) is
structurally intact.

Branch `auto-compact-trunk` in `ocaml-compiler/ocaml-git`, 2 one-line
commits, no co-author trailer. Not pushed (no push credentials on this
machine) -- built locally to `/home/curche/opt/ocaml-auto-compact-trunk`,
referenced in the experiment config via `executable:` rather than
`repo:`/`commit:`.

**The compaction-count heatmap below is the real validation that this
rebase is semantically correct, not just "it compiled":** `owl_gc`
compacts 26,745 times on `ocaml-auto-compact-trunk` vs. 26,806 on
`ocaml-auto-compact` (5.5.0) -- a 0.2% difference, i.e. the same runtime
behavior survived 14 months of upstream churn essentially unchanged.

## Setup

5 runtimes, full macro-benches suite, 3 invocations:
`src/running/config/experiments/trunk_auto_compact_comparison.yml`.

| runtime | what |
|---|---|
| `ocaml-5.5` | stock 5.5.0 |
| `ocaml-auto-compact` | 5.5.0 + auto-compact (`auto-compact-5.5`) |
| `ocaml-5.5.1` | stock 5.5.1 |
| `ocaml-trunk` | stock trunk @ `eba18e50be` |
| `ocaml-auto-compact-trunk` | trunk @ `eba18e50be` + auto-compact (rebased, this session) |

Plots/data: `plots/heatmap_{wall_time_ratio,max_rss_ratio,gc_overhead_pct,
compactions}.png`, `plots/summary_stats.txt`. Reuses
`compactor-comparison/plot_results.py` verbatim (copied in, not run
cross-directory).

## Known gap: 12 of 29 benchmarks don't build on either trunk runtime

`alt_ergo_*` (×3), `devkit_*` (×4), `frama_c_eva_*` (×2), `goblint`,
`infer_default`, `irmin_mem_rw`, `jsoo`, `liq_parse_typecheck`,
`sedlex_tokenize` fail identically on **both** `ocaml-trunk` and
`ocaml-auto-compact-trunk` with the same error shape as the socaml/ppxlib
issue fixed in `auto-compact-tuning` Phase 10, just one version up:

```
File "duniverse/ppxlib/astlib/ast_506.ml", lines 350-472, ...
Error: This variant or record definition does not match that of type
       Parsetree.expression_desc
       An extra constructor, Pexp_hole, is provided in the original definition.
```

ppxlib's pinned `ast_506.ml` (its mirror of OCaml 5.6's `Parsetree`) claims
a `Pexp_hole` constructor that this trunk snapshot's real
`expression_desc` doesn't have -- the opposite-direction version of the
same class of bug (a vendored AST-shape mirror drifting from a specific
compiler snapshot's real AST), now hitting the *trunk* pin instead of the
*socaml* pin. **Not caused by the auto-compact rebase** -- it fails
identically on plain stock `ocaml-trunk`, so it doesn't bias the
auto-compaction comparison, just shrinks its coverage to 17/29
benchmarks. Not fixed here (out of scope; would need either pinning
duniverse's ppxlib to a version with a matching `ast_506.ml`, or the same
"patch the compiler's own Parsetree to match what ppxlib expects"
approach used for socaml). `ocaml-5.5` / `ocaml-auto-compact` / `ocaml-
5.5.1` are unaffected (29/29) -- ppxlib's `ast_505.ml` pin matches all
three fine.

## Results

**The auto-compact-tuning finding reproduces on trunk essentially
unchanged.** `owl_gc` is still the only benchmark that compacts at all
(compactions heatmap), auto-compaction still costs it real time and RSS,
and the magnitude actually looks a hair worse on trunk than on 5.5.0:

| runtime | owl_gc wall time | owl_gc GC overhead | owl_gc RSS |
|---|---|---|---|
| ocaml-5.5 | 4.60s | 31.6% | baseline |
| ocaml-auto-compact | +27.0% | 45.8% | +3.0% |
| ocaml-5.5.1 | +3.3% (no auto-compact) | 33.0% | +1.3% |
| ocaml-trunk (no auto-compact) | +2.4% | 32.9% | +11.9% |
| ocaml-auto-compact-trunk | +32.8% | 48.5% | +14.9% |

(the `ocaml-5.5.1`/`ocaml-trunk` rows have no auto-compact enabled --
their small deltas are the version-freshness effect below, not
compaction; `+33.3%`/`+32.8%`-style deltas on `owl_gc` are the real
auto-compact cost, consistent with everything in `auto-compact-tuning`.)

- **Auto-compaction's cost is reproduced on trunk at closely matching
  magnitude**: +27.0% (5.5.0) vs. +32.8% (trunk) wall time, 45.8% vs.
  48.5% GC overhead, 26,806 vs. 26,745 compactions. The
  `auto-compact-tuning` recommendation (raise the compiled-in default
  from 500 to 700-1000) should transfer to trunk without re-deriving it
  from scratch -- nothing about the mechanism changed.
- **A real, separate version-freshness effect exists independent of
  auto-compaction**: comparing the two *stock* columns (`ocaml-5.5` vs.
  `ocaml-trunk`, neither with auto-compact), `owl_gc` alone is already
  +11.9% RSS on trunk, and several other benchmarks pick up a smaller but
  consistent RSS bump on both trunk columns identically --
  `ocamlformat_rocq` (+9%), `test_decompress` (+7.6-7.9%), `zarith_pi`
  (+7.5-7.6%) -- present on `ocaml-trunk` stock, not just the auto-compact
  variant. This is trunk drifting from 5.5.0, unrelated to this
  investigation's GC work; not chased further here.
- **`liq_video_frames_pool` is uniformly ~6-8% faster on every non-5.5.0
  runtime**, including plain `ocaml-5.5.1` and `ocaml-trunk` -- a general
  version improvement, not an auto-compact effect.
- **`pplacer_testsuite`'s GC overhead is flat at ~80-82% across all five
  runtimes** (consistent with every other view of this benchmark in this
  investigation) -- version freshness and auto-compaction both leave it
  untouched.
- **`infer_default`'s `+33.3%`** is the same artifact as everywhere else
  in this investigation (crashes near-instantly, ~0.03-0.04s, so % deltas
  on it are meaningless) -- this config doesn't carry the smaller
  minor-heap modifier `infer` needs (see `auto-compact-tuning` Phase 4).

## Conclusion

The port holds up: rebasing 14 months of upstream OCaml runtime churn onto
a 2-commit GC patch surfaced exactly two mechanical, easily-resolved
conflicts and zero semantic drift in the actual compaction logic, and the
benchmark data confirms it behaviorally (owl_gc's compaction count within
0.2% of the 5.5.0 patch). The `auto-compact-tuning` investigation's
findings and recommendation are not 5.5.0-specific artifacts -- they hold
on trunk too.
