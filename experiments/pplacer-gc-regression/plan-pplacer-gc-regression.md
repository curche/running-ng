# Investigation Plan: `pplacer_testsuite` Regression (GC Stats)

## Background

`experiments/compactor-comparison/plots/turing-2026-07-01-Wed-230036/results.md`
finding #3 flagged `pplacer_testsuite` as a **~+19-20% wall-time regression**
present in *all three* non-stock runtimes (`ocaml-auto-compact`, `socaml`,
`socaml-auto-compact`) vs. stock `ocaml-5.5`, with **identical RSS** and
**zero compactions** everywhere — i.e. not attributable to compaction firing.
The original notes flagged this as needing follow-up.

The regression was reproduced for real on 2026-07-13 (run id
`turing-2026-07-13-Mon-230928`, logs now at
`experiments/pplacer-gc-regression/logs/turing-2026-07-13-Mon-230928/`,
config `src/running/config/experiments/pplacer_gc_regression.yml`), confirming
it is not noise:

| Runtime | wall (s) | gc_time (s) | gc_overhead % | minor GCs | major GCs | forced_major | compactions |
|---|---|---|---|---|---|---|---|
| `ocaml-5.5` | 23.36 | 17.18 | 73.5 | 9152 | 3557 | 1116 | 0 |
| `ocaml-auto-compact` | 27.90 (+19.4%) | 21.67 (+26.1%) | 77.7 | 9152 | 3557 | 1116 | 0 |
| `socaml` | 27.88 (+19.3%) | 21.17 (+23.2%) | 75.9 | 9152 | 3561 | 1116 | 0 |
| `socaml-auto-compact` | 28.15 (+20.5%) | 21.43 (+24.7%) | 76.1 | 9152 | 3561 | 1116 | 0 |

(medians of 3 invocations; full per-invocation data in the olly JSON sidecars
in the logs dir above)

## The key observation

**Minor and major collection *counts* are essentially unchanged** (minor:
exactly 9152 on all four; major: 3557 vs. 3557 vs. 3561/3561 — a 0.1% diff
that can't explain a 20%+ time regression). Non-GC ("mutator") time is also
roughly flat (~6.2s stock/auto-compact, ~6.7s socaml variants). **Almost the
entire wall-time regression is `gc_time` going up by 23-26% while the number
of GC cycles stays the same** — i.e. each collection is doing more work or
taking longer, not firing more often.

Back-of-envelope: `ocaml-auto-compact`'s extra 4.49s of gc_time spread over
3557 major cycles is ~1.26ms/cycle of added overhead — right in the range
you'd expect from an extra check/computation added to the per-slice path
(e.g. `should_compact_from_stw_single`, mentioned in the original results.md
as a suspect) rather than from any actual compaction (there are zero).

Build parity was checked and ruled out as a confound: all four switches
have identical `ocamlopt -config` output for `flambda` (false),
`ocamlopt_cflags` (`-O2 -fno-strict-aliasing -fwrapv -fPIC -pthread`), and the
same `dune` version (3.23.1). So this isn't a compiler-flags artifact.

`socaml`'s base version (`5.5.0+dev1-2026-01-22`) is a different dev snapshot
than `ocaml-auto-compact`'s (`5.5.0+ocaml-auto-compact`, based directly on tag
`5.5.0`) — the two branches share no common ancestor beyond both resembling
5.5. That two *independently developed* branches show the same ~20-25% GC
slowdown is either coincidence (both regress the same underlying benchmark
behavior for unrelated reasons) or points at something common to how
running-ng builds/invokes `executable:`-style runtimes vs. `version:`-style
ones. Phase 1 below checks this.

All four `tests.exe` binaries are unstripped native executables (confirmed
via `nm`) exposing `caml_major_collection_slice`, `caml_minor_collection`,
`caml_compact_heap`, `caml_compactions_count` — so `perf probe` (uprobes) can
instrument them without rebuilding.

---

## Update (2026-07-14): flambda / frame-pointers variant matrix

> **⚠️ Findings 1 and 2 below are corrected by new data** — a same-day
> follow-up run built *stock* `ocaml-5.5` with the same fp/flambda flags and
> found stock itself regresses substantially under them. That breaks the
> "vs. plain stock" framing used below. See **"Correction (2026-07-14, later
> run): stock itself regresses under flambda/fp"** immediately after this
> section for the corrected, same-flags-vs-same-flags comparison and revised
> conclusions. This section is kept as-is for the investigative trail.

