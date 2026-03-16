# Makefile — single source of truth for all repo operations
# Usage: make <target>
#
# Targets:
#   lint         — Run ruff linter
#   format-check — Verify code formatting
#   format       — Auto-format code
#   typecheck    — Run pyright strict mode
#   test         — Run unit/integration tests (excludes e2e)
#   test-e2e     — Run end-to-end tests (requires Docling models)
#   test-all     — Run all tests
#   ci           — Full pre-release validation suite
#   release      — Run release script

.PHONY: lint format-check format typecheck test test-e2e test-all ci release

lint:
	uv run ruff check .

format-check:
	uv run ruff format --check .

format:
	uv run ruff format .

typecheck:
	uv run pyright

test:
	uv run pytest tests/ -v --ignore=tests/e2e

test-e2e:
	uv run pytest -m "e2e" --timeout=60

test-all: test test-e2e

ci: lint format-check typecheck test-all

release:
	./scripts/release.sh --yes
