"""
Plot wall-clock time, max RSS, and compaction counts from the
compactor-comparison benchmark run.

Usage:
    python3 plot_results.py <run_dir> <output_dir>

E.g.:
    python3 plot_results.py \
        logs/turing-2026-07-01-Wed-230036 \
        plots/turing-2026-07-01-Wed-230036
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
import matplotlib.ticker as mticker

# ---------------------------------------------------------------------------
# Parse olly JSON sidecars
# ---------------------------------------------------------------------------

SIDECAR_RE = re.compile(
    r"^olly_(?P<benchmark>[a-z0-9_]+)"
    r"\.\d+\.\d+\."
    r"(?P<runtime>[^.]+(?:\.[^.]+)*?)"
    r"\.perf_grp\d+"
    r"\.re-\d+"
    r"\.md-\d+"
    r"(?:\.macro-[a-z0-9-]+)?"
    r"\.json$"
)

RUNTIME_ORDER = ["ocaml-5.5", "ocaml-auto-compact", "socaml", "socaml-auto-compact"]
RUNTIME_LABELS = {
    "ocaml-5.5":           "5.5 stock",
    "ocaml-auto-compact":  "5.5 + auto-compact",
    "socaml":              "new compactor",
    "socaml-auto-compact": "new compactor\n+ auto-compact",
}
COLORS = {
    "ocaml-5.5":           "#4878CF",
    "ocaml-auto-compact":  "#6ACC65",
    "socaml":              "#D65F5F",
    "socaml-auto-compact": "#B47CC7",
}

def load_run(run_dir: Path) -> dict:
    """Return {benchmark: {runtime: {wall_time, max_rss_mb, compactions}}}
    where each value is a list (one per invocation)."""
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for path in sorted(run_dir.glob("olly_*.json")):
        m = SIDECAR_RE.match(path.name)
        if not m:
            continue
        bm, rt = m.group("benchmark"), m.group("runtime")
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            wt = rec.get("wall_time", float("nan"))
            if wt < 0:  # corrupted olly wall_time (lost runtime events)
                wt = float("nan")
            data[bm][rt]["wall_time"].append(wt)
            rss_kb = rec.get("max_rss_kb", float("nan"))
            data[bm][rt]["max_rss_mb"].append(rss_kb / 1024.0 if rss_kb == rss_kb else float("nan"))
            data[bm][rt]["compactions"].append(
                rec.get("collections", {}).get("compactions", 0)
            )
    return data


def median(vals):
    clean = [v for v in vals if v == v]
    return float(np.median(clean)) if clean else float("nan")


# ---------------------------------------------------------------------------
# Heatmap: ratios vs baseline (ocaml-5.5)
# ---------------------------------------------------------------------------

def plot_heatmap(data, metric, title, fmt, output_path, higher_is_worse=True):
    baselines = ["ocaml-5.5"]
    comparisons = [r for r in RUNTIME_ORDER if r != "ocaml-5.5"]

    benchmarks = sorted(
        bm for bm in data
        if any(data[bm].get(r) for r in RUNTIME_ORDER)
    )
    if not benchmarks:
        return

    n_bm = len(benchmarks)
    n_cmp = len(comparisons)

    ratios = np.full((n_bm, n_cmp), np.nan)
    for i, bm in enumerate(benchmarks):
        base_vals = data[bm].get("ocaml-5.5", {}).get(metric, [])
        base = median(base_vals)
        if base != base or base == 0:
            continue
        for j, rt in enumerate(comparisons):
            vals = data[bm].get(rt, {}).get(metric, [])
            m = median(vals)
            if m == m:
                ratios[i, j] = m / base

    fig, ax = plt.subplots(
        figsize=(max(6, n_cmp * 2.2), max(5, n_bm * 0.45 + 1.5))
    )

    # Colour: green = better (< 1), red = worse (> 1) if higher_is_worse
    cmap = plt.cm.RdYlGn_r if higher_is_worse else plt.cm.RdYlGn
    vmin, vmax = 0.9, 1.1
    im = ax.imshow(ratios, aspect="auto", cmap=cmap, vmin=vmin, vmax=vmax)

    ax.set_xticks(range(n_cmp))
    ax.set_xticklabels(
        [RUNTIME_LABELS[r] for r in comparisons],
        fontsize=9, ha="center"
    )
    ax.set_yticks(range(n_bm))
    ax.set_yticklabels(benchmarks, fontsize=8)
    ax.set_title(title, fontsize=11, pad=10)

    for i in range(n_bm):
        for j in range(n_cmp):
            v = ratios[i, j]
            if v == v:
                txt = fmt.format(v)
                color = "black" if 0.93 < v < 1.07 else "white"
                ax.text(j, i, txt, ha="center", va="center", fontsize=7, color=color)

    cbar = fig.colorbar(im, ax=ax, shrink=0.6)
    cbar.set_label("ratio vs 5.5 stock", fontsize=8)
    cbar.ax.tick_params(labelsize=7)

    ax.set_xlabel("runtime", fontsize=9)
    ax.set_ylabel("benchmark", fontsize=9)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {output_path}")


# ---------------------------------------------------------------------------
# Bar chart: compaction counts per benchmark × runtime
# ---------------------------------------------------------------------------

def plot_compaction_bars(data, output_path):
    benchmarks = sorted(
        bm for bm in data
        if any(
            sum(data[bm].get(rt, {}).get("compactions", [0])) > 0
            for rt in RUNTIME_ORDER
        )
    )
    if not benchmarks:
        # No compactions anywhere — still produce an informative chart
        benchmarks = sorted(data.keys())
        all_zero = True
    else:
        all_zero = False

    n_bm = len(benchmarks)
    n_rt = len(RUNTIME_ORDER)
    width = 0.8 / n_rt

    fig, ax = plt.subplots(figsize=(max(10, n_bm * 0.7), 5))

    for j, rt in enumerate(RUNTIME_ORDER):
        xs = np.arange(n_bm) + (j - n_rt / 2 + 0.5) * width
        ys = [
            median(data[bm].get(rt, {}).get("compactions", [0]))
            for bm in benchmarks
        ]
        ax.bar(xs, ys, width=width * 0.9,
               label=RUNTIME_LABELS[rt], color=COLORS[rt], alpha=0.85)

    ax.set_xticks(np.arange(n_bm))
    ax.set_xticklabels(benchmarks, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("compactions (median across invocations)", fontsize=9)
    ax.set_title("Compaction counts per benchmark and runtime", fontsize=11)
    ax.legend(fontsize=8, loc="upper right")
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    if all_zero:
        ax.set_ylim(0, 1)
        ax.text(
            0.5, 0.5, "No compactions observed\n(default O=500% threshold not reached)",
            transform=ax.transAxes, ha="center", va="center",
            fontsize=10, color="gray"
        )

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {output_path}")


# ---------------------------------------------------------------------------
# Summary table: absolute medians
# ---------------------------------------------------------------------------

def print_summary(data):
    benchmarks = sorted(data.keys())
    print(f"\n{'benchmark':<30}  {'runtime':<25}  {'wall_s':>7}  {'rss_mb':>8}  {'compact':>7}")
    print("-" * 82)
    for bm in benchmarks:
        for rt in RUNTIME_ORDER:
            if rt not in data[bm]:
                continue
            w  = median(data[bm][rt].get("wall_time", [float("nan")]))
            r  = median(data[bm][rt].get("max_rss_mb", [float("nan")]))
            c  = median(data[bm][rt].get("compactions", [0]))
            print(f"{bm:<30}  {rt:<25}  {w:>7.2f}  {r:>8.1f}  {c:>7.0f}")


# ---------------------------------------------------------------------------
# GC overhead comparison
# ---------------------------------------------------------------------------

def load_gc_overhead(run_dir: Path) -> dict:
    """Return {benchmark: {runtime: [gc_overhead_pct]}} from olly JSON."""
    data = defaultdict(lambda: defaultdict(list))
    for path in sorted(run_dir.glob("olly_*.json")):
        m = SIDECAR_RE.match(path.name)
        if not m:
            continue
        bm, rt = m.group("benchmark"), m.group("runtime")
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            data[bm][rt].append(rec.get("gc_overhead", float("nan")))
    return data


def plot_gc_overhead_heatmap(run_dir, output_path):
    data = load_gc_overhead(run_dir)
    benchmarks = sorted(
        bm for bm in data
        if any(data[bm].get(r) for r in RUNTIME_ORDER)
    )
    n_bm, n_rt = len(benchmarks), len(RUNTIME_ORDER)
    matrix = np.full((n_bm, n_rt), np.nan)
    for i, bm in enumerate(benchmarks):
        for j, rt in enumerate(RUNTIME_ORDER):
            vals = data[bm].get(rt, [])
            m = median(vals)
            if m == m:
                matrix[i, j] = m

    fig, ax = plt.subplots(figsize=(max(6, n_rt * 2), max(5, n_bm * 0.45 + 1.5)))
    im = ax.imshow(matrix, aspect="auto", cmap="YlOrRd", vmin=0, vmax=50)
    ax.set_xticks(range(n_rt))
    ax.set_xticklabels([RUNTIME_LABELS[r] for r in RUNTIME_ORDER], fontsize=9)
    ax.set_yticks(range(n_bm))
    ax.set_yticklabels(benchmarks, fontsize=8)
    ax.set_title("GC overhead % (absolute)", fontsize=11, pad=10)
    for i in range(n_bm):
        for j in range(n_rt):
            v = matrix[i, j]
            if v == v:
                ax.text(j, i, f"{v:.1f}%", ha="center", va="center", fontsize=6.5,
                        color="black" if v < 35 else "white")
    cbar = fig.colorbar(im, ax=ax, shrink=0.6)
    cbar.set_label("GC overhead %", fontsize=8)
    cbar.ax.tick_params(labelsize=7)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    run_dir = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading data from {run_dir} ...")
    data = load_run(run_dir)
    print(f"  {len(data)} benchmarks found")

    print_summary(data)

    print("\nGenerating plots ...")
    plot_heatmap(
        data, "wall_time",
        "Wall-clock time ratio vs stock OCaml 5.5\n(< 1 = faster, > 1 = slower)",
        "{:.3f}",
        out_dir / "heatmap_wall_time_ratio.png",
        higher_is_worse=True,
    )
    plot_heatmap(
        data, "max_rss_mb",
        "Max RSS ratio vs stock OCaml 5.5\n(< 1 = less memory, > 1 = more memory)",
        "{:.3f}",
        out_dir / "heatmap_max_rss_ratio.png",
        higher_is_worse=True,
    )
    plot_compaction_bars(data, out_dir / "compaction_counts.png")
    plot_gc_overhead_heatmap(run_dir, out_dir / "heatmap_gc_overhead_pct.png")
    print("Done.")


if __name__ == "__main__":
    main()
