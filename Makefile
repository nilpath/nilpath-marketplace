VENV := $(HOME)/.virtualenvs/nilpath-marketplace
PYTHON := $(VENV)/bin/python
PYTEST := $(VENV)/bin/pytest

.PHONY: install test test-static test-behavioral

install:
	uv venv $(VENV) --python 3.11
	uv pip install pytest python-frontmatter pyyaml --python $(PYTHON)

test: test-static test-behavioral

test-static:
	$(PYTEST) tests/ -m "not behavioral" -v

test-behavioral:
	$(PYTEST) tests/test_behavioral.py -m behavioral -v -n auto
