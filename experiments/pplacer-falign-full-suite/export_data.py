"""
Dump merged falign + non-falign run data as JSON for the interactive
HTML comparison table.

Usage:
    python3 export_data.py <falign_run_dir> <nonfalign_run_dir> <out.json>
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from plot_results import merge_runs, median, RUNTIME_ORDER, RUNTIME_LABELS


def main():
    falign_dir = Path(sys.argv[1])
    nonfalign_dir = Path(sys.argv[2])
    out_path = Path(sys.argv[3])

    data = merge_runs(falign_dir, nonfalign_dir)

    out = {
        "runtimes": RUNTIME_ORDER,
        "labels": {r: RUNTIME_LABELS[r].replace("\n", " ") for r in RUNTIME_ORDER},
        "benchmarks": {},
    }
    for bm in sorted(data.keys()):
        row = {}
        for rt in RUNTIME_ORDER:
            metrics = data[bm].get(rt)
            if metrics is None:
                row[rt] = None
                continue
            wt = median(metrics.get("wall_time", []))
            rss = median(metrics.get("max_rss_mb", []))
            gc = median(metrics.get("gc_overhead", []))
            comp = median(metrics.get("compactions", [0]))
            row[rt] = {
                "wall_time": wt if wt == wt else None,
                "max_rss_mb": rss if rss == rss else None,
                "gc_overhead": gc if gc == gc else None,
                "compactions": comp if comp == comp else 0,
            }
        out["benchmarks"][bm] = row

    out_path.write_text(json.dumps(out, indent=None, separators=(",", ":")))
    print(f"wrote {out_path} ({len(data)} benchmarks)")


if __name__ == "__main__":
    main()