**Question:** is the regression just unoptimized codegen (the original
switches were all built with `flambda: false`), or is it a genuine added cost
on the GC hot path that survives optimization?

**Method:** built 4 new opam switches from the *same* two source commits
(`ocaml-git@d2e194bce3` = `auto-compact-5.5`, `socaml-git@34988cfd7b` =
`new_compactor`), varying only the configure flags, via running-ng's built-in
`opam-compiler` integration (`type: OCaml` + `repo:`/`commit:`/
`configure_args:` — no manual switch setup needed; see config below). This
required pushing `new_compactor` to `curche/ocaml.git` on GitHub first (it
was local-only in `socaml-git`; `auto-compact-5.5` was already pushed there).

**Results** (medians of 3 invocations, run id `turing-2026-07-14-Tue-105038`,
`perf_grp1|re-25|md-2`, sorted by wall time; stock baseline this run: 23.40s /
70.3MB):

| Runtime | wall (s) | Δ vs stock | max RSS (MB) | gc_time (s) | minor GCs | major GCs |
|---|---|---|---|---|---|---|
| `ocaml-5.5` (stock) | 23.40 | — | 70.3 | 17.21 | 9152 | 3557 |
| `socaml-auto-compact-flambda` | **23.12** | **−1.2%** | 75.7 (+7.7%) | 17.23 | 8928 | 3547-3548 |
| `socaml-auto-compact-fp` | 25.19 | +7.6% | 70.2 | 18.80 | 9152 | 3561 |
| `ocaml-auto-compact-flambda-fp` | 26.44 | +13.0% | 75.4 (+7.3%) | 20.28 | 8926 | 3545-3546 |
| `socaml-auto-compact-flambda-fp` | 26.94 | +15.1% | 75.7 (+7.7%) | 20.81 | 8928 | 3549 |
| `ocaml-auto-compact-fp` | 27.43 | +17.2% | 70.0 | 20.83 | 9152 | 3557 |
| `ocaml-auto-compact` (plain, on record) | 27.90 | +19.2% | 70.0 | 21.67 | 9152 | 3557 |
| `socaml-auto-compact` (plain, on record) | 28.15 | +20.3% | 70.4 | 21.43 | 9152 | 3561 |

**Findings:**

1. **`ocaml-auto-compact` lineage: modest, monotonic improvement.**
   fp-alone barely moves it (19.2%→17.2%); flambda+fp together gets to 13.0%.
   Consistent with the standing hypothesis (an unconditional per-slice check,
   e.g. `should_compact_from_stw_single`) — flambda makes that check cheaper
   to execute but doesn't remove it. This lineage never matches stock even
   with every optimization on, i.e. **this is a real added cost, not a
   codegen artifact.**

2. **`socaml-auto-compact` lineage: non-monotonic, with an anti-synergy.**
   `flambda` alone **nearly eliminates the regression** (−1.2%, i.e.
   matches/beats stock) at the cost of +7.7% RSS. `fp` alone gives partial
   relief (+7.6%). But **`flambda`+`fp` together is worse than either alone**
   (+15.1%) — reproducible across all 3 invocations per variant (23.11-23.19s
   for flambda-alone vs. 26.92-26.97s for both combined; not noise). This
   suggests reserving a register for the frame pointer costs the chunk-based
   pool allocator's hot path more than flambda's optimizations can recover
   once the two are competing for registers in the same generated code.

3. **Reframes the root-cause hypothesis by lineage:**
   - `ocaml-auto-compact`'s regression looks like genuine added GC-hot-path
     work — optimization-resistant. Phase 3's `major_gc.c`/`gc_ctrl.c` diff
     review (below) is the right next step for *this* lineage.
   - `socaml-auto-compact`'s regression looks substantially like a
     codegen/register-allocation artifact — flambda alone nearly closes it.
     The interesting open question is no longer just "why is socaml slower"
     but **"why does frame-pointers reservation hurt so much more when
     flambda is also active"** — a new Phase 2b, below.
   - Both lineages independently show a consistent side effect: flambda
     builds drop minor-collection count from 9152 to ~8926-8928 (−2.4%) and
     raise RSS by ~7.5%, regardless of which branch. This is a flambda
     allocation-behavior effect (probably less boxing/fewer short-lived
     allocations), orthogonal to the auto-compact/new-compactor regression
     itself.

