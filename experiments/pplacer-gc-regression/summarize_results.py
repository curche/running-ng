#!/usr/bin/env python3
"""Summarize pplacer_testsuite olly JSON sidecars from a running-ng run dir.

Auto-discovers every runtime present in the given run directory by globbing
for olly_pplacer_testsuite.0.0.<runtime>.<config-suffix>.json sidecars
(NDJSON, one JSON line per invocation), computes medians across invocations,
and prints a table sorted by wall time with a delta column relative to the
stock ocaml-5.5 runtime (or the fastest runtime present, if ocaml-5.5 isn't
in this particular run).

Works for any pplacer_testsuite run directory produced by running-ng in this
investigation (pplacer_gc_regression.yml, pplacer_flambda_fp_check.yml,
pplacer_scratch_rebuild_check.yml, ...) regardless of which specific
runtimes/configs it contains.

Usage:
    python3 summarize_results.py <run-dir>
"""
import json
import re
import statistics
import sys
from pathlib import Path

FILENAME_RE = re.compile(
    r"^olly_pplacer_testsuite\.0\.0\.(?P<runtime>.+?)\.(?P<config>perf_grp\d+\..*)\.json$"
)


def discover_runtimes(run_dir: Path):
    found = {}
    for fn in sorted(run_dir.glob("olly_pplacer_testsuite.0.0.*.json")):
        m = FILENAME_RE.match(fn.name)
        if m:
            found[m.group("runtime")] = fn
    return found


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    run_dir = Path(sys.argv[1])

    runtime_files = discover_runtimes(run_dir)
    if not runtime_files:
        print(f"No olly_pplacer_testsuite*.json sidecars found in {run_dir}")
        sys.exit(1)

    rows = []
    for rt, fn in runtime_files.items():
        recs = [json.loads(l) for l in fn.open() if l.strip()]
        wall = statistics.median(r["wall_time"] for r in recs)
        rss = statistics.median(r["max_rss_kb"] / 1024 for r in recs)
        gct = statistics.median(r["gc_time"] for r in recs)
        minor = recs[0]["collections"]["minor"]
        major = recs[0]["collections"]["major"]
        comp = recs[0]["collections"]["compactions"]
        rows.append((rt, wall, rss, gct, minor, major, comp))

    rows.sort(key=lambda r: r[1])
    stock_wall = next((r[1] for r in rows if r[0] == "ocaml-5.5"), rows[0][1])

    name_width = max(len(r[0]) for r in rows) + 1
    header = (
        f'{"runtime":{name_width}} {"wall(s)":>8} {"delta":>8} {"rss(MB)":>8} '
        f'{"gc_time":>8} {"minor":>7} {"major":>7} {"comp":>5}'
    )
    print(header)
    for rt, wall, rss, gct, minor, major, comp in rows:
        delta = (wall / stock_wall - 1) * 100
        print(
            f"{rt:{name_width}} {wall:8.2f} {delta:+7.1f}% {rss:8.1f} "
            f"{gct:8.2f} {minor:7d} {major:7d} {comp:5d}"
        )


if __name__ == "__main__":
    main()
