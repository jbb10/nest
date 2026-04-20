"""Unit tests for VS Code agent writer."""

from pathlib import Path

from conftest import MockFileSystem
from nest.agents.vscode_writer import VSCodeAgentWriter
from nest.core.paths import AGENT_FILES, TEMPLATE_TO_AGENT_FILE

_AGENTS_FRONTMATTER = (
    "agents: ['nest-master-researcher', 'nest-master-synthesizer', 'nest-master-planner']"
)


# --- render() tests (backward compat, AC6) ---


class TestRender:
    """Tests for the render() method — backward compatible coordinator rendering."""

    def test_render_returns_string(self, mock_filesystem: MockFileSystem) -> None:
        writer = VSCodeAgentWriter(filesystem=mock_filesystem)

        result = writer.render()

        assert isinstance(result, str)

    def test_render_returns_coordinator_content(self, mock_filesystem: MockFileSystem) -> None:
        """AC6: render() returns coordinator template content."""
        writer = VSCodeAgentWriter(filesystem=mock_filesystem)

        result = writer.render()

        assert "name: nest-master-coordinator" in result
        assert _AGENTS_FRONTMATTER in result

    def test_render_contains_no_jinja_variables(self, mock_filesystem: MockFileSystem) -> None:
        writer = VSCodeAgentWriter(filesystem=mock_filesystem)

        result = writer.render()

        assert "{{" not in result
        assert "}}" not in result

    def test_render_does_not_write_to_filesystem(self, mock_filesystem: MockFileSystem) -> None:
        writer = VSCodeAgentWriter(filesystem=mock_filesystem)

        writer.render()

        assert len(mock_filesystem.written_files) == 0
        assert len(mock_filesystem.created_dirs) == 0

    def test_render_matches_generate_output(self, mock_filesystem: MockFileSystem) -> None:
        """AC6: render() produces same content as generate() writes."""
        writer = VSCodeAgentWriter(filesystem=mock_filesystem)
        output_path = Path("/project/.github/agents/nest.agent.md")

        rendered = writer.render()
        writer.generate(output_path)

        assert rendered == mock_filesystem.written_files[output_path]

    def test_render_is_deterministic(self, mock_filesystem: MockFileSystem) -> None:
        writer = VSCodeAgentWriter(filesystem=mock_filesystem)

        result1 = writer.render()
        result2 = writer.render()

        assert result1 == result2


# --- generate() tests (backward compat, AC6) ---


class TestGenerate:
    """Tests for the generate() method — backward compatible single-file generation."""

    def test_generate_creates_coordinator_file(self, mock_filesystem: MockFileSystem) -> None:
        """AC6: generate() writes coordinator file."""
        writer = VSCodeAgentWriter(filesystem=mock_filesystem)
        output_path = Path("/project/.github/agents/nest.agent.md")

        writer.generate(output_path)

        content = mock_filesystem.written_files[output_path]
        assert "name: nest-master-coordinator" in content

    def test_generate_creates_parent_directory(self, mock_filesystem: MockFileSystem) -> None:
        writer = VSCodeAgentWriter(filesystem=mock_filesystem)
        output_path = Path("/project/.github/agents/nest.agent.md")

        writer.generate(output_path)

        assert Path("/project/.github/agents") in mock_filesystem.created_dirs

    def test_generate_skips_directory_creation_if_exists(
        self, mock_filesystem: MockFileSystem
    ) -> None:
        mock_filesystem.existing_paths.add(Path("/project/.github/agents"))
        writer = VSCodeAgentWriter(filesystem=mock_filesystem)
        output_path = Path("/project/.github/agents/nest.agent.md")

        writer.generate(output_path)

        assert Path("/project/.github/agents") not in mock_filesystem.created_dirs

    def test_generate_includes_required_instructions(self, mock_filesystem: MockFileSystem) -> None:
        writer = VSCodeAgentWriter(filesystem=mock_filesystem)
        output_path = Path("/project/.github/agents/nest.agent.md")

        writer.generate(output_path)

        content = mock_filesystem.written_files[output_path]
        assert "00_MASTER_INDEX.md" in content
        assert "_nest_context/" in content
        assert "cite" in content.lower() or "citation" in content.lower()


