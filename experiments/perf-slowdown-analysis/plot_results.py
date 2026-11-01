#!/usr/bin/env python3
"""Summary plots for TASK 2 perf analysis. Reads perf stat + folded files."""
import os, re
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
HERE=os.path.dirname(os.path.abspath(__file__)); PL=os.path.join(HERE,"plots"); os.makedirs(PL,exist_ok=True)
ST=os.path.join(HERE,"stat"); FG=os.path.join(HERE,"flamegraphs")

def stat(bench,rt,metric):
    p=os.path.join(ST,f"{bench}__{rt}.stat.txt")
    if not os.path.exists(p): return None
    for l in open(p):
        m=re.match(r"\s*([0-9][0-9,\.]*)\s+(?:cpu_core/)?"+re.escape(metric),l)
        if m: return float(m.group(1).replace(",",""))
    return None

# ---- Plot 1: instruction ratio vs stock (the honest "is it slower?" metric) ----
benches=["owl_gc","zarith_pi","ocamlc_self_compile","pplacer_testsuite","cpdf_squeeze","test_decompress"]
rts=["socaml","socaml-auto-compact"]
fig,ax=plt.subplots(figsize=(11,5.5))
x=np.arange(len(benches)); w=0.38
for i,rt in enumerate(rts):
    vals=[]
    for b in benches:
        s=stat(b,"ocaml-5.5","instructions"); v=stat(b,rt,"instructions")
        vals.append(v/s if s and v else np.nan)
    bars=ax.bar(x+(i-0.5)*w,vals,w,label=rt)
    for bx,val in zip(bars,vals):
        if not np.isnan(val): ax.text(bx.get_x()+bx.get_width()/2,val+0.02,f"{val:.2f}",ha="center",fontsize=8)
ax.axhline(1.0,color="k",lw=0.8,ls="--")
ax.set_xticks(x); ax.set_xticklabels(benches,rotation=20,ha="right")
ax.set_ylabel("instructions retired  (patched / stock)")
ax.set_title("Real cost of the patch: instruction count vs stock ocaml-5.5\n(=1.0 means identical work; only owl_gc regresses, zarith speeds up)")
ax.legend(); ax.set_ylim(0,2.9); fig.tight_layout(); fig.savefig(os.path.join(PL,"instruction_ratio.png"),dpi=130); plt.close(fig)

# ---- Plot 2: owl subsystem stacked bar across 4 runtimes ----
def subsys(bench,rt):
    from collections import defaultdict
    CATS=[("BLAS/compute",r"dgemm|cblas|_HASWELL|contract_two|float64_copy|ndarray|owl_stub|__memset|__memcpy|c_float64|caml_uniform_array"),
          ("GC:mark",r"do_some_marking|caml_darken|mark_stack|caml_mark|_marking"),
          ("GC:roots",r"scan_global_roots|caml_scan_stack|caml_do_roots|scan_roots|oldify|mark_roots"),
          ("GC:sweep",r"pool_sweep|caml_sweep|_sweep"),
          ("GC:compact",r"compact")]
    def cat(leaf):
        for n,p in CATS:
            if re.search(p,leaf): return n
        return "other"
    tot=defaultdict(float)
    p=os.path.join(FG,f"{bench}__{rt}.folded")
    for l in open(p):
        i=l.rfind(" "); leaf=l[:i].rsplit(";",1)[-1]; tot[cat(leaf)]+=float(l[i+1:])
    return tot
order=["BLAS/compute","GC:mark","GC:roots","GC:sweep","GC:compact","other"]
colors={"BLAS/compute":"#4c78a8","GC:mark":"#e45756","GC:roots":"#f58518","GC:sweep":"#b279a2","GC:compact":"#54a24b","other":"#bab0ac"}
rts4=["ocaml-5.5","ocaml-auto-compact","socaml","socaml-auto-compact"]
data={rt:subsys("owl_gc",rt) for rt in rts4}
fig,ax=plt.subplots(figsize=(9,5.5)); xb=np.arange(len(rts4)); bottom=np.zeros(len(rts4))
for cat in order:
    vals=np.array([data[rt].get(cat,0)/1e9 for rt in rts4])
    ax.bar(xb,vals,0.6,bottom=bottom,label=cat,color=colors[cat]); bottom+=vals
ax.set_xticks(xb); ax.set_xticklabels(rts4,rotation=15,ha="right")
ax.set_ylabel("CPU cycles (billions, period-weighted)")
ax.set_title("owl_gc: where the time goes, per runtime\n(BLAS compute is flat; the regression is entirely GC mark+roots / compaction)")
ax.legend(loc="upper left",fontsize=9); fig.tight_layout(); fig.savefig(os.path.join(PL,"owl_subsystem.png"),dpi=130); plt.close(fig)
print("wrote plots/instruction_ratio.png, plots/owl_subsystem.png")
