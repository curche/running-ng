# Benchmark Plan: Compactor Comparison Experiment

## Goal

Isolate the performance impact of two independent changes to OCaml 5.5:

1. **New chunk-based compactor** (`socaml-git` `new_compactor` branch)
2. **Automatic compaction** (`automatic-compactor-oxcaml.patch`, ported to both repos)

By crossing them we get four runtimes and three independent comparisons.

---

## Four runtimes

| Config name | Description | Source | Opam switch |
|---|---|---|---|
| `ocaml-5.5` | Stock OCaml 5.5.0 | upstream tag `5.5.0` | via `version:` in running-ng |
| `ocaml-auto-compact` | Stock OCaml + automatic compaction only | `ocaml-git` branch `auto-compact-5.5` | `ocaml-auto-compact-<timestamp>` |
| `socaml` | New chunk-based compactor only | `socaml-git` commit `7f6d55c648` | `socaml-20260630-140841` |
| `socaml-auto-compact` | New compactor + automatic compaction | `socaml-git` commit `34988cfd7b` | `socaml-auto-compact-20260629-131142` |

---

## YAML config structure

```yaml
runtimes:
  ocaml-5.5:
    type: OCaml
    version: "5.5.0"

  ocaml-auto-compact:
    type: OCaml
    executable: /home/curche/.opam/ocaml-auto-compact-<timestamp>/bin

  socaml:
    type: OCaml
    executable: /home/curche/.opam/socaml-20260630-140841/bin

  socaml-auto-compact:
    type: OCaml
    executable: /home/curche/.opam/socaml-auto-compact-20260629-131142/bin

configs:
  - "ocaml-5.5|perf_grp1|re-25|md-2"
  - "ocaml-auto-compact|perf_grp1|re-25|md-2"
  - "socaml|perf_grp1|re-25|md-2"
  - "socaml-auto-compact|perf_grp1|re-25|md-2"

comparisons:
  # Effect of automatic compaction alone (no new compactor)
  - baseline: "ocaml-5.5|perf_grp1|re-25|md-2"
    experiment: "ocaml-auto-compact|perf_grp1|re-25|md-2"
    name: "auto-compact-only"

  # Effect of new compactor alone (no automatic compaction)
  - baseline: "ocaml-5.5|perf_grp1|re-25|md-2"
    experiment: "socaml|perf_grp1|re-25|md-2"
    name: "new-compactor-only"

  # Adding automatic compaction on top of new compactor
  - baseline: "socaml|perf_grp1|re-25|md-2"
    experiment: "socaml-auto-compact|perf_grp1|re-25|md-2"
    name: "auto-compact-on-new-compactor"

  # Combined effect of both changes (sanity / cross-check)
  - baseline: "ocaml-5.5|perf_grp1|re-25|md-2"
    experiment: "socaml-auto-compact|perf_grp1|re-25|md-2"
    name: "both-changes-combined"
```

---

## Prerequisites before running

- [ ] Finish `ocaml-auto-compact` opam switch:
  - Commit all changes on `auto-compact-5.5` branch in `ocaml-git`
  - Rebuild switch so `sys.ml` is regenerated from committed source
  - Verify `ocamlopt --version` → `5.5.0+ocaml-auto-compact`
  - Install dune/ocamlfind in that switch
- [ ] Confirm dune/ocamlfind present in `socaml-20260630-140841` and `socaml-auto-compact-20260629-131142`
- [ ] Fill in the actual timestamp in the `ocaml-auto-compact` executable path

---

## Follow-on: OCAMLRUNPARAM sweep

Once baselines are established, run a parameter sweep on `O=` (max_overhead)
across both auto-compact runtimes to find the optimal threshold:

Suggested values: `O=100`, `O=200`, `O=500` (default), `O=1000`, `O=2000`,
`O=999999` (effectively disabled).

This identifies the compaction aggressiveness that minimises runtime without
excessive GC pause overhead.
