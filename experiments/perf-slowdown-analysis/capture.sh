#!/usr/bin/env bash
# TASK 2 perf capture harness.
# Runs one benchmark on one runtime under: (a) perf record (dwarf call-graph,
# for flamegraphs), (b) perf stat (hardware counters), (c) optional strace -c
# (syscall counts). Direct-exec of the per-runtime .exe — bypasses running-ng
# for profiling, reusing the exact args from macro_base.yml.
#
# Usage: capture.sh <bench> <runtime> [reps] [strace:0|1]
#   <bench>   : owl_gc | zarith_pi | pplacer_testsuite | eio_fiber_stream |
#               ocamlc_self_compile | test_decompress | cpdf_squeeze |
#               liq_video_frames_pool | ...
#   <runtime> : ocaml-5.5 | ocaml-auto-compact | socaml | socaml-auto-compact
#
# Methodology (validated Phase 0): dwarf,16384 (FP breaks at OCaml/C boundary);
# --all-user (kernel syms restricted by kptr_restrict=1; kernel cost captured
# via perf stat instead); perf script always run with --no-inline downstream
# (the default DWARF inline resolver hangs pathologically on these 31MB
# not-stripped binaries). taskset+setarch -R for stability. OCAMLRUNPARAM
# matches the 4-way baseline (re-25|md-2 -> e=25,d=2; inert without olly).
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
MB=/home/curche/git/macro-benches
CORE=3
FREQ=999
OCAMLRUNPARAM="e=25,d=2"

BENCH="${1:?bench}"; RT="${2:?runtime}"; REPS="${3:-3}"; DOSTRACE="${4:-0}"

# --- per-benchmark: build-subdir, exe name, args, extra env -----------------
declare -A SUBDIR EXE ARGS ENV
SUBDIR[owl_gc]=owl;                 EXE[owl_gc]=owl_gc.exe;                 ARGS[owl_gc]="6";                              ENV[owl_gc]="OWL_MATRIX_DIM=100"
SUBDIR[zarith_pi]=zarith;          EXE[zarith_pi]=zarith_pi.exe;           ARGS[zarith_pi]="15000";                       ENV[zarith_pi]=""
SUBDIR[pplacer_testsuite]=pplacer; EXE[pplacer_testsuite]=pplacer_testsuite.exe; ARGS[pplacer_testsuite]="5";             ENV[pplacer_testsuite]=""
SUBDIR[eio_fiber_stream]=eio;      EXE[eio_fiber_stream]=eio_fiber_stream.exe; ARGS[eio_fiber_stream]="";                 ENV[eio_fiber_stream]=""
SUBDIR[ocamlc_self_compile]=ocamlc-self-compile; EXE[ocamlc_self_compile]=""; ARGS[ocamlc_self_compile]="";              ENV[ocamlc_self_compile]=""
SUBDIR[test_decompress]=decompress; EXE[test_decompress]=test_decompress.exe; ARGS[test_decompress]="64 524288";         ENV[test_decompress]=""
SUBDIR[cpdf_squeeze]=cpdf;         EXE[cpdf_squeeze]=cpdf.exe;             ARGS[cpdf_squeeze]="-squeeze ${MB}/benchmarks/cpdf/PDFReference16.pdf_toobig -o /dev/null"; ENV[cpdf_squeeze]=""
SUBDIR[liq_video_frames_pool]=liq-video-frames; EXE[liq_video_frames_pool]=liq_video_frames_pool.exe; ARGS[liq_video_frames_pool]="30000"; ENV[liq_video_frames_pool]=""

sd="${SUBDIR[$BENCH]:?unknown bench $BENCH}"
exe="${EXE[$BENCH]}"
bargs="${ARGS[$BENCH]}"
benv="${ENV[$BENCH]}"

# Prefer the per-runtime wrapper if present (handles special exes like
# ocamlc-self-compile / cpdf whose real path/env is non-trivial); else the exe.
WRAP="${MB}/benchmarks/${sd}/${BENCH}-${RT}"
REAL="${MB}/_build-${RT}/default/benchmarks/${sd}/${exe}"
if [[ -x "$WRAP" ]]; then
  TARGET=("$WRAP" $bargs)
elif [[ -n "$exe" && -f "$REAL" ]]; then
  TARGET=("$REAL" $bargs)
else
  echo "!! no wrapper ($WRAP) and no exe ($REAL) for $BENCH/$RT" >&2; exit 2
fi

pd="$HERE/perf-data"; st="$HERE/stat"; str="$HERE/strace"; lg="$HERE/logs"
mkdir -p "$pd" "$st" "$str" "$lg"
tag="${BENCH}__${RT}"
echo "=== capture $tag :: ${TARGET[*]} :: env=[$benv $OCAMLRUNPARAM] ==="

runenv=(env OCAMLRUNPARAM="$OCAMLRUNPARAM")
[[ -n "$benv" ]] && runenv+=($benv)

# (a) perf record — REPS reps
for i in $(seq 1 "$REPS"); do
  "${runenv[@]}" taskset -c "$CORE" setarch -R \
    perf record -F "$FREQ" --call-graph dwarf,16384 --all-user \
    -o "$pd/${tag}.rep${i}.data" -- "${TARGET[@]}" >"$lg/${tag}.rep${i}.out" 2>&1
  echo "  rep$i: $(grep -oE '[0-9]+ samples' "$lg/${tag}.rep${i}.out" | tail -1)"
done

# (b) perf stat — one clean run, rich counter set
"${runenv[@]}" taskset -c "$CORE" \
  perf stat -o "$st/${tag}.stat.txt" \
  -e task-clock,cycles,instructions,page-faults,minor-faults,major-faults,cache-references,cache-misses,dTLB-load-misses,context-switches \
  -- "${TARGET[@]}" >"$lg/${tag}.stat.out" 2>&1
echo "  stat: $(grep -E 'seconds time elapsed' "$st/${tag}.stat.txt" | awk '{print $1"s"}')"

# (c) strace -c syscall summary (memory syscalls of interest surface here)
if [[ "$DOSTRACE" == "1" ]]; then
  "${runenv[@]}" taskset -c "$CORE" \
    strace -f -c -o "$str/${tag}.strace.txt" -- "${TARGET[@]}" >"$lg/${tag}.strace.out" 2>&1
  echo "  strace: mmap=$(grep -E ' mmap' "$str/${tag}.strace.txt" | awk '{print $4}' | head -1) munmap=$(grep -E ' munmap' "$str/${tag}.strace.txt" | awk '{print $4}' | head -1)"
fi
echo "  done $tag"