**New sub-investigation — Phase 2b:** `perf record -g --call-graph dwarf`
diff between `socaml-auto-compact-flambda` and `socaml-auto-compact-flambda-fp`
specifically (same source, same flambda flag, only frame-pointers differs) to
see which function(s) gain self-time purely from the fp reservation — this
is a much cleaner isolate than comparing across lineages.

Config: `src/running/config/experiments/pplacer_flambda_fp_check.yml`. Logs:
`experiments/pplacer-gc-regression/flambda-fp-check/` (see folder structure
below).

---

## Correction (2026-07-14, later run): stock itself regresses under flambda/fp

**What was missing:** the variant matrix above only ever built `ocaml-5.5`
*plain*. Every "Δ vs stock" figure implicitly compared an fp/flambda-built
patched runtime against *plain* stock — conflating "cost of the patch" with
"cost of the compiler flags." A follow-up run added `ocaml-5.5-fp`,
`ocaml-5.5-flambda`, and `ocaml-5.5-flambda-fp` (all built from upstream
`ocaml/ocaml.git` tag `5.5.0`, no patch) to close this gap. Run id
`turing-2026-07-14-Tue-223028`, config
`src/running/config/experiments/pplacer_flambda_fp_check.yml` (now includes
all 9 configs), full data in `flambda-fp-check/results-tables.md` and the
run directory itself.

**Result: frame-pointers and flambda substantially regress *plain, unpatched*
OCaml on this benchmark, with no patch involved at all:**

| Runtime | wall (s) | Δ vs plain stock | RSS (MB) |
|---|---|---|---|
| `ocaml-5.5` (plain stock) | 23.30 | — | 70.1 |
| `ocaml-5.5-fp` (fp only) | 25.73 | **+10.4%** | 70.5 |
| `ocaml-5.5-flambda-fp` (both) | 27.50 | **+18.0%** | 75.4 |
| `ocaml-5.5-flambda` (flambda only) | 28.17 | **+20.9%** | 75.3 |

Tight across all 3 invocations (flambda-only: 28.11/28.19/28.17s) — real, not
noise. This also directly confirms finding 3 above (flambda drops minor-GC
count, raises RSS) as a **general flambda-on-this-benchmark effect**,
independent of either patch: stock+flambda alone shows the same drop (9152→
8926 minor GCs) and the same ~+7.3% RSS increase.

### Corrected comparisons — same build flags, delta vs. stock *in that group*

**Plain** — stock `ocaml-5.5` 23.36s / 70.0MB (from the Phase 0 baseline run)

| Runtime | wall (s) | Δ | RSS (MB) |
|---|---|---|---|
| `socaml` | 27.88 | +19.3% | 70.1 |
| `ocaml-auto-compact` | 27.90 | +19.4% | 70.0 |
| `socaml-auto-compact` | 28.15 | +20.5% | 70.1 |

**fp only** — stock `ocaml-5.5-fp` 25.73s / 70.5MB

| Runtime | wall (s) | Δ | RSS (MB) |
|---|---|---|---|
| `socaml-auto-compact-fp` | 25.16 | **−2.2%** | 70.1 |
| `ocaml-auto-compact-fp` | 27.51 | **+7.0%** | 70.0 |

**flambda only** — stock `ocaml-5.5-flambda` 28.17s / 75.3MB

| Runtime | wall (s) | Δ | RSS (MB) |
|---|---|---|---|
| `socaml-auto-compact-flambda` | 23.13 | **−17.9%** | 75.5 |

**flambda + fp** — stock `ocaml-5.5-flambda-fp` 27.50s / 75.4MB

| Runtime | wall (s) | Δ | RSS (MB) |
|---|---|---|---|
| `ocaml-auto-compact-flambda-fp` | 26.39 | **−4.0%** | 75.6 |
| `socaml-auto-compact-flambda-fp` | 26.85 | **−2.4%** | 75.7 |

### What this corrects

