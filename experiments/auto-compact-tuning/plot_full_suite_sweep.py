"""
Plot benchmark x O= heatmaps for the full-suite O= sweep
(Phase 9 of the auto-compact-tuning investigation).

Reads the olly_gc_stats sidecar JSON produced by running-ng for each
(benchmark, O=value) cell, takes the median across invocations, and
renders three heatmaps:
  - heatmap_wall_time_ratio.png : wall time relative to that benchmark's
    own O=600 (the leftmost point in this sweep, not the compiled-in
    O=500 default -- O=500 wasn't part of this sweep)
  - heatmap_gc_overhead_pct.png : raw GC overhead %% (olly's gc_overhead
    field, i.e. gc_time / wall_time * 100) per cell
  - heatmap_compactions.png     : raw compaction count per cell

Usage:
    python3 plot_full_suite_sweep.py <run_dir> <output_dir>
"""

import json
import re
import sys
from pathlib import Path
from collections import defaultdict

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

O_VALUES = [600, 700, 800, 900, 1000]

SIDECAR_RE = re.compile(
    r"^olly_(?P<bench>.+?)\.\d+\.\d+\."
    r"(?P<runtime>[^.]+)\.perf_grp\d+\.re-\d+\.md-\d+\.O-(?P<O>\d+)\."
    r"macro-[a-zA-Z0-9_\-]+\.json$"
)


def load_run(run_dir: Path) -> dict:
    """Return {bench: {O: {"wall_time": [...], "gc_overhead": [...],
    "max_rss_mb": [...], "compactions": [...]}}}."""
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for path in sorted(run_dir.glob("olly_*.json")):
        m = SIDECAR_RE.match(path.name)
        if not m:
            continue
        bench = m.group("bench")
        o_val = int(m.group("O"))
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            cell = data[bench][o_val]
            cell["wall_time"].append(rec.get("wall_time", float("nan")))
            cell["gc_overhead"].append(rec.get("gc_overhead", float("nan")))
            cell["max_rss_mb"].append(rec.get("max_rss_kb", float("nan")) / 1024.0)
            cell["compactions"].append(
                rec.get("collections", {}).get("compactions", float("nan"))
            )
    return data


def median(vals):
    clean = [v for v in vals if v == v]
    return float(np.median(clean)) if clean else float("nan")


def benches_sorted_by(data, metric, o_ref=600):
    """Sort benchmarks descending by their value at o_ref, NaNs last."""
    def key(b):
        v = median(data[b].get(o_ref, {}).get(metric, []))
        return (-1.0 if v == v else float("-inf"), 0 if v == v else 1)
    return sorted(data.keys(), key=lambda b: key(b), reverse=False)


def plot_ratio_heatmap(data, benches, metric, title, cbar_label, output_path,
                        vrange=0.30):
    grid = np.full((len(benches), len(O_VALUES)), np.nan)
    for i, b in enumerate(benches):
        baseline = median(data[b].get(O_VALUES[0], {}).get(metric, []))
        for j, o in enumerate(O_VALUES):
            v = median(data[b].get(o, {}).get(metric, []))
            if v == v and baseline == baseline and baseline != 0:
                grid[i, j] = v / baseline

    fig, ax = plt.subplots(figsize=(6, 0.32 * len(benches) + 1.5))
    cmap = plt.cm.RdYlGn_r
    vmin, vmax = 1 - vrange, 1 + vrange
    im = ax.imshow(grid, aspect="auto", cmap=cmap, vmin=vmin, vmax=vmax)

    ax.set_xticks(range(len(O_VALUES)))
    ax.set_xticklabels([f"O={o}" for o in O_VALUES], fontsize=9)
    ax.set_yticks(range(len(benches)))
    ax.set_yticklabels(benches, fontsize=8)
    ax.set_title(title, fontsize=11, pad=10)

    for i in range(len(benches)):
        for j in range(len(O_VALUES)):
            v = grid[i, j]
            if v == v:
                pct = (v - 1) * 100
                txt = f"{pct:+.1f}%"
                color = "black" if 0.97 < v < 1.03 else "white"
                ax.text(j, i, txt, ha="center", va="center", fontsize=7, color=color)
            else:
                ax.text(j, i, "—", ha="center", va="center", fontsize=7, color="gray")

    cbar = fig.colorbar(im, ax=ax, shrink=0.6)
    cbar.set_label(cbar_label, fontsize=9)
    cbar.ax.tick_params(labelsize=8)
    ax.set_xlabel("OCAMLRUNPARAM O= (ocaml-auto-compact)", fontsize=9)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {output_path}")


