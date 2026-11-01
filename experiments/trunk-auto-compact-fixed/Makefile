.PHONY: help run plot all clean-plots

# =============================================================================
# trunk-auto-compact-fixed -- reproduction Makefile
# =============================================================================
# Re-run of ../trunk-auto-compact-comparison/ after fixing the ppxlib/trunk
# ast_506.ml build gap (see config.yml header and worklog.md). Same 5
# runtimes, full macro-benches suite, 3 invocations.
#
# Targets:
#   make run    -- full 5-runtime x full-suite x 3-invocation sweep.
#   make plot   -- 5-way heatmaps + summary_stats.txt from the `run` log dir.
#   make all    -- run, plot in sequence.
#
# All targets are idempotent: opam switches and benchmark builds are reused
# if already present.
# =============================================================================

HERE          := $(CURDIR)
RUNNING_NG    := $(abspath $(HERE)/../..)
MACRO_BENCH_DIR := $(abspath $(HERE)/../../../macro-benches)
RUN_SCRIPT    := $(RUNNING_NG)/run_ocaml_bench_gc_sweep.sh

ALL_RUNTIMES := ocaml-5.5,ocaml-auto-compact,ocaml-5.5.1,ocaml-trunk,ocaml-auto-compact-trunk

# `run` (via runbms) creates one timestamped subdirectory per invocation
# under logs/full/ -- that's where the actual .log/olly_*.json files land,
# NOT logs/full/ itself. Resolve it dynamically (newest first).
RUN_DIR := $(shell ls -td $(HERE)/logs/full/*/ 2>/dev/null | head -1)

help:
	@sed -n '1,20p' $(lastword $(MAKEFILE_LIST))

run:
	mkdir -p $(HERE)/logs/full
	RUNNING_MACRO_BENCH_DIR=$(MACRO_BENCH_DIR) \
	CONFIG_FILE=$(HERE)/config.yml \
	LOG_DIR=$(HERE)/logs/full \
		bash $(RUN_SCRIPT) 2>&1 | tee $(HERE)/logs/full_run.log

plot:
	mkdir -p $(HERE)/plots/full
	python3 $(HERE)/plot_results.py "$(RUN_DIR)" $(HERE)/plots/full $(ALL_RUNTIMES)

all: run plot

clean-plots:
	rm -rf $(HERE)/plots/full
