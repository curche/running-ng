#!/usr/bin/env bash
# Rigorous pinned perf stat + topdown check for pplacer_testsuite across all
# 4 alignment values, mirroring ../pplacer-falign-deep-dive/'s methodology.
# Directly tests the mitigation prediction: does a smaller -falign-functions
# value reduce the Frontend Bound tax?
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
MB=/home/curche/git/macro-benches
CORE=3
OCAMLRUNPARAM="e=25,d=2"
BARGS="5"
REPS="${1:-20}"

st="$HERE/stat"; lg="$HERE/logs"
mkdir -p "$st" "$lg"

for RT in ocaml-5.5 ocaml-5.5-falign16 ocaml-5.5-falign32 ocaml-5.5-falign; do
  WRAP="${MB}/benchmarks/pplacer/pplacer_testsuite-${RT}"
  if [[ ! -x "$WRAP" ]]; then
    echo "!! no wrapper $WRAP for $RT -- run 'make run' first" >&2
    exit 2
  fi
  tag="pplacer_testsuite__${RT}"

  echo "=== perf stat -r $REPS $tag (full counter set) ==="
  env OCAMLRUNPARAM="$OCAMLRUNPARAM" taskset -c "$CORE" setarch -R \
    perf stat -r "$REPS" \
    -e task-clock,cycles,instructions,branches,branch-misses,cache-references,cache-misses,iTLB-load-misses,dTLB-load-misses,cpu_core/frontend_retired.itlb_miss/,cpu_core/frontend_retired.l1i_miss/ \
    -o "$st/${tag}.stat_r${REPS}.txt" \
    -- "$WRAP" $BARGS >"$lg/${tag}.stat.out" 2>&1
  cat "$st/${tag}.stat_r${REPS}.txt"

  echo "=== topdown frontend-bound, r=10, single metric group ==="
  env OCAMLRUNPARAM="$OCAMLRUNPARAM" taskset -c "$CORE" setarch -R \
    perf stat -r 10 -M tma_frontend_bound \
    -o "$st/${tag}.topdown.txt" \
    -- "$WRAP" $BARGS >"$lg/${tag}.topdown.out" 2>&1
  cat "$st/${tag}.topdown.txt"
  echo
done
