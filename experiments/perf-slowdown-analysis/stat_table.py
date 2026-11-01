#!/usr/bin/env python3
"""Parse perf stat files into a comparison table. Usage: stat_table.py <bench> <rt1> <rt2> ..."""
import sys, re, os
HERE = os.path.dirname(os.path.abspath(__file__))
ST = os.path.join(HERE, "stat")
METRICS = ["task-clock","cycles","instructions","page-faults","cache-references",
           "cache-misses","dTLB-load-misses","context-switches"]
def parse(bench, rt):
    d = {}
    p = os.path.join(ST, f"{bench}__{rt}.stat.txt")
    if not os.path.exists(p): return d
    for line in open(p):
        line=line.strip()
        m = re.match(r"([0-9][0-9,\.]*)\s+(?:cpu_core/)?([a-zA-Z\-]+)/?", line)
        if not m: continue
        val = float(m.group(1).replace(",",""))
        name = m.group(2)
        if name in METRICS and name not in d:   # first (cpu_core) wins
            d[name]=val
    return d
bench=sys.argv[1]; rts=sys.argv[2:]
data={rt:parse(bench,rt) for rt in rts}
base=rts[0]
w=20
hdr="metric".ljust(20)+"".join(rt[:w].rjust(w) for rt in rts)
print(f"\n{bench}: perf stat (Δx vs {base})\n"); print(hdr); print("-"*len(hdr))
def fmt(v):
    if v>=1e9: return f"{v/1e9:.1f}e9"
    if v>=1e6: return f"{v/1e6:.1f}e6"
    if v>=1e3: return f"{v/1e3:.1f}e3"
    return f"{v:.0f}"
for m in METRICS:
    row=m.ljust(20); b=data[base].get(m)
    for rt in rts:
        v=data[rt].get(m)
        if v is None: row+="-".rjust(w); continue
        cell=fmt(v)+(f" ({v/b:.2f}x)" if rt!=base and b else "")
        row+=cell.rjust(w)
    print(row)
# IPC
row="IPC".ljust(20)
for rt in rts:
    c=data[rt].get("cycles"); i=data[rt].get("instructions")
    row+=(f"{i/c:.2f}" if c and i else "-").rjust(w)
print(row)
