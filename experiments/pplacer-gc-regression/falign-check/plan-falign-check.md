# Investigation Plan: Does forcing a common function alignment eliminate the `ocaml-auto-compact-fp` regression?

## Background

Both the flambda/fp variant matrix
(`experiments/pplacer-gc-regression/plan-pplacer-gc-regression.md`) and the
padding experiment
(`experiments/pplacer-gc-regression/alignment-artifact/plan-alignment-artifact.md`)
established that `ocaml-auto-compact-fp`'s ~7-9% regression on
`pplacer_testsuite` traces to `do_some_marking` landing at a different
64-byte cache-line offset in the patched binary than in stock (32→48),
despite byte-identical source and machine code. Inert padding that
reproduces a comparable offset shift reproduces the regression; padding that
doesn't move the function reproduces nothing.

That investigation used hand-written dummy C functions to *indirectly* nudge
addresses, discovering the resulting offset only after the fact via `nm`.
This experiment uses a much more direct lever: **`gcc -falign-functions=N`**,
which forces every function's start address to a chosen power-of-two
boundary — no source changes, no guessing.

## GCC alignment flags on this machine

GCC here is 13.3.0 (Ubuntu 24.04). Checked directly:
- `-fmin-function-alignment` (GCC ≥14) is **not available** — this GCC
  suggests `-flimit-function-alignment` instead, which caps alignment down
  for small functions rather than forcing it up; not what we want.
- `-falign-functions=N` **is** available and confirmed to work: at default
  `-O2` (no explicit flag), GCC already emits `.p2align 4` (16-byte
  alignment) for every function — this is exactly why every offset we've
  observed so far (0, 16, 32, 48) has been a multiple of 16: functions are
  always 16-byte aligned, but *which* of the 4 possible 16-byte-aligned
  slots within a 64-byte cache line depends on cumulative code size before
  it, which is what patches/padding perturb.
- `-falign-functions=64` forces every function's start to a 64-byte
  boundary — i.e. cache-line offset 0, always, regardless of what precedes
  it in the object file. Confirmed via a standalone compile +
  `nm`: `do_some_marking` and `mark` both land at offset 0 with this flag,
  vs. their normal (unforced) offsets.
- Verified the flag reaches the actual runtime build: `CFLAGS` is a
  standard autoconf variable, and OCaml's `./configure` accepts trailing
  `VAR=value` tokens same as env vars — `./configure --enable-frame-pointers
  CFLAGS=-falign-functions=64` correctly sets `CFLAGS=-falign-functions=64
  -pthread` in the resulting `Makefile.config`. running-ng's
  `configure_args:` list is just space-joined after `./configure `, so
  adding `"CFLAGS=-falign-functions=64"` as a list element works without any
  code changes to running-ng itself.

## Design: 2×2×2 matrix

| | plain | `-fp` |
|---|---|---|
| **stock, no falign** | `ocaml-5.5` (on record) | `ocaml-5.5-fp` (on record) |
| **stock, falign=64** | `ocaml-5.5-falign` [new] | `ocaml-5.5-fp-falign` [new] |
| **auto-compact, no falign** | `ocaml-auto-compact-scratch` (on record, opam-compiler-built, `configure_args: []`) | `ocaml-auto-compact-fp` (on record) |
| **auto-compact, falign=64** | `ocaml-auto-compact-falign` [new] | `ocaml-auto-compact-fp-falign` [new] |

4 new switches needed; the other 4 already exist from prior investigations
(reused as-is — `ocaml-auto-compact-scratch` specifically chosen over the
historical manually-built `ocaml-auto-compact` switch because it shares the
same `configure_args: []` opam-compiler recipe as everything else here,
avoiding the `--enable-ocamltest` build-recipe mismatch flagged in the
padding-on-patch follow-up).

## Hypothesis

If `-falign-functions=64` is applied to **both** stock and
`auto-compact-5.5`, every function — including `do_some_marking` — should
land at the *same* offset (0) in both binaries. If the alignment-artifact
theory is complete, this should **eliminate the wall-time gap** between
`ocaml-5.5-fp-falign` and `ocaml-auto-compact-fp-falign` (and similarly for
the plain pair), since there's no longer any difference in *where* the hot
function sits — only in the (essentially free) `should_compact_from_stw_single`
logic itself.

