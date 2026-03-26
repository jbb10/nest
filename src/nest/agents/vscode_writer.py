"""VS Code Custom Agent file generator."""

from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from nest.adapters.protocols import FileSystemProtocol
from nest.core.paths import TEMPLATE_TO_AGENT_FILE


class VSCodeAgentWriter:
    """Generates VS Code Custom Agent files from Jinja2 templates."""

    def __init__(self, filesystem: FileSystemProtocol):
        """Initialize writer with filesystem adapter.

        Args:
            filesystem: Filesystem adapter for directory/file operations.
        """
        self._filesystem = filesystem
        self._jinja_env = Environment(
            loader=PackageLoader("nest.agents", "templates"),
            autoescape=select_autoescape(),
        )

    def render(self) -> str:
        """Render coordinator agent template to string without writing to disk.

        Returns:
            Rendered coordinator template content as string.
        """
        template = self._jinja_env.get_template("coordinator.md.jinja")
        return template.render()

    def generate(self, output_path: Path) -> None:
        """Generate coordinator VS Code agent file.

        Args:
            output_path: Path to write agent file
                (e.g., .github/agents/nest.agent.md).

        Raises:
            IOError: If directory cannot be created or file cannot be written.
        """
        # Ensure parent directory exists
        output_dir = output_path.parent
        if not self._filesystem.exists(output_dir):
            self._filesystem.create_directory(output_dir)

        content = self.render()
        self._filesystem.write_text(output_path, content)

    def render_all(self) -> dict[str, str]:
        """Render all agent templates to strings without writing to disk.

        Returns:
            Dictionary mapping agent filenames to rendered content.
        """
        result: dict[str, str] = {}
        for template_name, agent_filename in TEMPLATE_TO_AGENT_FILE.items():
            template = self._jinja_env.get_template(template_name)
            result[agent_filename] = template.render()
        return result

    def generate_all(self, output_dir: Path) -> None:
        """Generate all agent files to specified directory.

        Args:
            output_dir: Directory where agent files should be written.

        Raises:
            IOError: If directory cannot be created or files cannot be written.
        """
        if not self._filesystem.exists(output_dir):
            self._filesystem.create_directory(output_dir)
        for filename, content in self.render_all().items():
            self._filesystem.write_text(output_dir / filename, content)
