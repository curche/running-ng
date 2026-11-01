# worklog -- falign value sweep

Follow-up to `../pplacer-falign-deep-dive/`. User: "try smaller falign in
new experiments."

## Phase 0 -- setup

Built 2 new opam switches (`ocaml-5.5-falign16`, `ocaml-5.5-falign32`),
reused the existing `ocaml-5.5-falign` switch (=64) and `ocaml-5.5`.
Scoped the harness comparison to 6 benchmarks: `pplacer_testsuite` (the
regressed one, primary target), `frama_c_eva_sqlite` + `menhir_sql_parser`
+ `menhir_ocamly` (falign64's biggest wins, checking they survive a
smaller value), `owl_gc` + `zarith_pi` (flat controls).

## Phase 1 -- hit the SAME stale-build bug a second time

`make run` came back 22/24 cells -- `frama_c_eva_sqlite` and `owl_gc`
missing on `ocaml-5.5-falign` (the reused switch). Root cause: identical to
TASK 3's gapfill bug and `../pplacer-falign-deep-dive/`'s Phase 1 bug --
that investigation's `config-rebuild.yml` run deleted+rebuilt
`_build-ocaml-5.5-falign` but only requested `pplacer_testsuite` as a
target, so dune never touched `frama_c_eva.exe`/`owl_gc.exe` in the fresh
build dir, leaving their wrapper scripts pointing at now-missing binaries.

Lesson (now three occurrences of this exact bug class): deleting/rebuilding
a shared `_build-<runtime>` directory for ONE benchmark's sake silently
breaks every OTHER benchmark already built against that directory, because
running-ng's build-skip check is wrapper-existence-based, not
binary-existence-based, and dune only builds what's explicitly requested.
Should have proactively rebuilt (or at least existence-checked) every
`_build-ocaml-5.5-falign` consumer after the pplacer investigation's forced
rebuild, not just the one benchmark it needed at the time.

Fixed the same way as before: deleted the 2 stale wrappers (+ a
precautionary delete of `frama_c_eva_t-ocaml-5.5-falign`, sharing the same
binary), wrote `config-gapfill.yml`, reran through the harness. Both
rebuilt cleanly, merged into the main run dir, 24/24 complete.

## Phase 2 -- harness comparison is too noisy to trust directly

`make plot` produced a 6-benchmark x 4-runtime table, but two benchmarks
(`menhir_sql_parser`, `menhir_ocamly`) flip SIGN entirely versus TASK 3's
original falign64 numbers for the same comparison. Consistent with
`../eio-deep-dive/`'s finding that this unpinned harness carries real
environmental noise (hybrid P/E-core CPU, `powersave` governor, no ASLR
control) -- decided not to trust this table for judging whether falign16
"keeps the wins," only for pplacer's own pinned deep-dive (below), which is
the benchmark that actually matters here.

## Phase 3 -- pinned deep-dive on pplacer_testsuite, all 4 values

Wrote `pplacer_deep_dive.sh` (adapted from
`../pplacer-falign-deep-dive/capture.sh`'s `stat` mode): `perf stat -r 20`
full counter set + `perf stat -r 10 -M tma_frontend_bound` topdown, looped
over all 4 runtimes.

Hit the exact double-backgrounding footgun from
`../pplacer-falign-deep-dive/worklog.md` Phase 1 a SECOND time -- launched
the script with a trailing `&` *and* `run_in_background: true` together,
so the harness only tracked the outer shell (which exits immediately after
printing a PID) while the actual 4-runtime script ran fully detached.
Should have internalized this after documenting it the first time; didn't.
Started a proper single-level wait (`while pgrep ...; do sleep 10; done`),
which itself then got killed by an unrelated session interruption
(`/recap`) -- but the underlying detached script kept running regardless
(it was never dependent on the wait wrapper), and had already finished all
4 runtimes by the time this was checked. No data lost, just an extra
"check on the rerun" round-trip that a properly single-level backgrounded
command would have avoided.

Results (see `results.md` for the full table): **falign16 removes the
regression.** Wall time +0.26% (vs +3.04-3.26% at 32/64) -- close to the
±0.01-0.04% noise floor established in the two prior pinned investigations,
i.e. not clearly distinguishable from noise. Frontend Bound stays at 22.7%
(same as stock) vs jumping to 26.1-26.5% at 32/64. Cache-misses still drop
at every value (-6 to -7.5%), so the earlier "not an icache problem"
finding holds regardless of alignment size.

**Threshold, not gradient**: falign32 and falign64 land on statistically
indistinguishable costs (both ~+3% wall, ~+18-21% raw frontend-bound
delta) -- crossing from 16 to 32 crosses whatever fetch-window boundary
triggers the tax; going further to 64 doesn't cost more. Consistent with
16 bytes being close to x86-64's natural function alignment already.

## Not done here (see results.md "Next steps")

Pinned verification that falign16 still delivers `frama_c_eva_sqlite`'s
win (the noisy harness table suggests yes, -9.0% vs -15.2% at falign64,
but given how unreliable that same table proved on two other benchmarks,
this needs the same `perf stat -r 20` treatment before trusting a number).
Left as a follow-up given the primary ask (verify+fix pplacer) is answered.
