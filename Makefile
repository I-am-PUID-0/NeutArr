POETRY ?= poetry
POETRY_RUN ?= $(POETRY) run
PYTHON ?= $(POETRY_RUN) python
RUFF ?= $(POETRY_RUN) ruff
PRE_COMMIT ?= $(POETRY_RUN) pre-commit
BANDIT ?= $(POETRY_RUN) bandit
PIP_AUDIT ?= $(POETRY_RUN) pip-audit

.PHONY: help install lint format format-check test compile security verify pre-commit-install

help:
	@printf '%s\n' \
		'NeutArr development targets:' \
		'  make install              Install project dependencies with Poetry' \
		'  make lint                 Run Ruff lint checks' \
		'  make format               Format Python files with Ruff' \
		'  make format-check         Check Python formatting with Ruff' \
		'  make test                 Run unittest discovery' \
		'  make compile              Compile Python files as a smoke check' \
		'  make verify               Run lint, format-check, compile, and tests' \
		'  make security             Run Bandit and pip-audit security checks' \
		'  make pre-commit-install   Install git hooks'

install:
	$(POETRY) install --no-root --with dev

lint:
	$(RUFF) check .

format:
	$(RUFF) format .

format-check:
	$(RUFF) format --check .

test:
	$(PYTHON) -m unittest discover -s tests

compile:
	$(PYTHON) -m compileall -q src main.py tests

security:
	$(BANDIT) -r src/ main.py -ll
	$(PIP_AUDIT)

verify: lint format-check compile test

pre-commit-install:
	$(PRE_COMMIT) install
	$(PRE_COMMIT) install --hook-type pre-push
