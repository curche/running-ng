# worklog -- pplacer_testsuite falign mechanism

Follow-up to TASK 3. User: "Comparing stock ocaml with falign version,
there still seems to be a slowdown... verify the mechanism on
pplacer_testsuite before mitigating."

## Phase 0 -- identify the real signal

Pulled TASK 3's `wall_time_table.txt` for ocaml-5.5 vs ocaml-5.5-falign
across all 29 benchmarks. Most are within +-2% (noise-level, especially
given `../eio-deep-dive/`'s finding that the unpinned harness carries real
environmental noise). `pplacer_testsuite` is the standout real slowdown:
11.22s -> 11.58s (+3.2%) -- also notable because it's literally the
benchmark this entire multi-task investigation started from, and its
magnitude keeps shifting across runs/machines (+3.2% here, +8.7-11.9% in
`../compactor-comparison-falign/results.md`, ~19-20% on the original
turing machine) -- itself a clue that whatever's happening is sensitive to
exact code layout, not a fixed cost.

## Phase 1 -- hit my own earlier bug

Set up `capture.sh` (same pattern as `../eio-deep-dive/capture.sh`) and ran
`perf stat -r 20` for `ocaml-5.5` cleanly (11.21s +-0.04%, full counter
set). The `ocaml-5.5-falign` run came back nonsensical: 2ms task-clock, 9M
instructions instead of ~134B. Root cause: `_build-ocaml-5.5-falign` was
the directory TASK 3's `gapfill2` fix deleted wholesale (to fix
`devkit_gzip`'s stale dune cache) and only rebuilt `devkit_gzip` in --
`pplacer_testsuite`'s binary was never rebuilt afterward, so the (still
present) wrapper script pointed at a `tests.exe` that no longer existed.

Fixed properly through the harness, not a hand-rolled build: wrote
`config-rebuild.yml` (1 runtime, 1 benchmark), discovered the wrapper's
mere *existence* (not the underlying binary) is what running-ng's
build-skip check looks at, so had to delete the stale wrapper script itself
(not just clear a `.build-failed` sentinel) before a real rebuild would
fire. Reran, `tests.exe` regenerated correctly (13.9MB, fresh timestamp),
confirmed with `perf stat -r 20` matching the stock run's magnitude
(11.50s, 133.83B instructions -- sane).

Also hit a background-process footgun twice: passed a trailing `&` inside
a command that was ALSO marked `run_in_background: true`, double-backgrounding
it -- the tool's own tracking only saw the outer shell (which exited
immediately after printing a PID), while the actual `perf stat` kept running
fully detached and untracked. Caught it by `pgrep`-checking for the live
process, then waited on it properly with a single-level `while pgrep...;
do sleep 5; done` background command instead of stacking two backgrounding
mechanisms.

## Phase 2 -- perf stat -r 20, full counter set

Corrected event set per this hybrid CPU: `icache.accesses`/`icache.misses`
are `cpu_atom` (E-core) only and unusable while pinned to a P-core (cpu3);
used `cpu_core/frontend_retired.itlb_miss/` and
`cpu_core/frontend_retired.l1i_miss/` instead (P-core-native, still
directly test the icache/alignment theory).

Result (see `results.md` for the full table): wall +2.55%, cycles +2.96%,
instructions flat (+0.12%), IPC -2.75% -- but cache-misses -13.5%,
L1i-misses -8.6%, iTLB-misses -2.4%, branch-misses -1.7%. **Every**
memory-hierarchy/prediction counter decreased. This directly falsifies the
standing "icache-layout artifact" theory (which predicts MORE misses, not
fewer) -- something else is costing the cycles.

## Phase 3 -- topdown microarchitecture analysis

Tried `-M tma_frontend_bound,tma_retiring,...` together first -- multiple
metrics multiplexed onto the PMU in separate groups (50% duty cycle each,
confusing/approximate). Reran each metric group separately
(`-M tma_frontend_bound` alone, r=10, single group, no multiplexing) for
clean numbers:

Frontend Bound: 23.1% (stock) -> 26.0% (falign), +2.9pp / +12.6% relative.
Raw topdown-bad-spec actually *fell* -6.5% (matches branch-misses -1.7%);
topdown-retiring flat +0.3% (matches flat instruction count);
topdown-fe-bound rose the most in absolute terms, +15.0%.

This is the confirming data point: the CPU pipeline is measurably more
front-end/fetch-bound under falign, not backend/memory-bound and not
losing more to misprediction recovery. Textbook signature of a
fetch/decode-bandwidth cost from bloated code (the alignment padding
itself), not a cache-locality regression.

## Phase 4 -- flamegraph diff, and catching my own second mistake

First pass: raw `difffolded.pl -n` stack diff. Top mover looked alarming --
`[unknown];do_some_marking` apparently jumping from 0 to 3.95B weighted
samples, plus `[libc.so.6];do_some_marking` from 0 to 568M. Nearly took
this at face value as "GC marking regressed sharply under falign."

Checked before trusting it: summed `[unknown]`-touched weight in both
files. Stock: 5.02B. Falign: 8.91B (+77%). The `[unknown]` fraction nearly
doubled -- meaning DWARF unwind resolution itself got measurably worse on
the falign binary for a meaningful fraction of samples (plausible: the
padding bytes/alignment interacting with how the unwinder walks certain
frames). The naive "new do_some_marking cost" was largely this unwind
artifact eating into what should have been well-resolved stacks, not a
real new code path.

Redid the analysis as leaf-function (self-time) aggregation normalized to
fraction-of-total -- robust to unwind-depth/resolution differences between
the two binaries, since it doesn't care how deep or well-resolved the
*rest* of the stack above the leaf is. Clean picture: `do_some_marking`
(already 64.5% of runtime -- pplacer is GC-heavy) gains +1.05 percentage
points, but so does a long diffuse tail of unrelated functions
(`caml_shared_try_alloc`, `try_update_object_header`, `oldify_mopup`,
`caml_ba_slice`, GSL calls, OCaml stdlib `Lexing`/`Parsing`, `_int_malloc`,
...) each by a small amount. No single hot path stands out beyond its
existing share of the runtime -- exactly what a blanket per-function
code-size tax looks like, not a targeted regression.

## Conclusion

Mechanism confirmed, and it's different from what TASK 3/the earlier
falign report assumed: **front-end fetch/decode-bandwidth tax from
`-falign-functions=64`'s padding, not an icache-miss/layout-luck effect.**
All three lines of evidence agree (counters, topdown, leaf-function diff).
See `results.md` for the mitigation implications -- smaller alignment
values are now the best-supported fix (previously "landing luck" theory
predicted this wouldn't reliably help; the confirmed "raw padding volume"
mechanism predicts it should).

Wrote `report.html` (same design system as `../eio-deep-dive/report.html`)
and published as an artifact.
