"""
Direct-extraction tables for the falign full-suite run:
  1. all-values-table.txt   -- falign run only, medians + % vs ocaml-5.5-falign
  2. before-after-table.txt -- regression %, non-falign run vs falign run,
                                side by side, per benchmark x non-stock runtime

Usage:
    python3 make_tables.py <falign_run_dir> <nonfalign_run_dir> <out_dir>
"""
import json
import re
import sys
from pathlib import Path
from collections import defaultdict

import numpy as np

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


def load_run(run_dir: Path) -> dict:
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
            wt = rec.get("wall_time", float("nan"))
            if wt < 0:
                wt = float("nan")
            data[bm][rt].append(wt)
    return data


def median(vals):
    clean = [v for v in vals if v == v]
    return float(np.median(clean)) if clean else float("nan")


def main():
    falign_dir = Path(sys.argv[1])
    nonfalign_dir = Path(sys.argv[2])
    out_dir = Path(sys.argv[3])
    out_dir.mkdir(parents=True, exist_ok=True)

    falign = load_run(falign_dir)
    nonfalign = load_run(nonfalign_dir)

    FALIGN_RUNTIMES = [
        "ocaml-5.5", "ocaml-5.5-falign", "ocaml-auto-compact-falign",
        "socaml-falign", "socaml-auto-compact-falign",
    ]
    BASELINE = "ocaml-5.5"

    # --- Table 1: all-values-table.txt (falign run) ---
    lines = []
    lines.append("falign full-suite: all benchmarks, wall time (median of 3 invocations)")
    lines.append(f"run id: {falign_dir.name} -- extracted directly from olly_*.json sidecars")
    lines.append("-- = build failed / did not run for that runtime")
    lines.append("nan = corrupted olly wall_time (runtime-events ring buffer overflow, known olly issue)")
    lines.append(f"percentages are vs {BASELINE} (plain stock reference) for the same benchmark")
    lines.append("")
    header = f"{'benchmark':<22} {'ocaml-5.5':>9} {'5.5-falign':>11} {'auto-compact-falign':>21} {'socaml-falign':>18} {'socaml-ac-falign':>19}"
    lines.append(header)
    lines.append("-" * len(header))

    benchmarks = sorted(falign.keys())
    for bm in benchmarks:
        base = median(falign[bm].get(BASELINE, []))
        cells = []
        for rt in FALIGN_RUNTIMES:
            vals = falign[bm].get(rt)
            if vals is None:
                cells.append("--")
                continue
            m = median(vals)
            if m != m:
                cells.append("nan")
            elif rt == BASELINE or base != base or base == 0:
                cells.append(f"{m:.2f}s")
            else:
                pct = (m / base - 1) * 100
                cells.append(f"{m:.2f}s ({pct:+.1f}%)")
        row = f"{bm:<22} " + " ".join(f"{c:>{w}}" for c, w in zip(
            cells, [9, 11, 21, 18, 19]))
        lines.append(row)

    (out_dir / "all-values-table.txt").write_text("\n".join(lines) + "\n")
    print(f"wrote {out_dir / 'all-values-table.txt'}")

    # --- Table 2: before-after-table.txt ---
    NONFALIGN_MAP = {
        "auto-compact-falign": ("ocaml-auto-compact-falign", "ocaml-auto-compact"),
        "socaml-falign": ("socaml-falign", "socaml"),
        "socaml-ac-falign": ("socaml-auto-compact-falign", "socaml-auto-compact"),
    }
    lines2 = []
    lines2.append("Regression %, BEFORE (non-falign) vs AFTER (falign), per benchmark")
    lines2.append(f"non-falign run: {nonfalign_dir.name}   falign run: {falign_dir.name}")
    lines2.append("baseline for each side is its own stock runtime (ocaml-5.5 / ocaml-5.5-falign)")
    lines2.append("-- = missing (build failed or nan) on that side")
    lines2.append("")
    header2 = f"{'benchmark':<22} {'auto-compact: before':>21} {'after':>9} {'socaml: before':>16} {'after':>9} {'socaml-ac: before':>19} {'after':>9}"
    lines2.append(header2)
    lines2.append("-" * len(header2))

    all_bms = sorted(set(falign.keys()) | set(nonfalign.keys()))
    for bm in all_bms:
        f_base = median(falign[bm].get("ocaml-5.5-falign", []))
        nf_base = median(nonfalign[bm].get("ocaml-5.5", []))

        def pct(run, rt, base):
            vals = run.get(bm, {}).get(rt)
            if vals is None or base != base or base == 0:
                return "--"
            m = median(vals)
            if m != m:
                return "--"
            return f"{(m / base - 1) * 100:+.1f}%"

        row_cells = []
        for label, (f_rt, nf_rt) in NONFALIGN_MAP.items():
            row_cells.append(pct(nonfalign, nf_rt, nf_base))
            row_cells.append(pct(falign, f_rt, f_base))

        row = f"{bm:<22} " + " ".join(f"{c:>{w}}" for c, w in zip(
            row_cells, [21, 9, 16, 9, 19, 9]))
        lines2.append(row)

    (out_dir / "before-after-table.txt").write_text("\n".join(lines2) + "\n")
    print(f"wrote {out_dir / 'before-after-table.txt'}")


if __name__ == "__main__":
    main()
