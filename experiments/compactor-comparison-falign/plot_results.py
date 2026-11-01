"""
Plot benchmark x runtime heatmaps for a 4-way (or N-way) compactor
comparison run: stock vs. auto-compact vs. socaml vs. socaml-auto-compact
(and, for the falign variant, the same crossed with -falign builds).

Reads the olly_gc_stats sidecar JSON produced by running-ng for each
(benchmark, runtime) cell, takes the median across invocations, and
renders four heatmaps:
  - heatmap_wall_time_ratio.png : wall time relative to the first runtime
    in --runtimes (the baseline column, e.g. "ocaml-5.5")
  - heatmap_max_rss_ratio.png   : max RSS relative to the same baseline
  - heatmap_gc_overhead_pct.png : raw GC overhead %% (gc_time / wall_time)
  - heatmap_compactions.png     : raw compaction count (log-color-scaled)

Usage:
    python3 plot_results.py <run_dir> <output_dir> <runtime1,runtime2,...>

The first runtime in the comma-separated list is the ratio baseline.
Runtime names must match the `.<runtime>.` component of the log/sidecar
filenames exactly (as configured in the experiment's YAML `runtimes:`).
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


def make_sidecar_re(runtimes):
    alts = "|".join(re.escape(r) for r in sorted(runtimes, key=len, reverse=True))
    return re.compile(
        r"^olly_(?P<bench>.+?)\.\d+\.\d+\."
        rf"(?P<runtime>{alts})\.perf_grp\d+\.re-\d+\.md-\d+\."
        r"macro-[a-zA-Z0-9_\-]+\.json$"
    )


def load_run(run_dir: Path, runtimes) -> dict:
    """Return {bench: {runtime: {"wall_time": [...], "gc_overhead": [...],
    "max_rss_mb": [...], "compactions": [...]}}}."""
    sidecar_re = make_sidecar_re(runtimes)
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for path in sorted(run_dir.glob("olly_*.json")):
        m = sidecar_re.match(path.name)
        if not m:
            continue
        bench = m.group("bench")
        rt = m.group("runtime")
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            cell = data[bench][rt]
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


def plot_ratio_heatmap(data, benches, runtimes, baseline_rt, metric, title,
                        cbar_label, output_path, vrange=0.30):
    grid = np.full((len(benches), len(runtimes)), np.nan)
    for i, b in enumerate(benches):
        baseline = median(data[b].get(baseline_rt, {}).get(metric, []))
        for j, rt in enumerate(runtimes):
            v = median(data[b].get(rt, {}).get(metric, []))
            if v == v and baseline == baseline and baseline != 0:
                grid[i, j] = v / baseline

    fig, ax = plt.subplots(figsize=(1.6 * len(runtimes) + 2, 0.32 * len(benches) + 1.5))
    cmap = plt.cm.RdYlGn_r
    vmin, vmax = 1 - vrange, 1 + vrange
    im = ax.imshow(grid, aspect="auto", cmap=cmap, vmin=vmin, vmax=vmax)

    ax.set_xticks(range(len(runtimes)))
    ax.set_xticklabels(runtimes, fontsize=9, rotation=25, ha="right")
    ax.set_yticks(range(len(benches)))
    ax.set_yticklabels(benches, fontsize=8)
    ax.set_title(title, fontsize=11, pad=10)

    for i in range(len(benches)):
        for j in range(len(runtimes)):
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

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {output_path}")


def plot_raw_heatmap(data, benches, runtimes, metric, title, cbar_label,
                      output_path, fmt="{:.1f}", cmap=None, log=False):
    grid = np.full((len(benches), len(runtimes)), np.nan)
    for i, b in enumerate(benches):
        for j, rt in enumerate(runtimes):
            grid[i, j] = median(data[b].get(rt, {}).get(metric, []))

    fig, ax = plt.subplots(figsize=(1.6 * len(runtimes) + 2, 0.32 * len(benches) + 1.5))
    cmap = cmap or plt.cm.YlOrRd
    plot_grid = np.log10(grid + 1) if log else grid
    vmin, vmax = (None, None)
    if log:
        finite = plot_grid[np.isfinite(plot_grid)]
        vmin = 0.0
        vmax = max(float(finite.max()), 0.1) if finite.size else 0.1
    im = ax.imshow(plot_grid, aspect="auto", cmap=cmap, vmin=vmin, vmax=vmax)

    ax.set_xticks(range(len(runtimes)))
    ax.set_xticklabels(runtimes, fontsize=9, rotation=25, ha="right")
    ax.set_yticks(range(len(benches)))
    ax.set_yticklabels(benches, fontsize=8)
    ax.set_title(title, fontsize=11, pad=10)

    for i in range(len(benches)):
        for j in range(len(runtimes)):
            v = grid[i, j]
            if v == v:
                ax.text(j, i, fmt.format(v), ha="center", va="center", fontsize=7, color="black")
            else:
                ax.text(j, i, "—", ha="center", va="center", fontsize=7, color="gray")

    cbar = fig.colorbar(im, ax=ax, shrink=0.6)
    cbar.set_label(cbar_label, fontsize=9)
    cbar.ax.tick_params(labelsize=8)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {output_path}")


def print_table(data, benches, runtimes):
    header = f"{'benchmark':<24}" + "".join(f"{rt:>22}" for rt in runtimes)
    print(f"\n{header}")
    for b in benches:
        row = f"{b:<24}"
        for rt in runtimes:
            wt = median(data[b].get(rt, {}).get("wall_time", []))
            row += f"{wt:>22.2f}" if wt == wt else f"{'--':>22}"
        print(row)


def write_summary_txt(data, benches, runtimes, baseline_rt, output_path):
    """Per-runtime summary across benchmarks: average, median, and range
    (min-max) of wall_time/max_rss ratio (vs. baseline_rt), plus raw
    gc_overhead %% and compaction count, all computed across the benchmark
    set for each runtime column. Benchmarks missing on a given runtime
    (build failures) are excluded from that column's stats."""
    lines = []
    lines.append("Compactor comparison -- cross-benchmark summary statistics")
    lines.append("=" * 70)
    lines.append("")
    for metric, label, is_ratio in [
        ("wall_time", f"wall_time ratio vs. {baseline_rt}", True),
        ("max_rss_mb", f"max RSS ratio vs. {baseline_rt}", True),
        ("gc_overhead", "gc_overhead %% (raw)", False),
        ("compactions", "compactions (raw)", False),
    ]:
        lines.append(f"{label} (average / median / range across benchmarks):")
        lines.append(f"{'runtime':<26}{'avg':>10}{'median':>10}{'min':>10}{'max':>10}{'range':>10}")
        for rt in runtimes:
            vals = []
            for b in benches:
                v = median(data[b].get(rt, {}).get(metric, []))
                if v != v:
                    continue
                if is_ratio:
                    baseline = median(data[b].get(baseline_rt, {}).get(metric, []))
                    if baseline == baseline and baseline != 0:
                        vals.append(v / baseline)
                else:
                    vals.append(v)
            if not vals:
                lines.append(f"{rt:<26}{'--':>10}")
                continue
            avg, med = np.mean(vals), np.median(vals)
            lo, hi = min(vals), max(vals)
            n = len(vals)
            if is_ratio:
                fmt = lambda x: f"{x:.3f}x"
            elif metric == "gc_overhead":
                fmt = lambda x: f"{x:.1f}%"
            else:
                fmt = lambda x: f"{x:.0f}"
            cells = "".join(f"{fmt(x):>10}" for x in [avg, med, lo, hi, hi - lo])
            lines.append(f"{rt:<26}{cells}   (n={n}/{len(benches)})")
        lines.append("")

    text = "\n".join(lines) + "\n"
    output_path.write_text(text)
    print(f"  saved {output_path}")
    print(text)


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    run_dir = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    runtimes = sys.argv[3].split(",")
    output_dir.mkdir(parents=True, exist_ok=True)

    data = load_run(run_dir, runtimes)
    benches = sorted(data.keys())
    print(f"Loaded {len(benches)} benchmarks x {len(runtimes)} runtimes from {run_dir}")
    print(f"Runtimes: {runtimes}")

    print_table(data, benches, runtimes)

    baseline_rt = runtimes[0]
    write_summary_txt(data, benches, runtimes, baseline_rt, output_dir / "summary_stats.txt")

    plot_ratio_heatmap(
        data, benches, runtimes, baseline_rt, "wall_time",
        f"Wall time vs. {baseline_rt}",
        f"wall time ratio vs. {baseline_rt}",
        output_dir / "heatmap_wall_time_ratio.png",
        vrange=0.30,
    )
    plot_ratio_heatmap(
        data, benches, runtimes, baseline_rt, "max_rss_mb",
        f"Max RSS vs. {baseline_rt}",
        f"max RSS ratio vs. {baseline_rt}",
        output_dir / "heatmap_max_rss_ratio.png",
        vrange=0.15,
    )
    plot_raw_heatmap(
        data, benches, runtimes, "gc_overhead",
        "GC overhead %% (gc_time / wall_time)",
        "gc_overhead %%",
        output_dir / "heatmap_gc_overhead_pct.png",
        fmt="{:.1f}%",
        cmap=plt.cm.YlOrRd,
    )
    plot_raw_heatmap(
        data, benches, runtimes, "compactions",
        "Compaction count per invocation",
        "compactions (log10(n+1) color scale)",
        output_dir / "heatmap_compactions.png",
        fmt="{:.0f}",
        cmap=plt.cm.YlOrRd,
        log=True,
    )


if __name__ == "__main__":
    main()
