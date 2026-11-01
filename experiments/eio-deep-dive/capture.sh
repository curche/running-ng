#!/usr/bin/env bash
# eio_fiber_stream deep-dive capture harness.
# Adapted from ../perf-slowdown-analysis/capture.sh (TASK 2), specialized to
# eio_fiber_stream with: (a) more reps by default (noise reduction), (b) an
# added off-CPU capture mode via `perf sched record` (Brendan Gregg's
# https://www.brendangregg.com/offcpuanalysis.html method), (c) a `stat`
# mode using `perf stat -r N` for built-in mean+stddev noise quantification.
# Reuses the vendored FlameGraph at ../perf-slowdown-analysis/FlameGraph
# (not re-vendored here).
#
# Usage:
#   capture.sh oncpu  <runtime> [reps=15]   -- perf record dwarf, for flamegraphs
#   capture.sh offcpu <runtime> [reps=5]    -- perf sched record, needs root
#                                               (sudo mount -o remount,mode=755
#                                               /sys/kernel/tracing/ first)
#   capture.sh stat   <runtime> [reps=30]   -- perf stat -r N, mean+stddev
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
MB=/home/curche/git/macro-benches
CORE=3          # a P-core (has an SMT sibling: cpu2/cpu3 pair) on this 14700
FREQ=999
OCAMLRUNPARAM="e=25,d=2"
BENCH=eio_fiber_stream
SUBDIR=eio
EXE=eio_fiber_stream.exe

MODE="${1:?mode: oncpu|offcpu|stat}"; RT="${2:?runtime}"
case "$MODE" in
  oncpu)  REPS="${3:-15}" ;;
  offcpu) REPS="${3:-5}" ;;
  stat)   REPS="${3:-30}" ;;
  *) echo "unknown mode $MODE" >&2; exit 2 ;;
esac

WRAP="${MB}/benchmarks/${SUBDIR}/${BENCH}-${RT}"
REAL="${MB}/_build-${RT}/default/benchmarks/${SUBDIR}/${EXE}"
if [[ -x "$WRAP" ]]; then
  TARGET=("$WRAP")
elif [[ -f "$REAL" ]]; then
  TARGET=("$REAL")
else
  echo "!! no wrapper ($WRAP) and no exe ($REAL) for $RT" >&2; exit 2
fi

pd="$HERE/perf-data"; pdo="$HERE/perf-data-offcpu"; st="$HERE/stat"; lg="$HERE/logs"
mkdir -p "$pd" "$pdo" "$st" "$lg"
tag="${BENCH}__${RT}"
runenv=(env OCAMLRUNPARAM="$OCAMLRUNPARAM")

case "$MODE" in
  oncpu)
    echo "=== on-CPU capture $tag :: ${TARGET[*]} :: $REPS reps ==="
    # -m 4 (small mmap ring buffer): perf record's DEFAULT ring buffer size
    # blows RLIMIT_MEMLOCK (8MB, hard-capped, no sudo available to raise it)
    # when combined with the benchmark's own io_uring_queue_init mlock
    # request, crashing the process with ENOMEM before it does any work.
    # -m 4 shrinks perf's own footprint well under the cap; confirmed this
    # is what was tripping it (not the dwarf stack size -- dwarf,1024 with
    # default -m still crashed; fp-unwind and no-callgraph also still
    # crashed with default -m). See worklog.md.
    for i in $(seq 1 "$REPS"); do
      "${runenv[@]}" taskset -c "$CORE" setarch -R \
        perf record -F "$FREQ" --call-graph dwarf,16384 -m 4 --all-user \
        -o "$pd/${tag}.rep${i}.data" -- "${TARGET[@]}" >"$lg/${tag}.oncpu.rep${i}.out" 2>&1
      echo "  rep$i: $(grep -oE '[0-9]+ samples' "$lg/${tag}.oncpu.rep${i}.out" | tail -1)"
    done
    ;;
  offcpu)
    echo "=== off-CPU capture $tag :: ${TARGET[*]} :: $REPS reps ==="
    echo "    (requires: sudo mount -o remount,mode=755 /sys/kernel/tracing/)"
    for i in $(seq 1 "$REPS"); do
      "${runenv[@]}" taskset -c "$CORE" setarch -R \
        perf sched record -m 4 --call-graph dwarf,16384 \
        -o "$pdo/${tag}.rep${i}.data" -- "${TARGET[@]}" >"$lg/${tag}.offcpu.rep${i}.out" 2>&1
      echo "  rep$i: $(tail -3 "$lg/${tag}.offcpu.rep${i}.out" | tr '\n' ' ')"
    done
    ;;
  stat)
    echo "=== perf stat -r $REPS $tag :: ${TARGET[*]} ==="
    "${runenv[@]}" taskset -c "$CORE" setarch -R \
      perf stat -r "$REPS" \
      -e task-clock,cycles,instructions,page-faults,context-switches,cpu-migrations,cache-misses \
      -o "$st/${tag}.stat_r${REPS}.txt" \
      -- "${TARGET[@]}" >"$lg/${tag}.stat.out" 2>&1
    cat "$st/${tag}.stat_r${REPS}.txt"
    ;;
esac
echo "  done $tag ($MODE)"