1. **Finding 1 above ("ocaml-auto-compact never matches stock, real added
   cost") is wrong as stated.** `ocaml-auto-compact-flambda-fp` is actually
   **4.0% faster** than a same-flags stock build. The only combination where
   `ocaml-auto-compact` still shows a real, persistent regression vs.
   correctly-matched stock is **fp-only, at +7.0%** (down from the misleading
   +17.2%-vs-plain-stock figure) — and this is the cleanest isolated data
   point in the whole investigation, because fp doesn't change collection
   counts (9152/9152 minor, matching stock-fp exactly), so it isn't
   confounded by flambda's allocation-pattern shift the way every
   flambda-inclusive comparison is.

2. **Finding 2's "flambda alone nearly eliminates the socaml regression" is
   also reframed**, though the *direction* survives: `socaml-auto-compact-
   flambda` is 17.9% *faster* than same-flags stock+flambda, not just
   "matching plain stock" as originally stated — the effect is bigger than
   first reported, in the correct comparison. This is a real, striking
   result and still needs explaining (see revised Phase 2b below).

3. **The plain-build regression (~19-20%, both lineages) is unaffected by
   this correction** — it was already a same-flags comparison (`ocaml-5.5`
   plain vs. patched-plain, no confound possible) and stands as originally
   found.

4. **A unifying hypothesis worth testing in Phase 2/3:** if the patch's
   actual runtime cost is a small, roughly *fixed per-major-GC-cycle*
   overhead (e.g. an unconditional `should_compact_from_stw_single`-style
   check), then flambda's effect of *reducing collection frequency*
   (fewer, larger cycles) would mechanically shrink the *total* overhead
   from that check, without the check itself getting any cheaper per call.
   That would explain why flambda builds show parity/improvement despite
   the check still running on every cycle — worth checking directly with
   Phase 2's uprobe method (total call count × per-call cost, compared
   before/after flambda).

5. **Still unexplained and now the sharpest open question:** `socaml-auto-
   compact`'s fp-only result (**faster** than stock-fp) doesn't fit the
   "fixed per-call overhead" story at all (fp doesn't change collection
   count, so there's no "fewer calls" explanation available) — the chunk
   allocator's own code appears to *genuinely benefit* from frame-pointer
   builds relative to stock in a way `ocaml-auto-compact` does not. This,
   plus the flambda+fp anti-synergy (`socaml-auto-compact-flambda` 23.13s →
   `socaml-auto-compact-flambda-fp` 26.85s, +16.1%, while stock goes the
   *other* direction: `ocaml-5.5-flambda` 28.17s → `ocaml-5.5-flambda-fp`
   27.50s, −2.4%) means Phase 2b (below) is now the single most interesting
   open thread in this investigation.

Config: same `pplacer_flambda_fp_check.yml` (now 9 configs). Full tables:
`experiments/pplacer-gc-regression/flambda-fp-check/results-tables.md`.
Summary script: `experiments/pplacer-gc-regression/summarize_results.py`
(auto-discovers runtimes from any run directory — see its docstring).

---

## Phase 1 — Rule out non-GC confounds

- [x] Compiler flags / flambda / dune version parity across all 4 switches (done, see above — no difference found)
- [ ] Diff GC parameter *defaults* baked into each binary — `OCAMLRUNPARAM=v=0x400,e=25,d=2` (verbose GC) on one short invocation per runtime, compare the startup banner (initial minor heap size, `percent_free`, `max_percent_free` if present) to rule out a changed compile-time default silently changing behavior even with explicit `e=`/`d=` set on the command line.
- [ ] Check for CPU frequency scaling / thermal effects from run *ordering* — running-ng runs configs in blocks (all invocations of config A, then config B, ...) rather than interleaved. Re-run once with the config order reversed (`socaml-auto-compact` first, `ocaml-5.5` last) and confirm the regression direction/magnitude is order-independent.

## Phase 2 — Localize where the extra gc_time goes

Since collection *counts* match but *time* doesn't, instrument the two hot
entry points directly rather than guessing:

```bash
# Requires perf_event_paranoid <= 1 (currently -1, so no sudo needed for perf stat;
# perf probe/record on user binaries may still want root depending on config).
sudo perf probe -x <tests.exe> --add caml_major_collection_slice
sudo perf probe -x <tests.exe> --add 'caml_major_collection_slice%return'
sudo perf probe -x <tests.exe> --add caml_minor_collection
sudo perf probe -x <tests.exe> --add 'caml_minor_collection%return'

perf record -e probe_tests_exe:caml_major_collection_slice \
            -e probe_tests_exe:caml_major_collection_slice__return \
            -e probe_tests_exe:caml_minor_collection \
            -e probe_tests_exe:caml_minor_collection__return \
            -o major_minor.data -- \
  env OCAMLRUNPARAM="e=25,d=2" <tests.exe binary> 5

perf script -i major_minor.data   # entry/return timestamp pairs -> sum durations
```

Do this for `ocaml-5.5` and `ocaml-auto-compact` (cleanest pair — identical
major/minor counts) first. Compare:
- total time inside `caml_major_collection_slice` (sum of per-call durations)
- total time inside `caml_minor_collection`
- per-call average for each

This tells us whether the extra ~4.5s lands in major, minor, or is spread
between both — and whether it's a fixed per-call tax (supports "extra check
added to the hot path") or growing per-call (supports "doing more scan work
per cycle", e.g. larger free-list/pool bookkeeping in socaml's chunk
allocator).

