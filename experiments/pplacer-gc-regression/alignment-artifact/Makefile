# Padding experiment: does adding functionally-inert code to major_gc.c
# reproduce the ocaml-auto-compact-fp regression via code-layout alone?
# See plan-alignment-artifact.md.

ROOT_DIR := $(abspath ../../..)
RUNNING_MACRO_BENCH_DIR := /home/curche/git/macro-benches
OLLY_BIN := /home/curche/git/runtime_events_tools/_build/install/default/bin
CONFIG := $(ROOT_DIR)/src/running/config/experiments/pplacer_alignment_check.yml
LOG_DIR := $(abspath logs)

export RUNNING_MACRO_BENCH_DIR
export PYTHONPATH := $(ROOT_DIR)/src
export PATH := $(OLLY_BIN):$(PATH)

.PHONY: validate run summarize clean

validate:
	cd $(ROOT_DIR) && python3 -c "\
from pathlib import Path; \
from running.config import Configuration; \
c = Configuration.from_file(Path('.'), 'src/running/config/experiments/pplacer_alignment_check.yml'); \
c.validate(); \
c.validate_tags(); \
print('OK - configs:', len(c.get('configs'))); \
[print(' ', x) for x in c.get('configs')]"

run: validate
	mkdir -p $(LOG_DIR)
	cd $(ROOT_DIR) && python3 -m running runbms $(LOG_DIR) $(CONFIG) \
		2>&1 | tee $(LOG_DIR)/run_stdout.log

summarize:
	@latest=$$(ls -dt $(LOG_DIR)/turing-* 2>/dev/null | head -1); \
	if [ -z "$$latest" ]; then echo "No run directory found under $(LOG_DIR)"; exit 1; fi; \
	echo "Summarizing $$latest"; \
	python3 $(ROOT_DIR)/experiments/pplacer-gc-regression/summarize_results.py "$$latest"

clean:
	rm -rf $(LOG_DIR)/turing-* $(LOG_DIR)/run_stdout.log