# --- render_all() tests (AC4) ---


class TestRenderAll:
    """Tests for render_all() — multi-file rendering."""

    def test_render_all_returns_dict_with_four_entries(
        self, mock_filesystem: MockFileSystem
    ) -> None:
        """AC4: render_all() returns dict with 4 entries."""
        writer = VSCodeAgentWriter(filesystem=mock_filesystem)

        result = writer.render_all()

        assert isinstance(result, dict)
        assert len(result) == 4

    def test_render_all_keys_match_agent_files(self, mock_filesystem: MockFileSystem) -> None:
        """AC4: keys match AGENT_FILES list."""
        writer = VSCodeAgentWriter(filesystem=mock_filesystem)

        result = writer.render_all()

        assert set(result.keys()) == set(AGENT_FILES)

    def test_render_all_coordinator_frontmatter(self, mock_filesystem: MockFileSystem) -> None:
        """AC2: coordinator template has agents: frontmatter field."""
        writer = VSCodeAgentWriter(filesystem=mock_filesystem)

        result = writer.render_all()

        coord = result["nest.agent.md"]
        assert "name: nest-master-coordinator" in coord
        assert _AGENTS_FRONTMATTER in coord

    def test_render_all_coordinator_references_index(self, mock_filesystem: MockFileSystem) -> None:
        """AC2: coordinator references .nest/00_MASTER_INDEX.md."""
        writer = VSCodeAgentWriter(filesystem=mock_filesystem)

        result = writer.render_all()

        assert ".nest/00_MASTER_INDEX.md" in result["nest.agent.md"]

    def test_render_all_coordinator_references_glossary(
        self, mock_filesystem: MockFileSystem
    ) -> None:
        """AC2: coordinator references .nest/glossary.md."""
        writer = VSCodeAgentWriter(filesystem=mock_filesystem)

        result = writer.render_all()

        assert ".nest/glossary.md" in result["nest.agent.md"]

    def test_render_all_coordinator_references_nest_context(
        self, mock_filesystem: MockFileSystem
    ) -> None:
        """AC2: coordinator content reading references _nest_context/."""
        writer = VSCodeAgentWriter(filesystem=mock_filesystem)

        result = writer.render_all()

        assert "_nest_context/" in result["nest.agent.md"]

    def test_render_all_subagents_have_user_invocable_false(
        self, mock_filesystem: MockFileSystem
    ) -> None:
        """AC3: all subagent templates have user-invocable: false."""
        writer = VSCodeAgentWriter(filesystem=mock_filesystem)
        subagent_files = [
            "nest-master-researcher.agent.md",
            "nest-master-synthesizer.agent.md",
            "nest-master-planner.agent.md",
        ]

        result = writer.render_all()

        for filename in subagent_files:
            assert "user-invocable: false" in result[filename], (
                f"{filename} missing user-invocable: false"
            )

    def test_render_all_subagent_names_match_coordinator_agents_list(
        self, mock_filesystem: MockFileSystem
    ) -> None:
        """AC3: each subagent has a unique name matching coordinator's agents: list."""
        writer = VSCodeAgentWriter(filesystem=mock_filesystem)

        result = writer.render_all()

        assert "name: nest-master-researcher" in result["nest-master-researcher.agent.md"]
        assert "name: nest-master-synthesizer" in result["nest-master-synthesizer.agent.md"]
        assert "name: nest-master-planner" in result["nest-master-planner.agent.md"]

    def test_render_all_subagents_reference_index(self, mock_filesystem: MockFileSystem) -> None:
        """AC1: all templates reference .nest/00_MASTER_INDEX.md."""
        writer = VSCodeAgentWriter(filesystem=mock_filesystem)
        subagent_files = [
            "nest-master-researcher.agent.md",
            "nest-master-synthesizer.agent.md",
            "nest-master-planner.agent.md",
        ]

        result = writer.render_all()

        for filename in subagent_files:
            assert ".nest/00_MASTER_INDEX.md" in result[filename], (
                f"{filename} missing index reference"
            )

    def test_render_all_subagents_reference_glossary(self, mock_filesystem: MockFileSystem) -> None:
        """AC1: all templates reference .nest/glossary.md."""
        writer = VSCodeAgentWriter(filesystem=mock_filesystem)
        subagent_files = [
            "nest-master-researcher.agent.md",
            "nest-master-synthesizer.agent.md",
            "nest-master-planner.agent.md",
        ]

        result = writer.render_all()

        for filename in subagent_files:
            assert ".nest/glossary.md" in result[filename], f"{filename} missing glossary reference"

    def test_render_all_does_not_write_to_filesystem(self, mock_filesystem: MockFileSystem) -> None:
        writer = VSCodeAgentWriter(filesystem=mock_filesystem)

        writer.render_all()

        assert len(mock_filesystem.written_files) == 0
        assert len(mock_filesystem.created_dirs) == 0


