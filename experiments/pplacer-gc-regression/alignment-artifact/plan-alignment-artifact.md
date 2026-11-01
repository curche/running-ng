# Investigation Plan: Is the `ocaml-auto-compact-fp` Regression a Code-Layout Artifact?

## Background

Per `experiments/pplacer-gc-regression/plan-pplacer-gc-regression.md`'s
Phase 3 priority, `ocaml-auto-compact-fp` vs. `ocaml-5.5-fp` (+7.0% wall
time, +6.3% in the later 13-config run — see that plan's "Correction"
section) is the single cleanest, unconfounded real regression in the whole
flambda/fp investigation: same collection counts as stock (9152 minor / 3557
major), so it isn't a flambda-allocation-pattern artifact like everything
else in that matrix.

## Finding: the regression traces to `do_some_marking`, whose *source is unchanged*

Using the fp-enabled binaries built for that investigation (frame pointers
make `perf record -g` reliable through OCaml-compiled frames — see
`experiments/pplacer-gc-regression/flamegraphs/`), a differential analysis
of per-function self-time between `ocaml-5.5-fp` and `ocaml-auto-compact-fp`
(`flamegraphs/data/*.folded`, 3369-3422 unique stacks each) found:

| Function | stock % | patched % | delta (pp) |
|---|---|---|---|
| `do_some_marking` | 51.647 | 54.514 | **+2.866** |
| `caml_scan_global_roots` | 0.407 | 0.525 | +0.118 |
| *(everything else)* | | | < ±0.15 |
| `pool_sweep` | 17.329 | 16.390 | **−0.939** |
| `gemmish_c` (GSL) | 5.097 | 4.733 | −0.364 |
| `caml_darken` | 0.821 | 0.648 | −0.173 |

`do_some_marking`'s gain dwarfs every other change by >20×. This is the
whole story.

**But `do_some_marking`'s source is byte-for-byte identical** between stock
`5.5.0` and `ocaml-git@auto-compact-5.5` — confirmed via
`git diff 5.5.0..auto-compact-5.5 -- runtime/major_gc.c`, which shows the
patch only adds:
- `should_compact_from_stw_single()` — a new function, called **once per
  major *cycle*** at the STW barrier (`stw_cycle_all_domains`), not once
  per slice. There are 3557 major *slices* but many fewer cycles.
- `caml_max_percent_free` — a new global, read only inside the function above.
- `caml_shared_heap_grow_bsize()` in `shared_heap.c` — likewise only called
  from the STW-barrier function.
- Everywhere else: a pure rename (`force_compaction` → `compaction_mode`,
  `int` → a 3-value enum), same values threaded through unchanged control
  flow — no logic difference.

None of this touches the marking loop, the mark stack, per-object work, or
sweeping. **The patch adds essentially zero computation to the actual hot
path.**

### Direct evidence of a layout shift

Comparing `nm` output for both `tests.exe` binaries:

| Function | size (both builds) | stock addr | stock cache-line offset | patched addr | patched offset |
|---|---|---|---|---|---|
| `do_some_marking` | 0x387 (identical) | `0x4f8f60` | 32 | `0x4f91b0` | **48** |
| `pool_sweep` | 0x31a (identical) | `0x5051d0` | 16 | `0x505430` | **48** |
| `mark` | 0x284 (identical) | `0x4f92f0` | 48 | `0x4f9540` | **0** |

Every hot function is byte-identical in content and size, but shifted to a
different address — and a different position relative to a 64-byte cache
line — purely because `should_compact_from_stw_single` and
`caml_max_percent_free` were added elsewhere in the same translation unit
(`major_gc.c`), pushing every subsequent symbol forward by ~592 bytes.

## Hypothesis