Secondary questions this design also answers:
- Does forcing offset 0 change *stock's own* baseline at all (is offset 0
  neutral, better, or worse than stock's natural offset 32)?
- Does `-falign-functions=64` interact with `-fp` (frame pointers) in any
  surprising way, given fp changes every function's compiled size?

## Config

`src/running/config/experiments/pplacer_falign_check.yml`, 8 configs,
`perf_grp1|re-25|md-2`, 3 invocations, matching the rest of this
investigation's protocol.

## Tooling

- Makefile in this folder (`make validate` / `make run` / `make summarize`
  / `make clean`), copied from the alignment-artifact folder's pattern.
- Logs: `experiments/pplacer-gc-regression/falign-check/logs/`.

## Results (2026-07-16, run `turing-2026-07-16-Thu-181351`)

`nm` verification on the built `tests.exe` binaries confirmed the flag
worked exactly as intended — **both `do_some_marking` and `mark` land at
cache-line offset 0 in all 4 `-falign` variants**, vs. their natural
(scattered) offsets in the unforced builds:

| Runtime | `do_some_marking` offset | `mark` offset |
|---|---|---|
| `ocaml-5.5` | 16 | 48 |
| `ocaml-5.5-fp` | 32 | 48 |
| `ocaml-auto-compact-scratch` | 0 | 32 |
| `ocaml-auto-compact-fp` | 48 | 0 |
| `ocaml-5.5-falign` | **0** | **0** |
| `ocaml-5.5-fp-falign` | **0** | **0** |
| `ocaml-auto-compact-falign` | **0** | **0** |
| `ocaml-auto-compact-fp-falign` | **0** | **0** |

Wall-time results (medians of 3 invocations, `perf_grp1|re-25|md-2`; all
spreads 0.07-0.28s except `ocaml-5.5` itself at 0.96s — noisy, but it's only
a reference point, not part of the key comparison):

| Pair | wall (s) | gap |
|---|---|---|
| `ocaml-5.5-fp-falign` vs. `ocaml-auto-compact-fp-falign` | **26.29 vs. 26.29** | **0.00s** |
| `ocaml-5.5-falign` vs. `ocaml-auto-compact-falign` | 27.30 vs. 27.13 | −0.17s (patched marginally faster — noise) |
| *(reference, unforced)* `ocaml-5.5-fp` vs. `ocaml-auto-compact-fp` | 25.87 vs. 27.41 | +1.54s (+6.0%) |
| *(reference, unforced)* `ocaml-5.5` vs. `ocaml-auto-compact-scratch` | 23.65 vs. 28.04 | +4.4s (+18.6%) |

`gc_time` shows the identical pattern (19.96 vs. 19.93; 21.08 vs. 20.94 —
both essentially equal once aligned), consistent with every other result in
this investigation being a pure per-collection-cost story.

## Conclusion: complete, decisive confirmation

Forcing `do_some_marking`/`mark` to identical addresses in both stock and
`auto-compact-5.5` — via a single compiler flag, with **zero source
changes** — eliminates the regression entirely, in both the `-fp` and plain
cases. This is the cleanest possible confirmation of the alignment-artifact
theory established in
`experiments/pplacer-gc-regression/alignment-artifact/plan-alignment-artifact.md`:
the ~7-19% `ocaml-auto-compact` regression (magnitude depends on build flags)
is *entirely* explained by where these two hot functions happen to land in
the binary, not by anything the patch's logic actually does.

One more nuance worth noting: absolute wall time at forced offset 0 (26-27s)
is *worse* than stock's own naturally-occurring offset in the unforced
builds (23-26s) — offset 0 isn't "the good one," it's just *equally applied*
to both binaries, which is what removes the disparity between them. This
matches the padding-on-patch follow-up's finding that alignment effects are
per-offset idiosyncrasies (plausibly icache-line-split, frontend-decode, or
branch-predictor-aliasing effects tied to the exact address) rather than a
directional or universally-rankable property — there's no "best" alignment
in general, only consistency (or its absence) between whatever two builds
are being compared.

**This closes the investigation into `ocaml-auto-compact-fp`'s regression.**
No further source-level work is warranted on the auto-compact patch itself
on this basis.
