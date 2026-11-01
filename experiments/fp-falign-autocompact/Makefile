.PHONY: help smoke run gapfill gapfill2 plot plot-group-baseline plot-group-fp plot-group-falign \
        plot-group-fpfalign plot-groups all clean-plots

# =============================================================================
# fp-falign-autocompact -- reproduction Makefile
# =============================================================================
# Self-contained: every config, log, and plot this experiment produces lives
# under this directory. See SETUP.md for prerequisites and README.md for the
# experiment design (TASK 3 in ../../../pplacer-workdir/PLAN.md).
#
# Targets:
#   make smoke        -- 4 fast benchmarks x 1 invocation. Builds the 4 new
#                         opam switches (ocaml-5.5-fp, ocaml-5.5-fp-falign,
#                         ocaml-auto-compact-fp, ocaml-auto-compact-fp-falign)
#                         and sanity-checks the harness. Run this FIRST.
#   make run           -- full 8-runtime x full-suite x 3-invocation sweep.
#                         Long (hours) -- reuses switches `make smoke` built.
#   make plot          -- full 8-way heatmaps + summary_stats.txt from the
#                         `run` log directory.
#   make plot-groups   -- one heatmap pair per Tier-B within-group comparison
#                         (baseline / fp / falign / fp+falign), isolating the
#                         auto-compaction effect under each fixed codegen
#                         configuration.
#   make all           -- smoke, run, plot, plot-groups in sequence.
#
# All targets are idempotent: opam switches and benchmark builds are reused
# if already present (running-ng skips existing switches; macro-benches
# build scripts skip already-built benchmarks unless sources changed).
# =============================================================================

HERE          := $(CURDIR)
RUNNING_NG    := $(abspath $(HERE)/../..)
MACRO_BENCH_DIR := $(abspath $(HERE)/../../../macro-benches)
RUN_SCRIPT    := $(RUNNING_NG)/run_ocaml_bench_gc_sweep.sh

ALL_RUNTIMES := ocaml-5.5,ocaml-5.5-fp,ocaml-5.5-falign,ocaml-5.5-fp-falign,ocaml-auto-compact,ocaml-auto-compact-fp,ocaml-auto-compact-falign,ocaml-auto-compact-fp-falign

# `run` (via runbms) creates one timestamped subdirectory per invocation
# under logs/full/ (e.g. lovelace-2026-09-09-Wed-174336/) -- that's where
# the actual .log/olly_*.json files land, NOT logs/full/ itself. Resolve
# it dynamically (newest first) so `plot`/`plot-groups` always point at
# real data instead of silently loading 0 benchmarks.
RUN_DIR := $(shell ls -td $(HERE)/logs/full/*/ 2>/dev/null | head -1)

help:
	@sed -n '1,30p' $(lastword $(MAKEFILE_LIST))

smoke:
	mkdir -p $(HERE)/logs/smoke
	RUNNING_MACRO_BENCH_DIR=$(MACRO_BENCH_DIR) \
	CONFIG_FILE=$(HERE)/config-smoke.yml \
	LOG_DIR=$(HERE)/logs/smoke \
		bash $(RUN_SCRIPT) 2>&1 | tee $(HERE)/logs/smoke_run.log

run:
	mkdir -p $(HERE)/logs/full
	RUNNING_MACRO_BENCH_DIR=$(MACRO_BENCH_DIR) \
	CONFIG_FILE=$(HERE)/config.yml \
	LOG_DIR=$(HERE)/logs/full \
		bash $(RUN_SCRIPT) 2>&1 | tee $(HERE)/logs/full_run.log

gapfill:
	mkdir -p $(HERE)/logs/gapfill
	RUNNING_MACRO_BENCH_DIR=$(MACRO_BENCH_DIR) \
	CONFIG_FILE=$(HERE)/config-gapfill.yml \
	LOG_DIR=$(HERE)/logs/gapfill \
		bash $(RUN_SCRIPT) 2>&1 | tee $(HERE)/logs/gapfill_run.log

gapfill2:
	mkdir -p $(HERE)/logs/gapfill2
	RUNNING_MACRO_BENCH_DIR=$(MACRO_BENCH_DIR) \
	CONFIG_FILE=$(HERE)/config-gapfill2.yml \
	LOG_DIR=$(HERE)/logs/gapfill2 \
		bash $(RUN_SCRIPT) 2>&1 | tee $(HERE)/logs/gapfill2_run.log

plot:
	mkdir -p $(HERE)/plots/full
	python3 $(HERE)/plot_results.py "$(RUN_DIR)" $(HERE)/plots/full $(ALL_RUNTIMES)

plot-group-baseline:
	mkdir -p $(HERE)/plots/group-baseline
	python3 $(HERE)/plot_results.py "$(RUN_DIR)" $(HERE)/plots/group-baseline \
		ocaml-5.5,ocaml-auto-compact

plot-group-fp:
	mkdir -p $(HERE)/plots/group-fp
	python3 $(HERE)/plot_results.py "$(RUN_DIR)" $(HERE)/plots/group-fp \
		ocaml-5.5-fp,ocaml-auto-compact-fp

plot-group-falign:
	mkdir -p $(HERE)/plots/group-falign
	python3 $(HERE)/plot_results.py "$(RUN_DIR)" $(HERE)/plots/group-falign \
		ocaml-5.5-falign,ocaml-auto-compact-falign

plot-group-fpfalign:
	mkdir -p $(HERE)/plots/group-fp-falign
	python3 $(HERE)/plot_results.py "$(RUN_DIR)" $(HERE)/plots/group-fp-falign \
		ocaml-5.5-fp-falign,ocaml-auto-compact-fp-falign

plot-groups: plot-group-baseline plot-group-fp plot-group-falign plot-group-fpfalign

all: smoke run plot plot-groups

# Not run by `all` -- deletes generated plots only (logs and opam switches
# are left alone; re-run `make plot`/`plot-groups` to regenerate).
clean-plots:
	rm -rf $(HERE)/plots/full $(HERE)/plots/group-baseline $(HERE)/plots/group-fp \
	       $(HERE)/plots/group-falign $(HERE)/plots/group-fp-falign
