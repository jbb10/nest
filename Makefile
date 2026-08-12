# Makefile - single source of truth for all repo operations
# Usage: make <target>
#
# Targets:
#   lint         - Run ruff linter
#   format-check - Verify code formatting
#   format       - Auto-format code
#   typecheck    - Run pyright strict mode
#   test         - Run unit/integration tests (excludes e2e)
#   test-e2e     - Run end-to-end tests (requires Docling models)
#   test-all     - Run all tests
#   scan-secrets - Run gitleaks secret scanner on full repo
#   ci           - Full local validation suite (matches GitHub Actions CI)
#
# Releases are cut automatically by release-please in CI - there is no local
# release target. See CONTRIBUTING.md.

.PHONY: lint format-check format typecheck test test-e2e test-all scan-secrets ci

E2E_TIMEOUT ?= 60

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
	uv run pytest -m "e2e" --timeout=$(E2E_TIMEOUT)

test-all: test test-e2e

scan-secrets:
	gitleaks dir --config .gitleaks.toml -v

ci: lint format-check typecheck scan-secrets test-all