Repeat for `socaml` vs `ocaml-5.5` (accepting the ~0.1% major-count noise).

**Priority note (post-2026-07-14 variant matrix, corrected below):** Phase
2/3 as originally scoped matter most for the **`ocaml-auto-compact` +
fp-only** combination specifically — that's the one comparison, out of the
whole matrix, that survives correction as a real, unconfounded regression vs.
same-flags stock (+7.0%, collection counts identical so it isn't a
flambda-allocation-pattern artifact). The plain-build regression (~19-20%,
both lineages) also stands. Every flambda-inclusive comparison, once
corrected against a same-flags stock baseline, shows the patched runtime at
parity or *faster* — so Phase 2/3's "genuine GC-hot-path cost" framing
applies mainly to the plain build and to `ocaml-auto-compact-fp`, not
generally across all optimization levels as first thought. See the
"Correction" section above for the full reasoning. The *primary* open
mystery is now Phase 2b below (why fp+flambda combined is worse than flambda
alone specifically for `socaml-auto-compact`, when the opposite happens for
stock) — though the source diff below is still useful background for
understanding what's on each lineage's hot path.

## Phase 2b — Why does frame-pointers regress *worse* when flambda is also on, for socaml only (stock does the opposite)

Isolated pair, same source/flambda flag, only `--enable-frame-pointers`
differs: `socaml-auto-compact-flambda` (23.12-23.13s) vs.
`socaml-auto-compact-flambda-fp` (26.85-26.94s, +16.1-16.5% relative to the
flambda-only build). This is a cleaner isolate than any cross-lineage
comparison — **and now sharper still**: stock itself goes the *other*
direction on the identical flag change (`ocaml-5.5-flambda` 28.17s →
`ocaml-5.5-flambda-fp` 27.50s, **−2.4%**), so this isn't "fp generally hurts
flambda builds" — it's specific to socaml's chunk-based allocator code.

```bash
perf record -g --call-graph dwarf -o flambda.data -- \
  env OCAMLRUNPARAM="e=25,d=2" \
  /home/curche/git/macro-benches/benchmarks/pplacer/pplacer_testsuite-socaml-auto-compact-flambda 5
perf record -g --call-graph dwarf -o flambda-fp.data -- \
  env OCAMLRUNPARAM="e=25,d=2" \
  /home/curche/git/macro-benches/benchmarks/pplacer/pplacer_testsuite-socaml-auto-compact-flambda-fp 5
perf diff flambda.data flambda-fp.data
```

Candidate explanations to check against the diff:
- Register pressure: `-fno-omit-frame-pointer` (confirmed in `ocamlopt_cflags`
  for both fp-enabled switches) permanently reserves `rbp`, shrinking the
  register file available to the C compiler for the chunk allocator's
  free-list/pool bookkeeping (`shared_heap.c`) — flambda-optimized OCaml code
  itself doesn't use `rbp` for allocation the same way C does, so this would
  show up specifically in the *C runtime* functions' generated assembly
  (`objdump -d` comparing `caml_major_collection_slice`/pool-alloc functions
  between the two switches), not in OCaml-compiled code.
- Check whether this is major-GC-specific or general: `gc_time` delta
  (17.23s → 20.81s, +3.58s) is close to the *entire* wall-time delta
  (23.12s → 26.94s, +3.82s) — so, like the original finding, this is almost
  entirely a GC-side effect, not mutator slowdown. Points back at
  `caml_major_collection_slice`/pool functions as the place to look, per
  Phase 2's uprobe method.

## Phase 3 — Source diff review, targeted by Phase 2's answer

