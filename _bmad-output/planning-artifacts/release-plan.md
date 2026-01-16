# Release Plan: v0.1.0 (Beta)

**Target Version:** `0.1.0`
**Current Version:** `1.0.0` (Placeholder)
**Release Type:** Initial Beta Release

## 1. Version Adjustment
The current placeholder version `1.0.0` will be reset to `0.1.0` to reflect the Beta status of the software. This aligns with Semantic Versioning for initial development releases.

**Files to Update:**
- `pyproject.toml`: `version = "0.1.0"`
- `src/nest/__init__.py`: `__version__ = "0.1.0"`

## 2. Pre-flight Validation
Ensure codebase quality before tagging.

- **Tests:** `uv run pytest` (Must pass 100%)
- **Linting:** `uv run ruff check src` (No errors)
- **Type Checking:** `uv run pyright src` (Strict mode compliance)

## 3. Documentation & Artifacts
- **Changelog:** Generate initial `CHANGELOG.md` using `git-cliff` (or manual creation if tool missing).
- **Build:** Generate distribution artifacts (`.whl`, `.tar.gz`) using `uv build`.

## 4. Release Execution
1.  Create release branch: `chore/release-v0.1.0`
2.  Apply version updates.
3.  Commit: `chore(release): prepare v0.1.0 beta`
4.  Tag: `git tag -a v0.1.0 -m "Release v0.1.0 Beta"`
5.  Merge to `main`.

## 5. Post-Release
- Deploy/Publish artifacts (if applicable).
- Update `sprint-status.yaml` to reflect milestone completion.
