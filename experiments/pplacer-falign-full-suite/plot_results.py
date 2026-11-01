"""
Plot wall-clock time, max RSS, GC overhead and compaction counts, comparing
each patch's PLAIN (non-falign) and FALIGN builds side by side against
plain ocaml-5.5 stock. Merges two run directories:
  - the falign full-suite run (ocaml-5.5 plain reference + 4 -falign variants)
  - the earlier non-falign full-suite run (ocaml-5.5, ocaml-auto-compact,
    socaml, socaml-auto-compact)

Usage:
    python3 plot_results.py <falign_run_dir> <nonfalign_run_dir> <output_dir>

E.g.:
    python3 plot_results.py \
        logs/turing-2026-07-17-Fri-132855 \
        ../compactor-comparison/logs/turing-2026-07-16-Thu-190928 \
        plots/turing-2026-07-17-Fri-132855
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

# Column order: baseline first (excluded from plotted comparisons), then
# each patch's plain build paired right next to its falign build.
RUNTIME_ORDER = [
    "ocaml-5.5",
    "ocaml-5.5-falign",
    "ocaml-auto-compact",
    "ocaml-auto-compact-falign",
    "socaml",
    "socaml-falign",
    "socaml-auto-compact",
    "socaml-auto-compact-falign",
]
RUNTIME_LABELS = {
    "ocaml-5.5":                  "5.5 stock\n(plain)",
    "ocaml-5.5-falign":           "5.5 stock\n(falign)",
    "ocaml-auto-compact":         "5.5 + auto-compact\n(plain)",
    "ocaml-auto-compact-falign":  "5.5 + auto-compact\n(falign)",
    "socaml":                     "new compactor\n(plain)",
    "socaml-falign":              "new compactor\n(falign)",
    "socaml-auto-compact":        "new compactor\n+ auto-compact\n(plain)",
    "socaml-auto-compact-falign": "new compactor\n+ auto-compact\n(falign)",
}
COLORS = {
    "ocaml-5.5":                  "#999999",
    "ocaml-5.5-falign":           "#4878CF",
    "ocaml-auto-compact":         "#A8DDA0",
    "ocaml-auto-compact-falign":  "#6ACC65",
    "socaml":                     "#F2A9A9",
    "socaml-falign":              "#D65F5F",
    "socaml-auto-compact":        "#D9BEE6",
    "socaml-auto-compact-falign": "#B47CC7",
}

BASELINE = "ocaml-5.5"  # plain stock reference, taken from the falign run

# runtime keys that come from the non-falign run dir; everything else
# (including baseline) comes from the falign run dir.
FROM_NONFALIGN = {"ocaml-auto-compact", "socaml", "socaml-auto-compact"}


def load_run(run_dir: Path, only_runtimes=None) -> dict:
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for path in sorted(run_dir.glob("olly_*.json")):
        m = SIDECAR_RE.match(path.name)
        if not m:
            continue
        bm, rt = m.group("benchmark"), m.group("runtime")
        if only_runtimes is not None and rt not in only_runtimes:
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            wt = rec.get("wall_time", float("nan"))
            if wt < 0:
                wt = float("nan")
            data[bm][rt]["wall_time"].append(wt)
            rss_kb = rec.get("max_rss_kb", float("nan"))
            data[bm][rt]["max_rss_mb"].append(rss_kb / 1024.0 if rss_kb == rss_kb else float("nan"))
            data[bm][rt]["compactions"].append(
                rec.get("collections", {}).get("compactions", 0)
            )
            data[bm][rt]["gc_overhead"].append(rec.get("gc_overhead", float("nan")))
    return data


def merge_runs(falign_dir: Path, nonfalign_dir: Path) -> dict:
    falign_data = load_run(falign_dir)
    nonfalign_data = load_run(nonfalign_dir, only_runtimes=FROM_NONFALIGN)

    merged = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for bm, per_rt in falign_data.items():
        for rt, metrics in per_rt.items():
            merged[bm][rt] = metrics
    for bm, per_rt in nonfalign_data.items():
        for rt, metrics in per_rt.items():
            merged[bm][rt] = metrics
    return merged


def median(vals):
    clean = [v for v in vals if v == v]
    return float(np.median(clean)) if clean else float("nan")


def plot_heatmap(data, metric, title, fmt, output_path, higher_is_worse=True):
    comparisons = [r for r in RUNTIME_ORDER if r != BASELINE]

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
        base_vals = data[bm].get(BASELINE, {}).get(metric, [])
        base = median(base_vals)
        if base != base or base == 0:
            continue
        for j, rt in enumerate(comparisons):
            vals = data[bm].get(rt, {}).get(metric, [])
            m = median(vals)
            if m == m:
                ratios[i, j] = m / base

    fig, ax = plt.subplots(
        figsize=(max(6, n_cmp * 2.6), max(5, n_bm * 0.45 + 1.5))
    )

    cmap = plt.cm.RdYlGn_r if higher_is_worse else plt.cm.RdYlGn
    vmin, vmax = 0.9, 1.1
    im = ax.imshow(ratios, aspect="auto", cmap=cmap, vmin=vmin, vmax=vmax)

    ax.set_xticks(range(n_cmp))
    ax.set_xticklabels(
        [RUNTIME_LABELS[r] for r in comparisons],
        fontsize=8, ha="center"
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
    cbar.set_label(f"ratio vs {BASELINE}", fontsize=8)
    cbar.ax.tick_params(labelsize=7)

    ax.set_xlabel("runtime", fontsize=9)
    ax.set_ylabel("benchmark", fontsize=9)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {output_path}")


def plot_compaction_bars(data, output_path):
    benchmarks = sorted(
        bm for bm in data
        if any(
            sum(data[bm].get(rt, {}).get("compactions", [0])) > 0
            for rt in RUNTIME_ORDER
        )
    )
    if not benchmarks:
        benchmarks = sorted(data.keys())
        all_zero = True
    else:
        all_zero = False

    n_bm = len(benchmarks)
    n_rt = len(RUNTIME_ORDER)
    width = 0.8 / n_rt

    fig, ax = plt.subplots(figsize=(max(10, n_bm * 0.9), 5))

    for j, rt in enumerate(RUNTIME_ORDER):
        xs = np.arange(n_bm) + (j - n_rt / 2 + 0.5) * width
        ys = [
            median(data[bm].get(rt, {}).get("compactions", [0]))
            for bm in benchmarks
        ]
        ax.bar(xs, ys, width=width * 0.9,
               label=RUNTIME_LABELS[rt].replace("\n", " "), color=COLORS[rt], alpha=0.85)

    ax.set_xticks(np.arange(n_bm))
    ax.set_xticklabels(benchmarks, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("compactions (median across invocations)", fontsize=9)
    ax.set_title("Compaction counts per benchmark and runtime (plain + falign)", fontsize=11)
    ax.legend(fontsize=6.5, loc="upper right")
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


def print_summary(data):
    benchmarks = sorted(data.keys())
    print(f"\n{'benchmark':<30}  {'runtime':<28}  {'wall_s':>7}  {'rss_mb':>8}  {'compact':>7}")
    print("-" * 85)
    for bm in benchmarks:
        for rt in RUNTIME_ORDER:
            if rt not in data[bm]:
                continue
            w  = median(data[bm][rt].get("wall_time", [float("nan")]))
            r  = median(data[bm][rt].get("max_rss_mb", [float("nan")]))
            c  = median(data[bm][rt].get("compactions", [0]))
            print(f"{bm:<30}  {rt:<28}  {w:>7.2f}  {r:>8.1f}  {c:>7.0f}")


def plot_gc_overhead_heatmap(data, output_path):
    comparisons = [r for r in RUNTIME_ORDER if r != BASELINE]

    benchmarks = sorted(
        bm for bm in data
        if any(data[bm].get(r) for r in RUNTIME_ORDER)
    )
    n_bm, n_rt = len(benchmarks), len(comparisons)
    matrix = np.full((n_bm, n_rt), np.nan)
    base_vals_by_bm = np.full(n_bm, np.nan)
    for i, bm in enumerate(benchmarks):
        base_vals_by_bm[i] = median(data[bm].get(BASELINE, {}).get("gc_overhead", []))
        for j, rt in enumerate(comparisons):
            vals = data[bm].get(rt, {}).get("gc_overhead", [])
            m = median(vals)
            if m == m:
                matrix[i, j] = m

    # Convert to percentage-point delta vs BASELINE, per benchmark row.
    delta = np.full_like(matrix, np.nan)
    for i in range(n_bm):
        base_v = base_vals_by_bm[i]
        if base_v != base_v:
            continue
        for j in range(n_rt):
            v = matrix[i, j]
            if v == v:
                delta[i, j] = v - base_v

    fig, ax = plt.subplots(figsize=(max(6, n_rt * 2.2), max(5, n_bm * 0.45 + 1.5)))
    im = ax.imshow(delta, aspect="auto", cmap="RdBu_r", vmin=-20, vmax=20)
    ax.set_xticks(range(n_rt))
    ax.set_xticklabels([RUNTIME_LABELS[r] for r in comparisons], fontsize=8)
    ax.set_yticks(range(n_bm))
    ax.set_yticklabels(benchmarks, fontsize=8)
    ax.set_title(f"GC overhead: change in percentage points vs {BASELINE}\n(+ = more time in GC, - = less)", fontsize=11, pad=10)
    for i in range(n_bm):
        for j in range(n_rt):
            v = delta[i, j]
            if v == v:
                ax.text(j, i, f"{v:+.1f}pp", ha="center", va="center", fontsize=6.5,
                        color="black" if -12 < v < 12 else "white")
    cbar = fig.colorbar(im, ax=ax, shrink=0.6)
    cbar.set_label(f"pp change vs {BASELINE}", fontsize=8)
    cbar.ax.tick_params(labelsize=7)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {output_path}")


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)

    falign_dir = Path(sys.argv[1])
    nonfalign_dir = Path(sys.argv[2])
    out_dir = Path(sys.argv[3])
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading falign data from {falign_dir} ...")
    print(f"Loading plain-patch data from {nonfalign_dir} ...")
    data = merge_runs(falign_dir, nonfalign_dir)
    print(f"  {len(data)} benchmarks found")

    print_summary(data)

    print("\nGenerating plots ...")
    plot_heatmap(
        data, "wall_time",
        f"Wall-clock time ratio vs {BASELINE}\n(< 1 = faster, > 1 = slower)",
        "{:.3f}",
        out_dir / "heatmap_wall_time_ratio.png",
        higher_is_worse=True,
    )
    plot_heatmap(
        data, "max_rss_mb",
        f"Max RSS ratio vs {BASELINE}\n(< 1 = less memory, > 1 = more memory)",
        "{:.3f}",
        out_dir / "heatmap_max_rss_ratio.png",
        higher_is_worse=True,
    )
    plot_compaction_bars(data, out_dir / "compaction_counts.png")
    plot_gc_overhead_heatmap(data, out_dir / "heatmap_gc_overhead_pct.png")
    print("Done.")


if __name__ == "__main__":
    main()
