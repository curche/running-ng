"""
Plot lineage x build-flags heatmaps from the flambda/fp pplacer_testsuite
investigation.

Unlike compactor-comparison's plot_results.py (benchmark x runtime, since
that experiment spans ~30 benchmarks x 4 runtimes), this investigation is a
single benchmark (pplacer_testsuite) x 4 source lineages x 4 build-flag
combinations. The natural "map" here is lineage (rows) x flags (columns).

Usage:
    python3 plot_heatmap.py <run_dir> <output_dir>

E.g.:
    python3 plot_heatmap.py \
        turing-2026-07-15-Wed-144732 \
        plots/turing-2026-07-15-Wed-144732
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

SIDECAR_RE = re.compile(
    r"^olly_pplacer_testsuite\.\d+\.\d+\."
    r"(?P<runtime>.+?)\.perf_grp\d+\.re-\d+\.md-\d+\.macro-pplacer\.json$"
)

# lineage (row) x flags (column) -> runtime name in the config
LINEAGES = ["ocaml-5.5", "ocaml-auto-compact", "socaml", "socaml-auto-compact"]
LINEAGE_LABELS = {
    "ocaml-5.5": "stock",
    "ocaml-auto-compact": "auto-compact",
    "socaml": "chunk allocator",
    "socaml-auto-compact": "chunk allocator\n+ auto-compact",
}
FLAGS = ["plain", "fp", "flambda", "flambda-fp"]
FLAG_LABELS = {
    "plain": "plain",
    "fp": "+fp",
    "flambda": "+flambda",
    "flambda-fp": "+flambda+fp",
}


def runtime_name(lineage: str, flag: str) -> str:
    if flag == "plain":
        return lineage
    return f"{lineage}-{flag}"


def load_run(run_dir: Path) -> dict:
    """Return {runtime: {wall_time: [...], max_rss_mb: [...], gc_time: [...]}}."""
    data = defaultdict(lambda: defaultdict(list))
    for path in sorted(run_dir.glob("olly_pplacer_testsuite*.json")):
        m = SIDECAR_RE.match(path.name)
        if not m:
            continue
        rt = m.group("runtime")
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            data[rt]["wall_time"].append(rec.get("wall_time", float("nan")))
            rss_kb = rec.get("max_rss_kb", float("nan"))
            data[rt]["max_rss_mb"].append(rss_kb / 1024.0 if rss_kb == rss_kb else float("nan"))
            data[rt]["gc_time"].append(rec.get("gc_time", float("nan")))
    return data


def median(vals):
    clean = [v for v in vals if v == v]
    return float(np.median(clean)) if clean else float("nan")


def plot_heatmap(data, metric, title, cbar_label, output_path, higher_is_worse=True, vrange=0.10):
    baseline = median(data.get("ocaml-5.5", {}).get(metric, []))

    grid = np.full((len(LINEAGES), len(FLAGS)), np.nan)
    for i, lineage in enumerate(LINEAGES):
        for j, flag in enumerate(FLAGS):
            rt = runtime_name(lineage, flag)
            m = median(data.get(rt, {}).get(metric, []))
            if m == m and baseline == baseline and baseline != 0:
                grid[i, j] = m / baseline

    fig, ax = plt.subplots(figsize=(7, 5.5))

    cmap = plt.cm.RdYlGn_r if higher_is_worse else plt.cm.RdYlGn
    vmin, vmax = 1 - vrange, 1 + vrange
    im = ax.imshow(grid, aspect="auto", cmap=cmap, vmin=vmin, vmax=vmax)

    ax.set_xticks(range(len(FLAGS)))
    ax.set_xticklabels([FLAG_LABELS[f] for f in FLAGS], fontsize=10)
    ax.set_yticks(range(len(LINEAGES)))
    ax.set_yticklabels([LINEAGE_LABELS[l] for l in LINEAGES], fontsize=10)
    ax.set_title(title, fontsize=12, pad=12)

    for i in range(len(LINEAGES)):
        for j in range(len(FLAGS)):
            v = grid[i, j]
            if v == v:
                pct = (v - 1) * 100
                txt = f"{pct:+.1f}%"
                color = "black" if 0.94 < v < 1.06 else "white"
                ax.text(j, i, txt, ha="center", va="center", fontsize=11, color=color)
            else:
                ax.text(j, i, "—", ha="center", va="center", fontsize=11, color="gray")

    cbar = fig.colorbar(im, ax=ax, shrink=0.7)
    cbar.set_label(cbar_label, fontsize=9)
    cbar.ax.tick_params(labelsize=8)

    ax.set_xlabel("compiler flags", fontsize=10)
    ax.set_ylabel("source lineage", fontsize=10)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {output_path}")


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    run_dir = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    output_dir.mkdir(parents=True, exist_ok=True)

    data = load_run(run_dir)
    print(f"Loaded {len(data)} runtimes from {run_dir}")

    plot_heatmap(
        data, "wall_time",
        "pplacer_testsuite: wall time vs. stock plain",
        "wall time ratio vs. ocaml-5.5 plain",
        output_dir / "heatmap_wall_time.png",
        higher_is_worse=True,
    )
    plot_heatmap(
        data, "max_rss_mb",
        "pplacer_testsuite: max RSS vs. stock plain",
        "RSS ratio vs. ocaml-5.5 plain",
        output_dir / "heatmap_rss.png",
        higher_is_worse=True,
        vrange=0.10,
    )
    plot_heatmap(
        data, "gc_time",
        "pplacer_testsuite: GC time vs. stock plain",
        "gc_time ratio vs. ocaml-5.5 plain",
        output_dir / "heatmap_gc_time.png",
        higher_is_worse=True,
        vrange=0.30,
    )


if __name__ == "__main__":
    main()
