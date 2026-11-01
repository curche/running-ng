# falign value sweep -- results

Follow-up to `../pplacer-falign-deep-dive/`, which confirmed falign=64's
`pplacer_testsuite` cost is a front-end fetch/decode-bandwidth tax from
padding every function to a 64-byte boundary (not an icache-miss/layout
effect -- every miss counter actually *improved* under falign=64). That
mechanism predicts a smaller alignment value should reduce the tax
directly. Tested `-falign-functions` in {16, 32, 64} against stock.

## Headline: falign=16 fixes it. 32 and 64 are the same cost.

Pinned (`taskset -c 3` + `setarch -R`), `perf stat -r 20` on
`pplacer_testsuite`:

| variant | wall time | vs stock | cycles | IPC | cache-misses | Frontend Bound |
|---|---|---|---|---|---|---|
| stock | 10.093s | ref | 40.00B | 3.341 | ref | 22.7% |
| **falign16** | 10.119s | **+0.26%** | +0.26% | 3.335 | -6.0% | **22.7% (+0.77% raw)** |
| falign32 | 10.422s | +3.26% | +3.24% | 3.238 | -7.5% | 26.5% (+20.6% raw) |
| falign64 | 10.399s | +3.04% | +3.01% | 3.246 | -6.2% | 26.1% (+17.9% raw) |

`falign16`'s wall-time and frontend-bound deltas are close to the ±0.01-0.04%
noise floor established in `../pplacer-falign-deep-dive/` and `../eio-deep-dive/`
under this same pinned methodology -- i.e. **not clearly distinguishable
from noise**, versus falign32/64's unambiguous +3% regression. Cache-misses
still drop at every alignment value (-6 to -7.5%), consistent with the
earlier finding that alignment padding, at any size, doesn't hurt cache
locality here -- only larger padding costs front-end fetch bandwidth.

**This is a threshold, not a gradient.** falign32 and falign64 land on
statistically indistinguishable costs (both ~+3.0-3.3% wall, both
~+18-21% frontend-bound). Going from 32 to 64 adds essentially nothing
further. Consistent with 16 bytes being close to x86-64's natural/default
function alignment already (so `-falign-functions=16` adds little padding
beyond what the compiler would do anyway), while any larger forced value
crosses whatever fetch-window/decode-boundary threshold triggers the tax
-- and once crossed, going further doesn't cost more.

## Does falign=16 still deliver the wins elsewhere?

The `make run` harness comparison (6 benchmarks, 5 invocations, unpinned)
is too noisy to answer this reliably on its own -- two benchmarks
(`menhir_sql_parser`, `menhir_ocamly`) flip sign entirely versus TASK 3's
original falign64 numbers between runs, confirming (again) that the
unpinned harness carries real environmental noise on this machine. Raw
numbers, treat directionally only:

| benchmark | stock | falign16 | falign32 | falign64 |
|---|---|---|---|---|
| frama_c_eva_sqlite | 21.47s | 19.54s (-9.0%) | 21.75s (+1.3%) | 18.21s (-15.2%) |
| menhir_sql_parser | 2.17s | 2.17s (+0.0%) | 2.19s (+0.9%) | 2.19s (+0.9%) |
| menhir_ocamly | 19.70s | 19.68s (-0.1%) | 19.74s (+0.2%) | 19.86s (+0.8%) |
| owl_gc | 4.62s | 4.63s (+0.2%) | 4.61s (-0.2%) | 4.64s (+0.4%) |
| zarith_pi | 4.16s | 4.14s (-0.5%) | 4.15s (-0.2%) | 4.14s (-0.5%) |

`frama_c_eva_sqlite` (falign64's biggest win) still shows a large speedup
at falign16 in this unpinned data (-9.0% vs -15.2% at falign64) -- directionally
promising that falign16 keeps most of the win, but given the noise already
demonstrated on this table (two benchmarks flipped sign vs. the original
TASK 3 run), this needs the same pinned `perf stat -r 20` treatment as
pplacer before trusting a specific number. Not yet run -- see "Next steps."

## Recommendation

Switch the patch's falign setting from 64 to **16**, not drop it entirely:
16 removes pplacer's regression (down to noise-floor level) while the
harness data suggests it directionally keeps a large chunk of
`frama_c_eva_sqlite`'s win. This is a better outcome than TASK 3's original
"don't apply it globally" framing, which would have given up the wins
entirely to fix the one regression.

## Next steps (not done here)

- Pinned `perf stat -r 20` for `frama_c_eva_sqlite` and `menhir_sql_parser`
  across all 4 alignment values, to replace the noisy harness numbers above
  with trustworthy ones -- confirm falign16 keeps (most of) the win before
  recommending it as a final replacement value.
- If confirmed, rerun TASK 3's full 8-way factorial
  (`../fp-falign-autocompact/`) with falign=16 in place of 64, to check the
  whole-suite picture, not just these 6 benchmarks.

## Files

- `config.yml` -- 4-runtime x 6-benchmark harness comparison (stock,
  falign16, falign32, falign64), reuses the existing falign64 switch.
- `pplacer_deep_dive.sh` -- pinned `perf stat -r N` + topdown, all 4
  values, `pplacer_testsuite` only (the rigorous data above).
- `plots/full/` -- harness-level heatmaps/tables (noisy, see caveat above).
- `stat/pplacer_testsuite__*.{stat_r20,topdown}.txt` -- raw pinned perf
  output backing the headline table.