> **✅ RESOLVED (2026-07-15) for `ocaml-auto-compact`** — see
> `experiments/pplacer-gc-regression/alignment-artifact/plan-alignment-artifact.md`.
> The flamegraph diff (below, Phase 4) found the entire self-time delta
> concentrated in `do_some_marking` (+2.87pp), despite that function's
> **source being byte-identical** between stock and `auto-compact-5.5`. A
> controlled padding experiment then confirmed this directly: inert,
> never-executed dummy code inserted in `major_gc.c` reproduces the full
> regression when it happens to shift `do_some_marking`'s address/cache-line
> alignment by a comparable amount to the real patch, and reproduces nothing
> when it doesn't. **`ocaml-auto-compact-fp`'s regression is a pure
> code-layout/cache-alignment artifact, not a real cost of the patch's
> logic.** The source diff review below is kept for reference but no longer
> needed as an open question for this lineage.

- `ocaml-auto-compact` (ocaml-git, `auto-compact-5.5` branch @ `d2e194bce3`):
  ```bash
  git -C /home/curche/git/ocaml-compiler/ocaml-git diff 5.5.0..auto-compact-5.5 -- \
    runtime/major_gc.c runtime/gc_ctrl.c runtime/compact.c runtime/major_gc.h
  ```
  Look specifically for code added to the *unconditional* per-slice/per-cycle
  path (not gated behind `if (compaction_mode != Compaction_none)` or
  similar) — a call to `should_compact_from_stw_single` (or its overhead-ratio
  computation) running on every major slice regardless of outcome is the
  prime suspect given results.md's own note about that function. Confirmed:
  this function only runs once per major *cycle* at the STW barrier, never
  touching the marking/sweeping loops — consistent with the alignment-artifact
  finding above (there was never a real per-slice cost to find).

- `socaml` (socaml-git, `new_compactor` branch): find the actual base commit
  it diverged from (not tag `5.5.0` — its `ocamlopt -config` reports
  `5.5.0+dev1-2026-01-22`), then diff `runtime/shared_heap.c` /
  `runtime/major_gc.c` for changes to pool allocation/free-list bookkeeping
  that run on every sweep, not just during an actual pool-compaction event.
  Lower priority than Phase 2b now — corrected data shows `socaml-auto-
  compact-flambda` is actually **17.9% faster** than same-flags stock (not
  merely "matching" it as first thought), so the source-level "extra work
  per sweep" story explains the plain-build regression but not why flambda
  flips this lineage to faster-than-stock. That flip, and its reversal when
  fp is added on top, is what Phase 2b targets.

## Phase 4 — Flamegraph diff (if Phase 2/3 don't pinpoint it cleanly)

Manual `perf record -g --call-graph dwarf` per runtime (outside running-ng's
`PerfAndOllyAttach`, which only does `perf stat`, not `perf record`):

```bash
perf record -g --call-graph dwarf -o ocaml-5.5.data -- \
  env OCAMLRUNPARAM="e=25,d=2" <tests.exe-ocaml-5.5> 5
perf record -g --call-graph dwarf -o ocaml-auto-compact.data -- \
  env OCAMLRUNPARAM="e=25,d=2" <tests.exe-ocaml-auto-compact> 5
perf diff ocaml-5.5.data ocaml-auto-compact.data
```

Look for functions with a large *relative* self-time delta — expect the
culprit to show up directly since mutator code is presumably identical
bytecode/native code (same pplacer OCaml source) and only runtime C code
differs.

## Phase 5 — Confirm and (optionally) propose a fix

Once a specific function/code path is implicated:
- Add a minimal `rdtsc`-based counter around just that path, rebuild, rerun
  1 invocation per runtime, confirm it accounts for ~the full gc_time delta.
- If it's genuinely dead-weight overhead (e.g. an O= threshold check that's
  cheap to skip when nowhere near triggering), propose/prototype a guard and
  re-run the full `pplacer_gc_regression.yml` config to confirm the
  regression shrinks without affecting `owl_gc`'s actual compaction behavior.

---

## Config / tooling already in place

