#!/usr/bin/env bash
# Record perf profiles of the fp-only pplacer_testsuite variants, convert to
# flamegraphs (Brendan Gregg's FlameGraph toolkit), and produce differential
# flamegraphs isolating each patch's marginal cost.
#
# Why the *-fp* variants specifically: normal OCaml native codegen omits
# frame pointers, so `perf record -g` on a stock build must fall back to
# slower/less-reliable DWARF unwinding (or misses OCaml frames entirely).
# The --enable-frame-pointers builds from the flambda/fp investigation
# (experiments/pplacer-gc-regression/plan-pplacer-gc-regression.md) let
# `perf record -g --call-graph fp` walk stacks cheaply and reliably straight
# through OCaml-compiled frames.
#
# Requires: perf (perf_event_paranoid <= 1 for no-sudo user profiling,
# confirmed -1 in this environment), and the FlameGraph toolkit at
# FLAMEGRAPH_DIR below (stackcollapse-perf.pl, flamegraph.pl, difffolded.pl).
#
# Usage: ./record_and_diff.sh [loop-count]
set -euo pipefail

FLAMEGRAPH_DIR="${FLAMEGRAPH_DIR:-/home/curche/git/FlameGraph}"
BENCH_DIR="${BENCH_DIR:-/home/curche/git/macro-benches/benchmarks/pplacer}"
OUT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OCAMLRUNPARAM_VAL="e=25,d=2"
LOOP="${1:-5}"
FREQ=997  # sampling frequency in Hz; non-round to avoid aliasing with periodic activity

RUNTIMES=(ocaml-5.5-fp ocaml-auto-compact-fp socaml-fp socaml-auto-compact-fp)

mkdir -p "$OUT_DIR/data" "$OUT_DIR/svg"

for rt in "${RUNTIMES[@]}"; do
  bin="$BENCH_DIR/pplacer_testsuite-$rt"
  if [[ ! -x "$bin" ]]; then
    echo "ERROR: $bin not found or not executable" >&2
    exit 1
  fi

  echo "=== recording $rt (loop=$LOOP) ==="
  OCAMLRUNPARAM="$OCAMLRUNPARAM_VAL" perf record -F "$FREQ" -g --call-graph fp \
    -o "$OUT_DIR/data/$rt.perf.data" -- "$bin" "$LOOP"

  echo "=== folding $rt ==="
  perf script -i "$OUT_DIR/data/$rt.perf.data" \
    | "$FLAMEGRAPH_DIR/stackcollapse-perf.pl" \
    > "$OUT_DIR/data/$rt.folded"

  echo "=== flamegraph $rt ==="
  "$FLAMEGRAPH_DIR/flamegraph.pl" --title "$rt (loop=$LOOP)" \
    "$OUT_DIR/data/$rt.folded" > "$OUT_DIR/svg/$rt.svg"
done

echo "=== differential flamegraphs vs ocaml-5.5-fp (stock) ==="
STOCK_FOLDED="$OUT_DIR/data/ocaml-5.5-fp.folded"
for rt in ocaml-auto-compact-fp socaml-fp socaml-auto-compact-fp; do
  "$FLAMEGRAPH_DIR/difffolded.pl" "$STOCK_FOLDED" "$OUT_DIR/data/$rt.folded" \
    | "$FLAMEGRAPH_DIR/flamegraph.pl" --title "$rt vs ocaml-5.5-fp (stock)" \
    > "$OUT_DIR/svg/diff-$rt-vs-stock.svg"
done

echo "=== differential: isolate the chunk allocator's marginal cost on top of auto-compact ==="
"$FLAMEGRAPH_DIR/difffolded.pl" \
  "$OUT_DIR/data/ocaml-auto-compact-fp.folded" "$OUT_DIR/data/socaml-auto-compact-fp.folded" \
  | "$FLAMEGRAPH_DIR/flamegraph.pl" --title "socaml-auto-compact-fp vs ocaml-auto-compact-fp" \
  > "$OUT_DIR/svg/diff-socaml-auto-compact-fp-vs-ocaml-auto-compact-fp.svg"

echo "=== differential: isolate auto-compact's marginal cost on top of the chunk allocator ==="
"$FLAMEGRAPH_DIR/difffolded.pl" \
  "$OUT_DIR/data/socaml-fp.folded" "$OUT_DIR/data/socaml-auto-compact-fp.folded" \
  | "$FLAMEGRAPH_DIR/flamegraph.pl" --title "socaml-auto-compact-fp vs socaml-fp" \
  > "$OUT_DIR/svg/diff-socaml-auto-compact-fp-vs-socaml-fp.svg"

echo "Done. SVGs in $OUT_DIR/svg/"
