"""E2E tests for AI glossary generation (Story 6.7).

Tests verify that sync with a real LLM produces a glossary with
AI-defined terms and respects the --no-ai flag.
All tests are gated by AI API key availability.
"""

from pathlib import Path

import pytest

from .conftest import ai_env_vars, run_cli, skip_without_ai

_GLOSSARY_CONTENT_1 = """\
# Alpha Project Overview

The Alpha Project is a cloud migration initiative led by the PDC (Project Delivery Committee).
Our SME team has identified 47 legacy systems requiring migration to Azure.
The SOW covers three phases: assessment, migration, and validation.
"""

_GLOSSARY_CONTENT_2 = """\
Q3 Planning Meeting Notes - 2026-02-15

Attendees: Sarah (VP Engineering), PDC members, SME leads
The SOW amendment for Phase 2 was approved by the PDC.
Key decision: migrate CRM database first, then ERP system.
Target completion: Q4 2026.
"""


@pytest.mark.e2e
class TestAIGlossaryE2E:
    """E2E tests for AI-powered glossary generation."""

    @skip_without_ai
    def test_sync_produces_glossary_with_ai_definitions(self, initialized_project: Path) -> None:
        """AC7: Sync with AI creates glossary with AI-defined terms."""
        project_dir = initialized_project
        sources_dir = project_dir / "_nest_sources"

        (sources_dir / "contracts").mkdir(parents=True, exist_ok=True)
        (sources_dir / "contracts" / "overview.md").write_text(_GLOSSARY_CONTENT_1)
        (sources_dir / "contracts" / "notes.txt").write_text(_GLOSSARY_CONTENT_2)

        result = run_cli(["sync"], cwd=project_dir, timeout=120, env=ai_env_vars())
        assert result.exit_code == 0, f"Sync failed: {result.stderr}\n{result.stdout}"

        glossary_path = project_dir / "_nest_context" / "glossary.md"
        assert glossary_path.exists(), "glossary.md should be created by AI sync"

        glossary_content = glossary_path.read_text()
        assert "<!-- nest:glossary-start -->" in glossary_content
        assert "<!-- nest:glossary-end -->" in glossary_content

        # Extract table between markers
        start = glossary_content.find("<!-- nest:glossary-start -->")
        end = glossary_content.find("<!-- nest:glossary-end -->")
        table_section = glossary_content[start:end]

        # Should have at least one data row (with | separators, not header/separator)
        data_rows = [
            line
            for line in table_section.splitlines()
            if line.startswith("|") and "---" not in line and "Term" not in line
        ]
        assert len(data_rows) >= 1, "Expected at least one glossary term row"

        # Check that rows have non-empty Category and Definition values.
        for row in data_rows:
            parts = [p.strip() for p in row.split("|")]
            # Typical: ['', 'Term', 'Category', 'Definition', '']
            term = parts[1] if len(parts) > 1 else ""
            category = parts[2] if len(parts) > 2 else ""
            definition = parts[3] if len(parts) > 3 else ""
            assert term, f"Glossary row missing term: {row}"
            assert category, f"Glossary row missing category: {row}"
            assert definition, f"Glossary row missing definition: {row}"

    @skip_without_ai
    def test_sync_no_ai_flag_skips_glossary(self, initialized_project: Path) -> None:
        """AC9: --no-ai flag prevents glossary creation."""
        project_dir = initialized_project
        sources_dir = project_dir / "_nest_sources"

        (sources_dir / "contracts").mkdir(parents=True, exist_ok=True)
        (sources_dir / "contracts" / "overview.md").write_text(_GLOSSARY_CONTENT_1)

        result = run_cli(["sync", "--no-ai"], cwd=project_dir, timeout=120, env=ai_env_vars())
        assert result.exit_code == 0, f"Sync failed: {result.stderr}\n{result.stdout}"

        glossary_path = project_dir / "_nest_context" / "glossary.md"
        assert not glossary_path.exists(), "glossary.md should NOT exist with --no-ai"
