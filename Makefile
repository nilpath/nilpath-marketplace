VENV := $(HOME)/.virtualenvs/nilpath-marketplace
PYTHON := $(VENV)/bin/python
PYTEST := $(VENV)/bin/pytest

# LM Studio backend defaults — override on the command line if your setup differs.
# Prerequisite: LM Studio (and any required Anthropic-compatible proxy such as
# claude-code-router or litellm) must already be running locally.
LMSTUDIO_BASE_URL ?= http://localhost:1234
LMSTUDIO_AUTH_TOKEN ?= lm-studio
LMSTUDIO_AGENT_MODEL ?= local-agent-model
LMSTUDIO_JUDGE_MODEL ?= local-judge-model

.PHONY: install test test-static test-behavioral test-behavioral-lmstudio

install:
	uv venv $(VENV) --python 3.11
	uv pip install pytest python-frontmatter pyyaml --python $(PYTHON)

test: test-static test-behavioral

test-static:
	$(PYTEST) tests/ -m "not behavioral" -v

test-behavioral:
	$(PYTEST) tests/test_behavioral.py -m behavioral -v -n auto

# Run the same behavioural test suite against a local LM Studio backend.
# Override env vars per invocation, e.g.:
#   make test-behavioral-lmstudio LMSTUDIO_AGENT_MODEL=qwen2.5-coder LMSTUDIO_JUDGE_MODEL=llama-3.2-3b
test-behavioral-lmstudio:
	ANTHROPIC_BASE_URL=$(LMSTUDIO_BASE_URL) \
	ANTHROPIC_AUTH_TOKEN=$(LMSTUDIO_AUTH_TOKEN) \
	ANTHROPIC_MODEL=$(LMSTUDIO_AGENT_MODEL) \
	JUDGE_MODEL=$(LMSTUDIO_JUDGE_MODEL) \
	$(PYTEST) tests/test_behavioral.py -m behavioral -v -n auto
