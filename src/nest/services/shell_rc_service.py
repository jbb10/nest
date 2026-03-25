"""Service for managing shell RC file AI configuration blocks.

Handles detection of user's shell, resolution of the correct RC file path,
and idempotent writing/removal of env var export blocks.
"""

import logging
import os
import sys
from pathlib import Path

BLOCK_START = "# --- Nest AI Configuration (managed by `nest config ai`) ---"
BLOCK_END = "# --- End Nest AI Configuration ---"

logger = logging.getLogger(__name__)


class ShellRCService:
    """Service for managing shell RC file AI configuration blocks."""

    def detect_shell(self) -> str:
        """Detect current shell from $SHELL environment variable.

        Returns:
            Shell name: "zsh", "bash", "fish", or "unknown".
        """
        shell_path = os.environ.get("SHELL", "")
        shell_name = Path(shell_path).name if shell_path else ""
        if shell_name in ("zsh", "bash", "fish"):
            return shell_name
        return "unknown"

    def resolve_rc_path(self, shell: str) -> Path:
        """Resolve the correct RC file path for the given shell.

        Args:
            shell: Shell name from detect_shell().

        Returns:
            Path to the shell RC file.
        """
        home = Path.home()
        if shell == "zsh":
            return home / ".zshrc"
        if shell == "bash":
            if sys.platform == "darwin":
                bash_profile = home / ".bash_profile"
                if bash_profile.exists():
                    return bash_profile
            return home / ".bashrc"
        if shell == "fish":
            return home / ".config" / "fish" / "config.fish"
        # fallback
        return home / ".profile"

    @staticmethod
    def _escape_shell_value(value: str) -> str:
        """Escape a value for safe inclusion in a double-quoted shell string.

        Escapes backslashes, double quotes, backticks, and dollar signs
        to prevent shell injection when the RC file is sourced.

        Args:
            value: Raw value to escape.

        Returns:
            Shell-safe escaped value.
        """
        value = value.replace("\\", "\\\\")
        value = value.replace('"', '\\"')
        value = value.replace("`", "\\`")
        value = value.replace("$", "\\$")
        return value

    def generate_config_block(
        self,
        endpoint: str,
        model: str,
        api_key: str,
        shell: str,
    ) -> str:
        """Generate the shell config block with env var exports.

        Args:
            endpoint: API endpoint URL.
            model: Model/deployment name.
            api_key: API key value.
            shell: Shell type for syntax selection.

        Returns:
            Complete config block string including sentinel comments.
        """
        # Escape double quotes and backslashes in values for shell safety
        safe_endpoint = self._escape_shell_value(endpoint)
        safe_model = self._escape_shell_value(model)
        safe_key = self._escape_shell_value(api_key)

        if shell == "fish":
            lines = [
                BLOCK_START,
                f'set -gx NEST_BASE_URL "{safe_endpoint}"',
                f'set -gx NEST_TEXT_MODEL "{safe_model}"',
                f'set -gx NEST_API_KEY "{safe_key}"',
                BLOCK_END,
            ]
        else:
            lines = [
                BLOCK_START,
                f'export NEST_BASE_URL="{safe_endpoint}"',
                f'export NEST_TEXT_MODEL="{safe_model}"',
                f'export NEST_API_KEY="{safe_key}"',
                BLOCK_END,
            ]
        return "\n".join(lines) + "\n"

    def write_config(
        self,
        rc_path: Path,
        endpoint: str,
        model: str,
        api_key: str,
        shell: str,
    ) -> None:
        """Write or replace the Nest AI config block in the RC file.

        Creates the file and parent directories if they don't exist.
        If a config block already exists, replaces it in-place.
        If no block exists, appends to end of file.

        Args:
            rc_path: Path to the shell RC file.
            endpoint: API endpoint URL.
            model: Model/deployment name.
            api_key: API key value.
            shell: Shell type for syntax selection.
        """
        block = self.generate_config_block(endpoint, model, api_key, shell)

        try:
            if not rc_path.exists():
                rc_path.parent.mkdir(parents=True, exist_ok=True)
                rc_path.write_text(block, encoding="utf-8")
                return

            content = rc_path.read_text(encoding="utf-8")
            new_content = self._replace_or_append_block(content, block)
            rc_path.write_text(new_content, encoding="utf-8")
        except PermissionError:
            logger.error("Permission denied writing to %s", rc_path)
            msg = f"Permission denied: cannot write to {rc_path}"
            raise PermissionError(msg) from None
        except OSError as exc:
            logger.error("Failed to write RC file %s: %s", rc_path, exc)
            msg = f"Failed to write RC file {rc_path}: {exc}"
            raise OSError(msg) from exc

    def _replace_or_append_block(self, content: str, block: str) -> str:
        """Replace existing config block or append new one.

        Args:
            content: Current file content.
            block: New config block to insert.

        Returns:
            Updated file content.
        """
        start_idx = content.find(BLOCK_START)
        end_idx = content.find(BLOCK_END)

        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            # Replace existing block (include the end marker + newline)
            end_of_block = end_idx + len(BLOCK_END)
            # Consume trailing newline if present
            if end_of_block < len(content) and content[end_of_block] == "\n":
                end_of_block += 1
            return content[:start_idx] + block + content[end_of_block:]

        # Append — ensure preceding newline
        if content and not content.endswith("\n"):
            content += "\n"
        return content + "\n" + block

    def remove_config(self, rc_path: Path) -> bool:
        """Remove the Nest AI config block from the RC file.

        Args:
            rc_path: Path to the shell RC file.

        Returns:
            True if a block was found and removed, False if no block existed.
        """
        if not rc_path.exists():
            return False

        try:
            content = rc_path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.error("Failed to read RC file %s: %s", rc_path, exc)
            msg = f"Failed to read RC file {rc_path}: {exc}"
            raise OSError(msg) from exc

        start_idx = content.find(BLOCK_START)
        end_idx = content.find(BLOCK_END)

        if start_idx == -1 or end_idx == -1 or start_idx >= end_idx:
            return False

        end_of_block = end_idx + len(BLOCK_END)
        if end_of_block < len(content) and content[end_of_block] == "\n":
            end_of_block += 1
        # Also remove preceding blank line if present
        if start_idx > 0 and content[start_idx - 1] == "\n":
            start_idx -= 1

        new_content = content[:start_idx] + content[end_of_block:]
        try:
            rc_path.write_text(new_content, encoding="utf-8")
        except PermissionError:
            logger.error("Permission denied writing to %s", rc_path)
            msg = f"Permission denied: cannot write to {rc_path}"
            raise PermissionError(msg) from None
        except OSError as exc:
            logger.error("Failed to write RC file %s: %s", rc_path, exc)
            msg = f"Failed to write RC file {rc_path}: {exc}"
            raise OSError(msg) from exc
        return True
