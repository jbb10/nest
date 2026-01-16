"""VS Code Custom Agent file generator."""

from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from nest.adapters.protocols import FileSystemProtocol


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

    def generate(self, project_name: str, output_path: Path) -> None:
        """Generate VS Code agent file.

        Args:
            project_name: Project name to interpolate into template.
            output_path: Path to write agent file
                (e.g., .github/agents/nest.agent.md).

        Raises:
            IOError: If directory cannot be created or file cannot be written.
        """
        # Ensure parent directory exists
        output_dir = output_path.parent
        if not self._filesystem.exists(output_dir):
            self._filesystem.create_directory(output_dir)

        # Render template
        template = self._jinja_env.get_template("vscode.md.jinja")
        content = template.render(project_name=project_name)

        # Write file
        self._filesystem.write_text(output_path, content)