# --- generate_all() tests (AC5) ---


class TestGenerateAll:
    """Tests for generate_all() — multi-file generation."""

    def test_generate_all_writes_four_files(self, mock_filesystem: MockFileSystem) -> None:
        """AC5: generate_all() writes all four agent files."""
        writer = VSCodeAgentWriter(filesystem=mock_filesystem)
        output_dir = Path("/project/.github/agents")

        writer.generate_all(output_dir)

        assert len(mock_filesystem.written_files) == 4
        for agent_file in AGENT_FILES:
            assert output_dir / agent_file in mock_filesystem.written_files

    def test_generate_all_creates_directory_if_missing(
        self, mock_filesystem: MockFileSystem
    ) -> None:
        """AC5: generate_all() creates output directory if it doesn't exist."""
        writer = VSCodeAgentWriter(filesystem=mock_filesystem)
        output_dir = Path("/project/.github/agents")

        writer.generate_all(output_dir)

        assert output_dir in mock_filesystem.created_dirs

    def test_generate_all_skips_directory_creation_if_exists(
        self, mock_filesystem: MockFileSystem
    ) -> None:
        mock_filesystem.existing_paths.add(Path("/project/.github/agents"))
        writer = VSCodeAgentWriter(filesystem=mock_filesystem)
        output_dir = Path("/project/.github/agents")

        writer.generate_all(output_dir)

        assert output_dir not in mock_filesystem.created_dirs

    def test_generate_all_content_matches_render_all(self, mock_filesystem: MockFileSystem) -> None:
        writer = VSCodeAgentWriter(filesystem=mock_filesystem)
        output_dir = Path("/project/.github/agents")

        rendered = writer.render_all()
        writer.generate_all(output_dir)

        for filename, content in rendered.items():
            assert mock_filesystem.written_files[output_dir / filename] == content


# --- Constants tests (AC7) ---


class TestConstants:
    """Tests for agent file constants."""

    def test_agent_files_contains_four_entries(self) -> None:
        """AC7: AGENT_FILES contains all four filenames."""
        assert len(AGENT_FILES) == 4

    def test_agent_files_contains_coordinator(self) -> None:
        assert "nest.agent.md" in AGENT_FILES

    def test_agent_files_contains_all_subagents(self) -> None:
        assert "nest-master-researcher.agent.md" in AGENT_FILES
        assert "nest-master-synthesizer.agent.md" in AGENT_FILES
        assert "nest-master-planner.agent.md" in AGENT_FILES

    def test_template_to_agent_file_maps_four_templates(self) -> None:
        assert len(TEMPLATE_TO_AGENT_FILE) == 4

    def test_template_to_agent_file_coordinator_maps_to_nest_agent(self) -> None:
        """Coordinator template outputs as nest.agent.md (not nest-master-coordinator)."""
        assert TEMPLATE_TO_AGENT_FILE["coordinator.md.jinja"] == "nest.agent.md"