- **`src/running/config/experiments/pplacer_gc_regression.yml`** — isolated
  `pplacer_testsuite`-only config, the original 4 runtimes/switches from
  `macrobenchmarks_compactor_4way.yml` plus `ocaml-auto-compact-flambda-fp`,
  3 invocations, `perf_grp1|re-25|md-2`. Re-run with:
  ```bash
  PYTHONPATH=src RUNNING_MACRO_BENCH_DIR=/home/curche/git/macro-benches \
  PATH=/home/curche/git/runtime_events_tools/_build/install/default/bin:$PATH \
  python3 -m running runbms experiments/pplacer-gc-regression/logs \
    src/running/config/experiments/pplacer_gc_regression.yml
  ```
  (patched `olly` on `runtime_events_tools` branch `count-auto-compactions`
  is required for `compactions` counts to include `EV_COMPACT`, not just
  `EV_EXPLICIT_GC_COMPACT` — see original results.md.)

- **`src/running/config/experiments/pplacer_flambda_fp_check.yml`** — the
  flambda/frame-pointers variant matrix, now **9 configs**: `ocaml-5.5`,
  `ocaml-5.5-fp`, `ocaml-5.5-flambda`, `ocaml-5.5-flambda-fp` (the stock
  controls added for the correction above), `ocaml-auto-compact-fp`,
  `ocaml-auto-compact-flambda-fp`, `socaml-auto-compact-fp`,
  `socaml-auto-compact-flambda`, `socaml-auto-compact-flambda-fp`. Each
  non-stock runtime is built automatically on first use via running-ng's
  `opam-compiler` integration (`type: OCaml` + `repo:`/`commit:`/
  `configure_args:`, or `version:`/`configure_args:` for the stock-5.5
  variants which pull from upstream `ocaml/ocaml.git`) — no manual switch
  setup. Re-run with the same env-var pattern as above, pointing at
  `experiments/pplacer-gc-regression/flambda-fp-check` as the log dir.
  Source refs used:
  - `https://github.com/ocaml/ocaml.git#5.5.0` (upstream, for the 3 stock
    fp/flambda/flambda-fp controls — unpatched)
  - `https://github.com/curche/ocaml.git#auto-compact-5.5` (= `ocaml-git`
    local branch `auto-compact-5.5` @ `d2e194bce3`, already pushed)
  - `https://github.com/curche/ocaml.git#new_compactor` (= `socaml-git`
    local branch `new_compactor` @ `34988cfd7b` — **pushed during this
    investigation on 2026-07-14**; it did not previously exist on any
    GitHub remote)

- **`src/running/config/experiments/pplacer_scratch_rebuild_check.yml`** —
  the from-scratch reproducibility sanity check: all 9 runtimes above,
  rebuilt under `-scratch`-suffixed switch names via `opam-compiler` (plus
  two source refs newly needed for the *plain*, no-flag builds of the
  `ocaml-auto-compact`/`socaml`/`socaml-auto-compact` lineage that weren't
  previously opam-compiler-managed:
  `https://github.com/curche/ocaml.git#auto-compact-5.5` with
  `configure_args: []`, and a newly pushed
  `https://github.com/curche/ocaml.git#socaml-chunk-only`, = `socaml-git`
  commit `7f6d55c648`, the pre-auto-compact chunk-allocator-only commit,
  previously only reachable as an ancestor of `new_compactor`). Does not
  touch or delete any existing switch. Log dir:
  `experiments/pplacer-gc-regression/scratch-rebuild-check/`.

- **New opam switches** (all reusable, all built via `opam compiler create`):
  `running-ng-ocaml-auto-compact-fp`, `running-ng-ocaml-auto-compact-flambda-fp`,
  `running-ng-socaml-auto-compact-fp`, `running-ng-socaml-auto-compact-flambda`,
  `running-ng-socaml-auto-compact-flambda-fp`, `running-ng-ocaml-5.5-fp`,
  `running-ng-ocaml-5.5-flambda`, `running-ng-ocaml-5.5-flambda-fp`, plus 8
  more under `-scratch`-suffixed names from the reproducibility check.
  (`ocamlfind` failed to install automatically in several of these — same
  `findlib_config.ml`/`ocaml_stdlib` build error seen throughout this
  investigation; `dune` installed fine in all of them, and benchmark builds
  use dune from the tools switch on `PATH` as a fallback, so this hasn't
  blocked anything.)

## Folder structure (this directory)

