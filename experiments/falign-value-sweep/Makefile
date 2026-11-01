.PHONY: help run plot deep-dive-pplacer all clean-plots

# =============================================================================
# falign-value-sweep -- does a smaller -falign-functions value fix pplacer
# without losing frama_c_eva_sqlite/menhir_sql_parser's wins?
# =============================================================================
# Follow-up to ../pplacer-falign-deep-dive/. See config.yml and results.md.
#
# Targets:
#   make run              -- builds falign16/falign32 switches (new), reuses
#                             stock + falign64, runs the 6-benchmark subset,
#                             5 invocations.
#   make plot              -- heatmaps + tables from the run.
#   make deep-dive-pplacer -- pinned perf stat -r N + topdown, all 4
#                             alignment values, pplacer_testsuite only
#                             (mirrors ../pplacer-falign-deep-dive/'s rigor).
#   make all               -- run, plot, deep-dive-pplacer in sequence.
# =============================================================================

HERE          := $(CURDIR)
RUNNING_NG    := $(abspath $(HERE)/../..)
MACRO_BENCH_DIR := $(abspath $(HERE)/../../../macro-benches)
RUN_SCRIPT    := $(RUNNING_NG)/run_ocaml_bench_gc_sweep.sh

ALL_RUNTIMES := ocaml-5.5,ocaml-5.5-falign16,ocaml-5.5-falign32,ocaml-5.5-falign

RUN_DIR := $(shell ls -td $(HERE)/logs/run/*/ 2>/dev/null | head -1)

help:
	@sed -n '1,25p' $(lastword $(MAKEFILE_LIST))

run:
	mkdir -p $(HERE)/logs/run
	RUNNING_MACRO_BENCH_DIR=$(MACRO_BENCH_DIR) \
	CONFIG_FILE=$(HERE)/config.yml \
	LOG_DIR=$(HERE)/logs/run \
		bash $(RUN_SCRIPT) 2>&1 | tee $(HERE)/logs/run.log

plot:
	mkdir -p $(HERE)/plots/full
	python3 $(HERE)/plot_results.py "$(RUN_DIR)" $(HERE)/plots/full $(ALL_RUNTIMES)

deep-dive-pplacer:
	bash $(HERE)/pplacer_deep_dive.sh

all: run plot deep-dive-pplacer

clean-plots:
	rm -rf $(HERE)/plots/full
