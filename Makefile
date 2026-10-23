VENV := $(HOME)/.virtualenvs/nilpath-marketplace
PYTHON := $(VENV)/bin/python
PYTEST := $(VENV)/bin/pytest
BUILDKIT := $(VENV)/bin/nilpath-build
export PYTHONPATH := $(CURDIR)/tools/buildkit/src

.PHONY: install build check validate test test-static test-behavioral viewer-build viewer-check viewer-test

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

viewer-build:
	npm --prefix tools/visual-viewer run build

viewer-check:
	npm --prefix tools/visual-viewer run check

viewer-test:
	$(PYTEST) tests/test_nstack_viewer.py -q