```
experiments/pplacer-gc-regression/
├── plan-pplacer-gc-regression.md          — this file
├── session-log-20260714-000452.md         — narrative summary of the initial
│                                             dry-run/reproduction session
├── full-conversation-export-ea4ff5e9-e897-4019-99da-a17ee76eeac9.md
│                                           — full raw transcript (every tool
│                                             call + output) for that session
├── render_full_export.py                  — regenerates the above from any
│                                             session's ~/.claude/projects
│                                             JSONL transcript (see its
│                                             docstring for usage)
├── summarize_results.py                   — auto-discovers runtimes in any
│                                             run dir below and prints a
│                                             wall/RSS/gc_time/collections
│                                             table sorted by wall time, e.g.
│                                             `python3 summarize_results.py
│                                             flambda-fp-check/turing-...`
├── logs/
│   └── turing-2026-07-13-Mon-230928/      — Phase 0 baseline: 4 original
│                                             runtimes, 3 invocations,
│                                             confirms results.md's numbers
│                                             (table at top of this doc)
├── flambda-fp-check/
│   ├── run_stdout.log                     — stdout of the first (2-config)
│   │                                         flambda+fp check
│   ├── run_stdout_full_matrix.log         — stdout of the 6-config variant
│   │                                         matrix build+run
│   ├── run_stdout_with_stock_variants.log — stdout of the 9-config run that
│   │                                         added ocaml-5.5-fp/-flambda/
│   │                                         -flambda-fp (the correction)
│   ├── results-tables.md                  — the full "all values" table plus
│   │                                         the 4 same-flags correct-
│   │                                         comparison tables (source for
│   │                                         the Correction section above)
│   ├── turing-2026-07-14-Tue-102910/      — first check: ocaml-5.5 vs.
│   │                                         ocaml-auto-compact-flambda-fp
│   │                                         only (superseded, kept for
│   │                                         reference)
│   ├── turing-2026-07-14-Tue-105038/      — the 6-config variant matrix;
│   │                                         numbers in the "Update
│   │                                         (2026-07-14)" table above
│   └── turing-2026-07-14-Tue-223028/      — the 9-config run (adds the 3
│                                             stock-5.5 fp/flambda controls);
│                                             numbers in the "Correction"
│                                             section above come from here
└── scratch-rebuild-check/
    ├── run_stdout.log                     — stdout of the from-scratch run
    ├── summarize_results.py               — earlier, single-run-dir version
    │                                         of the script now at the top
    │                                         level (kept for history; use
    │                                         the top-level one going forward)
    └── turing-2026-07-14-Tue-122822/      — sanity check: all 9 runtimes
                                              (8 fresh opam-compiler builds
                                              under "-scratch"-suffixed
                                              names, ocaml-5.5 reused)
                                              rebuilt completely independently
                                              of every prior switch; every
                                              number reproduced within 0.4%
```

Each `turing-*` run directory follows the standard running-ng layout:
`olly_pplacer_testsuite.0.0.<runtime>.perf_grp1.re-25.md-2.macro-pplacer.json`
(NDJSON, one line per invocation — `wall_time`, `max_rss_kb`, `gc_time`,
`gc_overhead`, `collections.{minor,major,forced_major,compactions}`),
matching `perf_pplacer_testsuite...json` (raw `perf stat` counters), and
`pplacer_testsuite...log` (build/run/system-info log), plus `runbms.yml` /
`runbms_args.yml` recording the resolved config and CLI args for that run.

## Deliverables

- `findings.md` in this folder once Phase 2/2b/3 converge: root cause(s) —
  per the 2026-07-14 correction, likely two separate write-ups: (1) the
  plain-build regression plus `ocaml-auto-compact-fp`'s persistent +7.0% —
  the one unconfounded, real, per-lineage cost, probably the
  `should_compact_from_stw_single`-style unconditional check; and (2) the
  `socaml-auto-compact` flambda/fp codegen interaction (faster than stock
  under flambda, but *worse* than flambda-alone when fp is added, the
  opposite of what happens to stock under the same flag change) — a
  register-pressure/codegen story specific to the chunk allocator, per
  Phase 2b. Supporting perf/diff evidence for both, and whether either is
  fixable or an accepted cost of the auto-compact/new-compactor design.
- If a fix is prototyped: a diff against the relevant branch
  (`ocaml-git:auto-compact-5.5` and/or `socaml-git:new_compactor`) plus a
  before/after run of `pplacer_gc_regression.yml` and/or
  `pplacer_flambda_fp_check.yml` proving the regression shrinks.