**The ~7% regression is a code-layout/instruction-cache-alignment artifact,
not a real algorithmic cost of the auto-compact patch.** This class of
effect — identical hot-loop machine code running at measurably different
speed purely due to its address/alignment — is well documented (e.g.
Mytkowicz et al., "Producing Wrong Data Without Doing Anything Obviously
Wrong"). It would also parsimoniously explain why flambda so unpredictably
changed this regression's magnitude across the whole matrix (see the main
plan doc's Correction section): flambda changes the *size* of OCaml-compiled
sections in the final binary, which reshuffles where the linked-in C-runtime
object files — and their hot functions — land, independent of any semantic
interaction with the patch.

## Validation plan: the padding experiment

If the hypothesis is right, adding an equivalent amount of **functionally
inert** code to stock `major_gc.c` — same location, similar size, never
executed — should reproduce a similar wall-time shift, purely from
alignment, with zero behavioral change.

### Design

- New branch off **stock tag `5.5.0`** in `ocaml-git` (not `auto-compact-5.5`
  — must be a clean stock base with no other changes).
- Insert a dummy function at the *exact same location* as the real patch
  (immediately before `struct cycle_callback_params`, i.e. right after
  `cycle_major_heap_from_stw_single`'s closing brace) — same rough
  line count and branch structure as `should_compact_from_stw_single`,
  but operating on a local dummy counter instead of real GC state.
- Marked `__attribute__((used))` so the linker can't dead-code-eliminate it,
  but **never called from anywhere** — this is the cleanest possible test,
  since with zero executions there is no possible "real cost" left to
  attribute any measured difference to. A positive result here is airtight:
  it can only be explained by static layout shift.
- Build via running-ng's `opam-compiler` integration with
  `configure_args: ["--enable-frame-pointers"]` (matching `ocaml-5.5-fp`
  and `ocaml-auto-compact-fp`'s build flags exactly), so it's an apples-to-
  apples comparison.
- Build `pplacer_testsuite` against it, run 3 invocations,
  `perf_grp1|re-25|md-2` (same protocol as the rest of this investigation).

### Interpretation

- **If `ocaml-5.5-padded-fp`'s wall time lands close to `ocaml-auto-compact-fp`
  (~27.4s)** rather than stock (~25.7s): strong confirmation — the
  regression is (mostly) a pure alignment artifact of adding code to
  `major_gc.c`, independent of what that code does or how often it runs.
- **If it lands close to stock**: the hypothesis is wrong (or at least
  incomplete) — something about the real patch's actual behavior (even the
  STW-barrier-only `should_compact_from_stw_single` call, or the enum/type
  change) has a genuine, if small, runtime cost that pure inert padding
  doesn't reproduce. Would need to fall back to Phase 2's `perf probe`
  uprobe plan (main plan doc) to directly time `do_some_marking` calls.
- **A middle result** would suggest layout effects explain *part* of the
  regression, with a smaller genuine cost on top.

## Results (2026-07-15)

### v1: inert padding placed *after* `do_some_marking` — inconclusive

First attempt (branch `padding-test-5.5`) inserted the dummy function at the
same *textual* location as the real patch's `should_compact_from_stw_single`
(right after `cycle_major_heap_from_stw_single`, before `struct
cycle_callback_params` — which comes *after* `do_some_marking`'s own
definition at line 1423). Checking via `nm` after the build: **this did not
shift `do_some_marking`'s or `mark`'s address at all** — both identical to
unpadded stock. Only `pool_sweep` (defined later in the file) shifted, and by
a different amount (80B) than the real patch (608B). This meant v1 wasn't a
valid test of the hypothesis for the function that actually mattered.

(Two side notes from this phase, unrelated to the core hypothesis: (1) the
first wall-time attempt was heavily confounded by system contention — load
average 3.3-4.5, a duplicate 18+-hour-old process of this exact Claude
session, 50 logged-in users on this shared machine — one raw invocation of
`ocaml-auto-compact-fp` read 31.13s against a normal ~27.5s, a 12%+ spread
that would never appear in clean data; a same-day re-run under similar load
still showed 0.3-1.4s spreads, well above the <0.2s baseline. (2) a plain
`static uintnat` counter in the first dummy function draft let GCC prove it
was always 0 and constant-fold away most of the function body — a `volatile`
qualifier was needed to stop this.)

### v2: padding placed *before* `do_some_marking` — confirmed

Moved the padding to immediately before `do_some_marking`'s own definition
and made the counter `volatile` (branch `padding-test-5.5-v2`). Verified via
`nm` before running anything: this shifted `do_some_marking` by ~416 bytes
(cache-line offset 48→16), a comparable magnitude to the real patch's 592-byte
shift (offset 32→48) — a valid test.

Clean run (`turing-2026-07-15-Wed-130527`, spreads 0.07-0.34s across all 6
configs, matching historical clean-data baselines):

| Runtime | wall (s) | raw invocations |
|---|---|---|
| `ocaml-5.5-fp` (stock) | 25.89 | [25.76, 25.94, 25.89] |
| `ocaml-5.5-padded-fp` (v1 — didn't shift `do_some_marking`) | 25.93 | [25.93, 26.02, 25.90] |
| `ocaml-auto-compact-fp` (real patch) | 27.49 | [27.55, 27.46, 27.49] |
| **`ocaml-5.5-padded-v2-fp`** (shifted `do_some_marking`) | **27.61** | [27.88, 27.61, 27.54] |

**`ocaml-5.5-padded-v2-fp` lands within 0.12s (0.4%) of the real patch**,
while v1 sits right on top of stock (+0.2%). Collections/RSS identical
across the board (9152 minor / 3557 major / 0 compactions; 70.3-70.6MB).

## Conclusion: confirmed — the regression is a pure code-layout artifact

The auto-compact patch's actual logic (`should_compact_from_stw_single`,
called once per major *cycle*, never touching the marking/sweeping loops)
costs essentially nothing. The `ocaml-auto-compact-fp` vs. `ocaml-5.5-fp`
regression (+7 to +9% depending on run) is fully reproduced by functionally
inert padding that happens to push `do_some_marking` to a similar address —
and fully absent when padding doesn't move that function. This is airtight:
v2's dummy code is never called at runtime, so there is no behavioral
mechanism left to attribute the reproduced slowdown to other than
instruction-cache/alignment placement.

**Implication for the main investigation:** Phase 3's priority on
`ocaml-auto-compact-fp` as "the one clean, unconfounded real regression" no
longer holds — it isn't a real cost at all, just where the linker happened to
put a hot loop. This resolves that phase; no further source-level fix is
warranted for the auto-compact patch on this basis (see cross-reference
added to the main plan doc).

## Tooling

- Padding source changes: two branches in
  `/home/curche/git/ocaml-compiler/ocaml-git-padding-test` (a worktree off
  stock tag `5.5.0`), pushed to `curche/ocaml.git` as `padding-test-5.5` (v1)
  and `padding-test-5.5-v2` (v2).
- Config: `src/running/config/experiments/pplacer_alignment_check.yml`,
  6 configs (`ocaml-5.5-fp`, `ocaml-5.5-padded-fp`, `ocaml-5.5-padded-v2-fp`,
  `ocaml-auto-compact-fp`, `socaml-fp`, `socaml-auto-compact-fp`).
- `experiments/pplacer-gc-regression/alignment-artifact/Makefile` —
  `make validate` / `make run` / `make summarize` / `make clean`.
- Logs: `experiments/pplacer-gc-regression/alignment-artifact/logs/`
  (`turing-2026-07-15-Wed-130527/` is the clean, decisive run).

### Unrelated infrastructure bug found and fixed along the way

Building `ocaml-5.5-padded-v2-fp`'s pplacer benchmark failed with a `Gc.stat`
type mismatch (`duniverse/batteries-included/src/batGc.mli` missing the
`live_stacks_words` field OCaml 5.5 added). Root cause: that vendored,
git-untracked file in the shared `macro-benches` repo was touched/reverted at
04:47 on 2026-07-15 (likely by an external process on this 50-user shared
machine — possibly the `sandmark` nightly automation also observed running
throughout this investigation), stripping a local compatibility patch.
Existing runtimes were unaffected (running-ng only checks whether the
wrapper binary file exists, never re-invokes `dune build` for a runtime
that's already built), but *any new* runtime's first build would have hit
this. Fixed by restoring the missing 3 lines
(`##V>=5.5## live_stacks_words: int; ...`) by diffing against a cached,
already-compiled copy in `_build-ocaml-5.5-fp/default/duniverse/...`.

## Deliverables

- [x] Result of the padding run (wall time, RSS, gc_time, collection counts)
  compared against `ocaml-5.5-fp` and `ocaml-auto-compact-fp`.
- [x] Updated conclusion in this doc and a cross-reference added to the main
  plan doc's Phase 3.
