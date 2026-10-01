VENV := $(HOME)/.virtualenvs/nilpath-marketplace
PYTHON := $(VENV)/bin/python
PYTEST := $(VENV)/bin/pytest
BUILDKIT := $(VENV)/bin/nilpath-build

.PHONY: install build check validate test test-static test-behavioral

install:
	uv venv $(VENV) --python 3.11
	uv pip install pytest pytest-xdist python-frontmatter pyyaml --python $(PYTHON)
	uv pip install -e tools/buildkit --python $(PYTHON)

build:
	$(BUILDKIT) build

check:
	$(BUILDKIT) check
	$(BUILDKIT) validate

test: test-static test-behavioral

test-static: check
	$(PYTEST) tests/ tools/buildkit/tests/ -m "not behavioral" -v

test-behavioral:
	$(PYTEST) tests/test_behavioral.py -m behavioral -v -n auto
