"""
Plot Jane Street "Memory Allocator Showdown"-style space-time curves
(https://blog.janestreet.com/memory-allocator-showdown/): sweep OCaml's
space_overhead (`o=`) parameter and plot wall_time (y) against max RSS (x)
for each runtime, connecting points in `o=` order to trace a curve. A curve
closer to the origin (down and to the left) is strictly better: faster AND
smaller, for the same knob setting.

Usage:
    python3 plot_space_time_curve.py <run_dir> <output_dir> <bench_name> \
        <runtime1,runtime2,...> [o_values_comma_separated]
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

DEFAULT_O_VALUES = [20, 40, 80, 120, 160, 240, 320]


def make_sidecar_re(bench, runtimes):
    alts = "|".join(re.escape(r) for r in sorted(runtimes, key=len, reverse=True))
    return re.compile(
        rf"^olly_{re.escape(bench)}\.\d+\.\d+\."
        rf"(?P<runtime>{alts})\.perf_grp\d+\.re-\d+\.md-\d+\.o-(?P<o>\d+)\."
        r"macro-[a-zA-Z0-9_\-]+\.json$"
    )


def load_run(run_dir: Path, bench: str, runtimes) -> dict:
    """Return {runtime: {o: {"wall_time": [...], "max_rss_mb": [...],
    "gc_overhead": [...], "compactions": [...]}}}."""
    sidecar_re = make_sidecar_re(bench, runtimes)
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for path in sorted(run_dir.glob(f"olly_{bench}.*.json")):
        m = sidecar_re.match(path.name)
        if not m:
            continue
        rt = m.group("runtime")
        o_val = int(m.group("o"))
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            cell = data[rt][o_val]
            cell["wall_time"].append(rec.get("wall_time", float("nan")))
            cell["max_rss_mb"].append(rec.get("max_rss_kb", float("nan")) / 1024.0)
            cell["gc_overhead"].append(rec.get("gc_overhead", float("nan")))
            cell["compactions"].append(
                rec.get("collections", {}).get("compactions", float("nan"))
            )
    return data


def median(vals):
    clean = [v for v in vals if v == v]
    return float(np.median(clean)) if clean else float("nan")


def plot_curve(data, runtimes, o_values, bench, output_path, title_suffix=""):
    fig, ax = plt.subplots(figsize=(8, 6.5))
    colors = plt.cm.tab10(np.linspace(0, 1, len(runtimes)))

    for rt, color in zip(runtimes, colors):
        xs, ys, labels = [], [], []
        for o in o_values:
            cell = data.get(rt, {}).get(o, {})
            rss = median(cell.get("max_rss_mb", []))
            wt = median(cell.get("wall_time", []))
            if rss == rss and wt == wt:
                xs.append(wt)
                ys.append(rss)
                labels.append(o)
        if not xs:
            continue
        ax.plot(xs, ys, "-o", color=color, label=rt, markersize=6, linewidth=1.8)
        for x, y, o in zip(xs, ys, labels):
            ax.annotate(f"o={o}", (x, y), textcoords="offset points",
                        xytext=(5, 5), fontsize=7, color=color)

    ax.set_xlabel("wall time (s)", fontsize=11)
    ax.set_ylabel("max RSS (MB)", fontsize=11)
    ax.set_title(f"{bench}{title_suffix}: space-time curve (space_overhead `o=` sweep)\n"
                 f"better = down and to the left", fontsize=12)
    ax.legend(fontsize=9, loc="best")
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {output_path}")


def fit_convex_poly(xs, ys, degree=2):
    """Least-squares polynomial fit of degree `degree`, constrained convex
    (leading coefficient >= 0, i.e. the curve bows upward like a real
    space-time tradeoff frontier rather than arcing up-then-down).

    For a convex quadratic objective (sum of squared residuals, linear in
    the coefficients) with a single linear inequality constraint on the
    leading coefficient, standard KKT theory says: if the unconstrained
    optimum already satisfies the constraint, it IS the constrained
    optimum; otherwise the constrained optimum lies exactly on the
    boundary (leading coefficient = 0), i.e. is the best-fit polynomial of
    one degree lower. So: fit unconstrained, and if that violates
    convexity, drop the degree and retry -- no QP solver (scipy) needed.
    """
    d = degree
    while d >= 1:
        coeffs = np.polyfit(xs, ys, d)
        if coeffs[0] >= 0 or d == 1:
            # d == 1 (a line) has zero curvature -- degenerate-convex,
            # always accepted as the final fallback.
            return np.pad(coeffs, (degree + 1 - len(coeffs), 0))
        d -= 1
    # Only reachable if degree < 1; fall back to the flat mean.
    return np.array([0.0] * degree + [np.mean(ys)])


def plot_curve_fit(data, runtimes, o_values, bench, output_path, degree=2,
                    title_suffix=""):
    """Same axes/data as plot_curve, but instead of connecting the raw
    points in `o=` order, fits a degree-`degree` polynomial RSS = f(wall_time)
    per runtime -- constrained convex via `fit_convex_poly` -- and draws
    that as a smooth curve. Raw points are still scattered (unconnected)
    for reference, so the fit's fidelity to the underlying data stays
    visible."""
    fig, ax = plt.subplots(figsize=(8, 6.5))
    colors = plt.cm.tab10(np.linspace(0, 1, len(runtimes)))

    for rt, color in zip(runtimes, colors):
        xs, ys = [], []
        for o in o_values:
            cell = data.get(rt, {}).get(o, {})
            rss = median(cell.get("max_rss_mb", []))
            wt = median(cell.get("wall_time", []))
            if rss == rss and wt == wt:
                xs.append(wt)
                ys.append(rss)
        if len(xs) < degree + 1:
            continue
        xs_arr, ys_arr = np.array(xs), np.array(ys)
        ax.scatter(xs_arr, ys_arr, color=color, s=28, zorder=3, alpha=0.85)

        coeffs = fit_convex_poly(xs_arr, ys_arr, degree)
        poly = np.poly1d(coeffs)
        x_fit = np.linspace(xs_arr.min(), xs_arr.max(), 200)
        y_fit = poly(x_fit)
        ax.plot(x_fit, y_fit, "-", color=color, label=rt, linewidth=2)

    ax.set_xlabel("wall time (s)", fontsize=11)
    ax.set_ylabel("max RSS (MB)", fontsize=11)
    ax.set_title(f"{bench}{title_suffix}: space-time curve, convex degree-{degree} fit\n"
                 f"(space_overhead `o=` sweep) -- better = down and to the left",
                 fontsize=12)
    ax.legend(fontsize=9, loc="best")
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {output_path}")


def print_table_and_summary(data, runtimes, o_values, bench, output_path):
    lines = []
    lines.append(f"{bench}: space_overhead (o=) sweep -- wall_time / RSS / gc_overhead / compactions")
    lines.append("=" * 100)
    for rt in runtimes:
        lines.append(f"\n{rt}:")
        lines.append(f"{'o=':<8}{'wall_time(s)':>14}{'max_rss(MB)':>14}{'gc_overhead':>14}{'compactions':>14}")
        for o in o_values:
            cell = data.get(rt, {}).get(o, {})
            wt = median(cell.get("wall_time", []))
            rss = median(cell.get("max_rss_mb", []))
            gc = median(cell.get("gc_overhead", []))
            comp = median(cell.get("compactions", []))
            if wt == wt:
                lines.append(
                    f"o={o:<6}{wt:>14.3f}{rss:>14.1f}{gc:>13.1f}%{comp:>14.0f}"
                )
            else:
                lines.append(f"o={o:<6}{'--':>14}")

    lines.append("")
    lines.append("Cross-o= summary per runtime (average / median / range):")
    lines.append(f"{'runtime':<24}{'wall avg':>12}{'wall med':>12}{'wall range':>12}"
                 f"{'rss avg':>12}{'rss med':>12}{'rss range':>12}")
    for rt in runtimes:
        wts = [median(data.get(rt, {}).get(o, {}).get("wall_time", [])) for o in o_values]
        wts = [v for v in wts if v == v]
        rsses = [median(data.get(rt, {}).get(o, {}).get("max_rss_mb", [])) for o in o_values]
        rsses = [v for v in rsses if v == v]
        if not wts or not rsses:
            continue
        lines.append(
            f"{rt:<24}{np.mean(wts):>11.3f}s{np.median(wts):>11.3f}s{max(wts)-min(wts):>11.3f}s"
            f"{np.mean(rsses):>11.1f}M{np.median(rsses):>11.1f}M{max(rsses)-min(rsses):>11.1f}M"
        )

    text = "\n".join(lines) + "\n"
    output_path.write_text(text)
    print(text)
    print(f"  saved {output_path}")


def parse_groups(spec):
    """Parse "label1=rt1,rt2;label2=rt3,rt4" into [(label1, [rt1,rt2]), ...]."""
    groups = []
    for part in spec.split(";"):
        label, rts = part.split("=", 1)
        groups.append((label.strip(), rts.split(",")))
    return groups


def main():
    if len(sys.argv) < 5:
        print(__doc__)
        sys.exit(1)
    run_dir = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    bench = sys.argv[3]
    runtimes = sys.argv[4].split(",")
    o_values = [int(x) for x in sys.argv[5].split(",")] if len(sys.argv) > 5 else DEFAULT_O_VALUES
    # Optional: "label1=rtA,rtB;label2=rtC,rtD" -- when the full runtime set
    # spans clusters too far apart to read on one shared axis (e.g. owl_gc's
    # stock vs. chunk-allocator runtimes), plot each group on its own
    # auto-scaled figure instead of one combined one.
    groups_spec = sys.argv[6] if len(sys.argv) > 6 else None
    output_dir.mkdir(parents=True, exist_ok=True)

    data = load_run(run_dir, bench, runtimes)
    print(f"Loaded {bench}: runtimes={list(data.keys())}")

    if groups_spec:
        for label, group_rts in parse_groups(groups_spec):
            plot_curve(data, group_rts, o_values, bench,
                       output_dir / f"space_time_curve_{bench}_{label}.png",
                       title_suffix=f" ({label})")
            plot_curve_fit(data, group_rts, o_values, bench,
                           output_dir / f"space_time_curve_fit_{bench}_{label}.png",
                           title_suffix=f" ({label})")
    else:
        plot_curve(data, runtimes, o_values, bench, output_dir / f"space_time_curve_{bench}.png")
        plot_curve_fit(data, runtimes, o_values, bench, output_dir / f"space_time_curve_fit_{bench}.png")

    print_table_and_summary(data, runtimes, o_values, bench,
                             output_dir / f"space_time_curve_{bench}.txt")


if __name__ == "__main__":
    main()
