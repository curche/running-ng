#!/usr/bin/env python3
"""Categorize folded perf stacks into runtime subsystems by leaf symbol and
report weight (period-weighted, proportional to CPU time) per subsystem per
runtime. Usage: subsys.py <bench> <rt1> <rt2> ..."""
import sys, re, glob, os
HERE = os.path.dirname(os.path.abspath(__file__))
FG = os.path.join(HERE, "flamegraphs")

# ordered: first matching category wins. matched against the LEAF (on-CPU) fn.
CATS = [
 ("BLAS/compute", r"dgemm|cblas|openblas|_HASWELL|contract_two|float64_copy|ndarray|owl_stub|__memset|__memcpy|c_float64|caml_uniform_array|blas|lapack"),
 ("GC:mark",      r"do_some_marking|caml_darken|mark_stack|caml_mark|_marking|caml_shrink_mark"),
 ("GC:sweep",     r"pool_sweep|caml_sweep|sweep_slice|_sweep"),
 ("GC:roots",     r"scan_global_roots|caml_scan_stack|caml_do_roots|scan_roots|caml_do_local_roots|oldify"),
 ("GC:minor",     r"minor_heap|empty_minor|caml_minor|stw_empty_minor"),
 ("GC:compact",   r"compact"),
 ("GC:major/misc",r"major_collection_slice|major_gc|caml_gc|caml_major|caml_alloc_shr|caml_shared_heap|pool_alloc|caml_alloc_small|caml_alloc_shr_|caml_add_to_heap|caml_get_pool|_pool"),
 ("GC:finalize",  r"finalize|finalise|caml_final|caml_ba_finalize"),
 ("alloc/ffi",    r"caml_alloc|caml_ba_alloc|caml_c_call|find_frame_descr|caml_call_gc|caml_apply|caml_curry"),
 ("libc/other",   r"__libc|malloc|free|pthread|_dl_|mmap|munmap|madvise|clock|memmove"),
]
def cat(leaf):
    for name, pat in CATS:
        if re.search(pat, leaf):
            return name
    if leaf.startswith("caml") or leaf.startswith("caml_"):
        return "runtime:other"
    return "other/unknown"

def load(bench, rt):
    f = os.path.join(FG, f"{bench}__{rt}.folded")
    tot = {}
    total = 0
    with open(f) as fh:
        for line in fh:
            line = line.rstrip("\n")
            i = line.rfind(" ")
            if i < 0: continue
            stack, w = line[:i], int(line[i+1:])
            leaf = stack.rsplit(";", 1)[-1]
            c = cat(leaf)
            tot[c] = tot.get(c, 0) + w
            total += w
    return tot, total

bench = sys.argv[1]; rts = sys.argv[2:]
data = {}; totals = {}
for rt in rts:
    data[rt], totals[rt] = load(bench, rt)
allcats = sorted({c for rt in rts for c in data[rt]},
                 key=lambda c: -max(data[rt].get(c,0) for rt in rts))
base = rts[0]
w = 22
print(f"\n{bench}: subsystem weight (millions, ~∝ CPU-ms), Δ vs {base}\n")
hdr = "subsystem".ljust(20) + "".join(rt[:w].rjust(w) for rt in rts)
print(hdr); print("-"*len(hdr))
def M(x): return f"{x/1e6:,.0f}"
for c in allcats:
    row = c.ljust(20)
    b = data[base].get(c,0)
    for rt in rts:
        v = data[rt].get(c,0)
        d = v-b
        cell = f"{M(v)}" + (f" ({'+' if d>=0 else ''}{M(d)})" if rt!=base else "")
        row += cell.rjust(w)
    print(row)
print("-"*len(hdr))
row = "TOTAL".ljust(20)
b = totals[base]
for rt in rts:
    v = totals[rt]; d=v-b
    cell = f"{M(v)}" + (f" ({'+' if d>=0 else ''}{M(d)})" if rt!=base else "")
    row += cell.rjust(w)
print(row)
