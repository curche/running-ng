#!/usr/bin/env bash
# Fold captured perf.data into flamegraphs + differential flamegraphs.
# Always uses perf script --no-inline (default inline resolver hangs on these
# binaries — Phase 0 finding).
#
# Subcommands:
#   fold  <bench> <runtime>              -> flamegraphs/<bench>__<rt>.folded (sum of reps) + .svg
#   diff  <bench> <rtA> <rtB>            -> diff flamegraph (rtB relative to rtA) + reverse
#   all   <bench> <rtA> <rtB> [rtC..]    -> fold each + diff each non-base vs rtA (base=first)
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
FG="$HERE/FlameGraph"
pd="$HERE/perf-data"; fg="$HERE/flamegraphs"
mkdir -p "$fg"

fold_cell() {
  local bench="$1" rt="$2" tag="${1}__${2}" out
  out="$fg/${tag}.folded"
  shopt -s nullglob
  local datas=( "$pd/${tag}".rep*.data )
  shopt -u nullglob
  [[ ${#datas[@]} -gt 0 ]] || { echo "!! no perf-data for $tag" >&2; return 1; }
  : > "$out"
  for d in "${datas[@]}"; do
    perf script --no-inline -i "$d" 2>/dev/null | "$FG/stackcollapse-perf.pl"
  done | awk '{c[substr($0,1,length($0)-length($NF)-1)]+=$NF} END{for(k in c)print k" "c[k]}' > "$out"
  local total; total=$(awk '{s+=$NF}END{print s}' "$out")
  "$FG/flamegraph.pl" --title "$tag" --subtitle "dwarf, sum of reps ($total samples-wt)" \
    --width 1600 --colors java "$out" > "$fg/${tag}.svg"
  echo "  folded $tag -> $(wc -l < "$out") stacks, ${total} wt; svg written"
}

diff_cells() {
  local bench="$1" a="$2" b="$3"
  local fa="$fg/${bench}__${a}.folded" fb="$fg/${bench}__${b}.folded"
  [[ -s "$fa" && -s "$fb" ]] || { echo "!! fold both cells first ($fa,$fb)" >&2; return 1; }
  # difffolded: colours by (b - a). Red = hotter in b (the slower/patched rt).
  "$FG/difffolded.pl" -n "$fa" "$fb" | \
    "$FG/flamegraph.pl" --title "${bench}: ${b} vs ${a} (red=more time in ${b})" \
      --width 1600 > "$fg/${bench}__DIFF__${b}_vs_${a}.svg"
  # negated view: fold b as base, so blue-on-a shows what got cheaper too
  "$FG/difffolded.pl" -n "$fb" "$fa" | \
    "$FG/flamegraph.pl" --title "${bench}: ${a} vs ${b} (red=more time in ${a})" \
      --width 1600 > "$fg/${bench}__DIFF__${a}_vs_${b}.svg"
  echo "  diff ${b} vs ${a} -> 2 svgs"
}

cmd="${1:?fold|diff|all}"; shift
case "$cmd" in
  fold) fold_cell "$@" ;;
  diff) diff_cells "$@" ;;
  all)
    bench="$1"; shift; base="$1"
    for rt in "$@"; do fold_cell "$bench" "$rt"; done
    for rt in "$@"; do [[ "$rt" == "$base" ]] || diff_cells "$bench" "$base" "$rt"; done
    ;;
  *) echo "unknown $cmd" >&2; exit 1 ;;
esac
