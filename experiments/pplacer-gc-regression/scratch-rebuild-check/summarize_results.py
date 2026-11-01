#!/usr/bin/env python3
"""Summarize pplacer_testsuite olly JSON sidecars from a running-ng run dir.

Parses the olly_pplacer_testsuite*.json NDJSON sidecars (one JSON line per
invocation) produced by the pplacer_scratch_rebuild_check.yml run, computes
medians across invocations, and prints a table sorted by wall time with a
delta column relative to the stock ocaml-5.5 runtime.

Usage:
    python3 summarize_results.py [run-dir]

run-dir defaults to the sibling turing-2026-07-14-Tue-122822/ directory
(the from-scratch rebuild sanity check run).
"""
import json
import statistics
import sys
from pathlib import Path

RUNTIMES = [
    "ocaml-5.5",
    "ocaml-auto-compact-scratch",
    "socaml-scratch",
    "socaml-auto-compact-scratch",
    "ocaml-auto-compact-fp-scratch",
    "ocaml-auto-compact-flambda-fp-scratch",
    "socaml-auto-compact-fp-scratch",
    "socaml-auto-compact-flambda-scratch",
    "socaml-auto-compact-flambda-fp-scratch",
]

CONFIG_SUFFIX = "perf_grp1.re-25.md-2.macro-pplacer.json"


def main():
    run_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        Path(__file__).parent / "turing-2026-07-14-Tue-122822"
    )

    rows = []
    stock_wall = None
    for rt in RUNTIMES:
        fn = run_dir / f"olly_pplacer_testsuite.0.0.{rt}.{CONFIG_SUFFIX}"
        recs = [json.loads(l) for l in fn.open() if l.strip()]
        wall = statistics.median(r["wall_time"] for r in recs)
        rss = statistics.median(r["max_rss_kb"] / 1024 for r in recs)
        gct = statistics.median(r["gc_time"] for r in recs)
        minor = recs[0]["collections"]["minor"]
        major = recs[0]["collections"]["major"]
        comp = recs[0]["collections"]["compactions"]
        if rt == "ocaml-5.5":
            stock_wall = wall
        rows.append((rt, wall, rss, gct, minor, major, comp))

    rows.sort(key=lambda r: r[1])

    header = (
        f'{"runtime":38} {"wall(s)":>8} {"delta":>8} {"rss(MB)":>8} '
        f'{"gc_time":>8} {"minor":>7} {"major":>7} {"comp":>5}'
    )
    print(header)
    for rt, wall, rss, gct, minor, major, comp in rows:
        delta = (wall / stock_wall - 1) * 100
        print(
            f"{rt:38} {wall:8.2f} {delta:+7.1f}% {rss:8.1f} "
            f"{gct:8.2f} {minor:7d} {major:7d} {comp:5d}"
        )


if __name__ == "__main__":
    main()
