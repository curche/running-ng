"""
Text table matching the merged heatmap: plain vs falign, per patch, vs
plain ocaml-5.5 baseline. Reuses plot_results.py's merge logic.

Usage:
    python3 make_final_table.py <falign_run_dir> <nonfalign_run_dir> <out_file>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from plot_results import merge_runs, median, BASELINE, RUNTIME_ORDER, RUNTIME_LABELS


def main():
    falign_dir = Path(sys.argv[1])
    nonfalign_dir = Path(sys.argv[2])
    out_file = Path(sys.argv[3])

    data = merge_runs(falign_dir, nonfalign_dir)
    comparisons = [r for r in RUNTIME_ORDER if r != BASELINE]

    lines = []
    lines.append("Full suite: plain vs falign, per patch, wall time (median of 3 invocations)")
    lines.append(f"falign run: {falign_dir.name}   non-falign run: {nonfalign_dir.name}")
    lines.append(f"baseline: {BASELINE} (plain stock) -- extracted directly from olly_*.json sidecars")
    lines.append("-- = build failed / did not run for that runtime")
    lines.append("")

    SHORT_LABELS = {
        "ocaml-5.5-falign":           "5.5-falign",
        "ocaml-auto-compact":         "auto-compact(plain)",
        "ocaml-auto-compact-falign":  "auto-compact(falign)",
        "socaml":                     "new-compactor(plain)",
        "socaml-falign":              "new-compactor(falign)",
        "socaml-auto-compact":        "new-compactor+ac(plain)",
        "socaml-auto-compact-falign": "new-compactor+ac(falign)",
    }
    COL_W = 24
    col_labels = [SHORT_LABELS[r] for r in comparisons]
    header = f"{'benchmark':<22}" + "".join(f"{l:>{COL_W}}" for l in col_labels)
    lines.append(header)
    lines.append("-" * len(header))

    for bm in sorted(data.keys()):
        base = median(data[bm].get(BASELINE, {}).get("wall_time", []))
        cells = []
        for rt in comparisons:
            vals = data[bm].get(rt, {}).get("wall_time")
            if vals is None:
                cells.append("--")
                continue
            m = median(vals)
            if m != m or base != base or base == 0:
                cells.append("nan")
            else:
                pct = (m / base - 1) * 100
                cells.append(f"{m:.2f}s ({pct:+.1f}%)")
        row = f"{bm:<22}" + "".join(f"{c:>{COL_W}}" for c in cells)
        lines.append(row)

    out_file.write_text("\n".join(lines) + "\n")
    print(f"wrote {out_file}")


if __name__ == "__main__":
    main()