def plot_raw_heatmap(data, benches, metric, title, cbar_label, output_path,
                      fmt="{:.1f}", cmap=None, log=False):
    grid = np.full((len(benches), len(O_VALUES)), np.nan)
    for i, b in enumerate(benches):
        for j, o in enumerate(O_VALUES):
            v = median(data[b].get(o, {}).get(metric, []))
            grid[i, j] = v

    fig, ax = plt.subplots(figsize=(6, 0.32 * len(benches) + 1.5))
    cmap = cmap or plt.cm.YlOrRd
    plot_grid = np.log10(grid + 1) if log else grid
    im = ax.imshow(plot_grid, aspect="auto", cmap=cmap)

    ax.set_xticks(range(len(O_VALUES)))
    ax.set_xticklabels([f"O={o}" for o in O_VALUES], fontsize=9)
    ax.set_yticks(range(len(benches)))
    ax.set_yticklabels(benches, fontsize=8)
    ax.set_title(title, fontsize=11, pad=10)

    for i in range(len(benches)):
        for j in range(len(O_VALUES)):
            v = grid[i, j]
            if v == v:
                txt = fmt.format(v)
                ax.text(j, i, txt, ha="center", va="center", fontsize=7, color="black")
            else:
                ax.text(j, i, "—", ha="center", va="center", fontsize=7, color="gray")

    cbar = fig.colorbar(im, ax=ax, shrink=0.6)
    cbar.set_label(cbar_label, fontsize=9)
    cbar.ax.tick_params(labelsize=8)
    ax.set_xlabel("OCAMLRUNPARAM O= (ocaml-auto-compact)", fontsize=9)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {output_path}")


def print_table(data, benches):
    print(f"\n{'benchmark':<24}" + "".join(f"{'O='+str(o):>12}" for o in O_VALUES))
    for b in benches:
        row = f"{b:<24}"
        for o in O_VALUES:
            wt = median(data[b].get(o, {}).get("wall_time", []))
            row += f"{wt:>12.2f}" if wt == wt else f"{'--':>12}"
        print(row)


def write_summary_txt(data, benches, output_path):
    """Per-O= summary across benchmarks: average, median, and range (min-max)
    of wall_time ratio (vs. each benchmark's own O=600), plus raw
    gc_overhead %% and compaction count, all computed across the benchmark
    set for each O= column."""
    lines = []
    lines.append("Full-suite O= sweep -- cross-benchmark summary statistics")
    lines.append("=" * 70)
    lines.append("")
    lines.append(
        "wall_time ratio vs. that benchmark's own O=600 "
        "(average / median / range across benchmarks):"
    )
    lines.append(f"{'O=':<10}{'avg':>10}{'median':>10}{'min':>10}{'max':>10}{'range':>10}")
    for o in O_VALUES:
        ratios = []
        for b in benches:
            baseline = median(data[b].get(O_VALUES[0], {}).get("wall_time", []))
            v = median(data[b].get(o, {}).get("wall_time", []))
            if v == v and baseline == baseline and baseline != 0:
                ratios.append(v / baseline)
        if ratios:
            avg, med = np.mean(ratios), np.median(ratios)
            lo, hi = min(ratios), max(ratios)
            lines.append(
                f"O={o:<8}{avg:>9.3f}x{med:>9.3f}x{lo:>9.3f}x{hi:>9.3f}x{hi - lo:>9.3f}x"
            )
    lines.append("")
    for metric, label, fmt in [
        ("gc_overhead", "gc_overhead %% (raw, across benchmarks)", "{:.1f}%"),
        ("compactions", "compactions (raw, across benchmarks)", "{:.0f}"),
        ("max_rss_mb", "max RSS MB (raw, across benchmarks)", "{:.0f}"),
    ]:
        lines.append(f"{label}:")
        lines.append(f"{'O=':<10}{'avg':>10}{'median':>10}{'min':>10}{'max':>10}{'range':>10}")
        for o in O_VALUES:
            vals = [median(data[b].get(o, {}).get(metric, [])) for b in benches]
            vals = [v for v in vals if v == v]
            if vals:
                avg, med = np.mean(vals), np.median(vals)
                lo, hi = min(vals), max(vals)
                cells = "".join(f"{fmt.format(x):>10}" for x in [avg, med, lo, hi, hi - lo])
                lines.append(f"O={o:<8}{cells}")
        lines.append("")

    text = "\n".join(lines) + "\n"
    output_path.write_text(text)
    print(f"  saved {output_path}")
    print(text)


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    run_dir = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    output_dir.mkdir(parents=True, exist_ok=True)

    data = load_run(run_dir)
    benches = sorted(data.keys())
    print(f"Loaded {len(benches)} benchmarks from {run_dir}: {benches}")

    print_table(data, benches)
    write_summary_txt(data, benches, output_dir / "summary_stats.txt")

    plot_ratio_heatmap(
        data, benches, "wall_time",
        "Full suite: wall time vs. that benchmark's own O=600",
        "wall time ratio vs. O=600",
        output_dir / "heatmap_wall_time_ratio.png",
        vrange=0.30,
    )
    plot_raw_heatmap(
        data, benches, "gc_overhead",
        "Full suite: GC overhead %% (gc_time / wall_time)",
        "gc_overhead %%",
        output_dir / "heatmap_gc_overhead_pct.png",
        fmt="{:.1f}%",
        cmap=plt.cm.YlOrRd,
    )
    plot_raw_heatmap(
        data, benches, "compactions",
        "Full suite: compaction count per invocation",
        "compactions (log10(n+1) color scale)",
        output_dir / "heatmap_compactions.png",
        fmt="{:.0f}",
        cmap=plt.cm.YlOrRd,
        log=True,
    )
    plot_raw_heatmap(
        data, benches, "max_rss_mb",
        "Full suite: max RSS (MB)",
        "max RSS (MB, log10 color scale)",
        output_dir / "heatmap_max_rss_mb.png",
        fmt="{:.0f}",
        cmap=plt.cm.YlOrRd,
        log=True,
    )


if __name__ == "__main__":
    main()
