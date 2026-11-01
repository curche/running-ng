#!/usr/bin/env bash
# pplacer_testsuite falign deep-dive capture harness.
# Same pattern as ../eio-deep-dive/capture.sh: pinned + ASLR-off + repeated
# measurement, on-CPU perf record for flamegraphs, plus a `stat` mode with
# icache/iTLB/branch counters specifically to test the "code-alignment /
# icache-layout artifact" theory from ../compactor-comparison-falign/
# (which was inferred from wall-time deltas alone, never confirmed with
# hardware counters).
#
# Usage:
#   capture.sh oncpu <runtime> [reps=8]
#   capture.sh stat  <runtime> [reps=30]
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
MB=/home/curche/git/macro-benches
CORE=3
FREQ=999
OCAMLRUNPARAM="e=25,d=2"
BENCH=pplacer_testsuite
SUBDIR=pplacer
BARGS="5"

MODE="${1:?mode: oncpu|stat}"; RT="${2:?runtime}"
case "$MODE" in
  oncpu) REPS="${3:-8}" ;;
  stat)  REPS="${3:-30}" ;;
  *) echo "unknown mode $MODE" >&2; exit 2 ;;
esac

WRAP="${MB}/benchmarks/${SUBDIR}/${BENCH}-${RT}"
if [[ -x "$WRAP" ]]; then
  TARGET=("$WRAP" $BARGS)
else
  echo "!! no wrapper $WRAP for $RT" >&2; exit 2
fi

pd="$HERE/perf-data"; st="$HERE/stat"; lg="$HERE/logs"
mkdir -p "$pd" "$st" "$lg"
tag="${BENCH}__${RT}"
runenv=(env OCAMLRUNPARAM="$OCAMLRUNPARAM")

case "$MODE" in
  oncpu)
    echo "=== on-CPU capture $tag :: ${TARGET[*]} :: $REPS reps ==="
    for i in $(seq 1 "$REPS"); do
      "${runenv[@]}" taskset -c "$CORE" setarch -R \
        perf record -F "$FREQ" --call-graph dwarf,16384 -m 4 --all-user \
        -o "$pd/${tag}.rep${i}.data" -- "${TARGET[@]}" >"$lg/${tag}.oncpu.rep${i}.out" 2>&1
      echo "  rep$i: $(grep -oE '[0-9]+ samples' "$lg/${tag}.oncpu.rep${i}.out" | tail -1)"
    done
    ;;
  stat)
    echo "=== perf stat -r $REPS $tag :: ${TARGET[*]} ==="
    # frontend_retired.{itlb_miss,l1i_miss} directly test the icache/
    # alignment theory. These are cpu_core (P-core) native events -- this
    # hybrid CPU's icache.accesses/icache.misses are cpu_atom (E-core) only
    # and unusable while pinned to a P-core, hence not included (see
    # worklog.md). cache-misses/branch-misses as a general cross-check.
    "${runenv[@]}" taskset -c "$CORE" setarch -R \
      perf stat -r "$REPS" \
      -e task-clock,cycles,instructions,branches,branch-misses,cache-references,cache-misses,iTLB-load-misses,dTLB-load-misses,cpu_core/frontend_retired.itlb_miss/,cpu_core/frontend_retired.l1i_miss/ \
      -o "$st/${tag}.stat_r${REPS}.txt" \
      -- "${TARGET[@]}" >"$lg/${tag}.stat.out" 2>&1
    cat "$st/${tag}.stat_r${REPS}.txt"
    ;;
esac
echo "  done $tag ($MODE)"
