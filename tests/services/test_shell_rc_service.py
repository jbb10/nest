"""Unit tests for ShellRCService."""

from pathlib import Path

import pytest

from nest.services.shell_rc_service import (
    BLOCK_END,
    BLOCK_START,
    ShellRCService,
)


class TestDetectShell:
    """Tests for shell detection from $SHELL env var."""

    def test_detect_shell_returns_zsh_from_shell_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """$SHELL=/bin/zsh → returns 'zsh'."""
        monkeypatch.setenv("SHELL", "/bin/zsh")
        service = ShellRCService()
        assert service.detect_shell() == "zsh"

    def test_detect_shell_returns_bash_from_shell_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """$SHELL=/bin/bash → returns 'bash'."""
        monkeypatch.setenv("SHELL", "/bin/bash")
        service = ShellRCService()
        assert service.detect_shell() == "bash"

    def test_detect_shell_returns_fish_from_shell_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """$SHELL=/usr/local/bin/fish → returns 'fish'."""
        monkeypatch.setenv("SHELL", "/usr/local/bin/fish")
        service = ShellRCService()
        assert service.detect_shell() == "fish"

    def test_detect_shell_returns_unknown_for_csh(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """$SHELL=/bin/csh → returns 'unknown'."""
        monkeypatch.setenv("SHELL", "/bin/csh")
        service = ShellRCService()
        assert service.detect_shell() == "unknown"

    def test_detect_shell_returns_unknown_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """$SHELL not set → returns 'unknown'."""
        monkeypatch.delenv("SHELL", raising=False)
        monkeypatch.delenv("PSModulePath", raising=False)
        service = ShellRCService()
        assert service.detect_shell() == "unknown"

    def test_detect_shell_returns_powershell_when_psmodulepath_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No $SHELL but $PSModulePath set → returns 'powershell'."""
        monkeypatch.delenv("SHELL", raising=False)
        monkeypatch.setenv("PSModulePath", "C:\\Users\\test\\Documents\\PowerShell\\Modules")
        service = ShellRCService()
        assert service.detect_shell() == "powershell"

    def test_detect_shell_prefers_posix_shell_over_psmodulepath(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """$SHELL=/bin/zsh with $PSModulePath → returns 'zsh' (POSIX wins)."""
        monkeypatch.setenv("SHELL", "/bin/zsh")
        monkeypatch.setenv("PSModulePath", "/some/path")
        service = ShellRCService()
        assert service.detect_shell() == "zsh"


class TestResolveRCPath:
    """Tests for RC file path resolution."""

    def test_resolve_rc_path_zsh(self) -> None:
        """zsh → ~/.zshrc."""
        service = ShellRCService()
        result = service.resolve_rc_path("zsh")
        assert result == Path.home() / ".zshrc"

    def test_resolve_rc_path_bash_linux(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Linux bash → ~/.bashrc."""
        monkeypatch.setattr("nest.services.shell_rc_service.sys.platform", "linux")
        service = ShellRCService()
        result = service.resolve_rc_path("bash")
        assert result == Path.home() / ".bashrc"

    def test_resolve_rc_path_bash_macos_with_bash_profile(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """macOS + .bash_profile exists → returns .bash_profile."""
        monkeypatch.setattr("nest.services.shell_rc_service.sys.platform", "darwin")
        # Create a fake .bash_profile
        bash_profile = tmp_path / ".bash_profile"
        bash_profile.touch()
        monkeypatch.setattr("nest.services.shell_rc_service.Path.home", lambda: tmp_path)
        service = ShellRCService()
        result = service.resolve_rc_path("bash")
        assert result == bash_profile

    def test_resolve_rc_path_bash_macos_without_bash_profile(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """macOS + no .bash_profile → returns ~/.bashrc."""
        monkeypatch.setattr("nest.services.shell_rc_service.sys.platform", "darwin")
        monkeypatch.setattr("nest.services.shell_rc_service.Path.home", lambda: tmp_path)
        service = ShellRCService()
        result = service.resolve_rc_path("bash")
        assert result == tmp_path / ".bashrc"

    def test_resolve_rc_path_fish(self) -> None:
        """fish → ~/.config/fish/config.fish."""
        service = ShellRCService()
        result = service.resolve_rc_path("fish")
        assert result == Path.home() / ".config" / "fish" / "config.fish"

    def test_resolve_rc_path_unknown(self) -> None:
        """unknown → ~/.profile."""
        service = ShellRCService()
        result = service.resolve_rc_path("unknown")
        assert result == Path.home() / ".profile"

    def test_resolve_rc_path_powershell_windows(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """PowerShell on Windows → ~/Documents/PowerShell/Microsoft.PowerShell_profile.ps1."""
        monkeypatch.setattr("nest.services.shell_rc_service.sys.platform", "win32")
        monkeypatch.delenv("PROFILE", raising=False)
        monkeypatch.setattr("nest.services.shell_rc_service.Path.home", lambda: tmp_path)
        service = ShellRCService()
        result = service.resolve_rc_path("powershell")
        assert result == tmp_path / "Documents" / "PowerShell" / "Microsoft.PowerShell_profile.ps1"

    def test_resolve_rc_path_powershell_unix(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """PowerShell (pwsh) on Unix → ~/.config/powershell/Microsoft.PowerShell_profile.ps1."""
        monkeypatch.setattr("nest.services.shell_rc_service.sys.platform", "linux")
        monkeypatch.delenv("PROFILE", raising=False)
        monkeypatch.setattr("nest.services.shell_rc_service.Path.home", lambda: tmp_path)
        service = ShellRCService()
        result = service.resolve_rc_path("powershell")
        assert result == tmp_path / ".config" / "powershell" / "Microsoft.PowerShell_profile.ps1"

    def test_resolve_rc_path_powershell_profile_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """$PROFILE env var set → uses that path directly."""
        profile_path = str(tmp_path / "custom" / "profile.ps1")
        monkeypatch.setenv("PROFILE", profile_path)
        service = ShellRCService()
        result = service.resolve_rc_path("powershell")
        assert result == Path(profile_path)


class TestGenerateConfigBlock:
    """Tests for config block generation."""

    def test_generate_config_block_bash(self) -> None:
        """Bash block uses 'export VAR=\"val\"' syntax."""
        service = ShellRCService()
        block = service.generate_config_block(
            "https://api.openai.com/v1", "gpt-4o-mini", "sk-test", "bash"
        )
        assert 'export NEST_AI_ENDPOINT="https://api.openai.com/v1"' in block
        assert 'export NEST_AI_MODEL="gpt-4o-mini"' in block
        assert 'export NEST_AI_API_KEY="sk-test"' in block

    def test_generate_config_block_zsh(self) -> None:
        """Zsh block uses 'export VAR=\"val\"' syntax (same as bash)."""
        service = ShellRCService()
        block = service.generate_config_block(
            "https://api.openai.com/v1", "gpt-4o-mini", "sk-test", "zsh"
        )
        assert 'export NEST_AI_ENDPOINT="https://api.openai.com/v1"' in block

    def test_generate_config_block_fish(self) -> None:
        """Fish block uses 'set -gx VAR \"val\"' syntax."""
        service = ShellRCService()
        block = service.generate_config_block(
            "https://api.openai.com/v1", "gpt-4o-mini", "sk-test", "fish"
        )
        assert 'set -gx NEST_AI_ENDPOINT "https://api.openai.com/v1"' in block
        assert 'set -gx NEST_AI_MODEL "gpt-4o-mini"' in block
        assert 'set -gx NEST_AI_API_KEY "sk-test"' in block

    def test_generate_config_block_contains_all_vars(self) -> None:
        """Block contains all three env var names."""
        service = ShellRCService()
        block = service.generate_config_block("https://ep", "model", "key", "bash")
        assert "NEST_AI_ENDPOINT" in block
        assert "NEST_AI_MODEL" in block
        assert "NEST_AI_API_KEY" in block

    def test_generate_config_block_has_sentinel_comments(self) -> None:
        """Block starts with BLOCK_START and ends with BLOCK_END."""
        service = ShellRCService()
        block = service.generate_config_block("https://ep", "model", "key", "zsh")
        assert block.startswith(BLOCK_START)
        assert BLOCK_END in block

    def test_generate_config_block_powershell(self) -> None:
        """PowerShell block uses '$Env:VAR = ...' syntax with single quotes."""
        service = ShellRCService()
        block = service.generate_config_block(
            "https://api.openai.com/v1", "gpt-4o-mini", "sk-test", "powershell"
        )
        assert "$Env:NEST_AI_ENDPOINT = 'https://api.openai.com/v1'" in block
        assert "$Env:NEST_AI_MODEL = 'gpt-4o-mini'" in block
        assert "$Env:NEST_AI_API_KEY = 'sk-test'" in block


class TestWriteConfig:
    """Tests for writing config to RC files."""

    def test_write_config_creates_new_file(self, tmp_path: Path) -> None:
        """RC file doesn't exist → created with block."""
        # Arrange
        rc_path = tmp_path / ".zshrc"
        service = ShellRCService()

        # Act
        service.write_config(rc_path, "https://api.openai.com/v1", "gpt-4o-mini", "sk-test", "zsh")

        # Assert
        content = rc_path.read_text(encoding="utf-8")
        assert BLOCK_START in content
        assert 'export NEST_AI_ENDPOINT="https://api.openai.com/v1"' in content
        assert 'export NEST_AI_MODEL="gpt-4o-mini"' in content
        assert 'export NEST_AI_API_KEY="sk-test"' in content
        assert BLOCK_END in content

    def test_write_config_creates_parent_dirs(self, tmp_path: Path) -> None:
        """Parent dirs created for fish config path."""
        # Arrange
        rc_path = tmp_path / ".config" / "fish" / "config.fish"
        service = ShellRCService()

        # Act
        service.write_config(rc_path, "https://api.openai.com/v1", "gpt-4o-mini", "sk-test", "fish")

        # Assert
        assert rc_path.exists()
        content = rc_path.read_text(encoding="utf-8")
        assert 'set -gx NEST_AI_ENDPOINT "https://api.openai.com/v1"' in content

    def test_write_config_powershell_creates_profile(self, tmp_path: Path) -> None:
        """PowerShell profile created with $Env: syntax."""
        # Arrange
        rc_path = tmp_path / "Documents" / "PowerShell" / "Microsoft.PowerShell_profile.ps1"
        service = ShellRCService()

        # Act
        service.write_config(
            rc_path, "https://api.openai.com/v1", "gpt-4o-mini", "sk-test", "powershell"
        )

        # Assert
        assert rc_path.exists()
        content = rc_path.read_text(encoding="utf-8")
        assert "$Env:NEST_AI_ENDPOINT = 'https://api.openai.com/v1'" in content
        assert "$Env:NEST_AI_MODEL = 'gpt-4o-mini'" in content
        assert "$Env:NEST_AI_API_KEY = 'sk-test'" in content
        assert BLOCK_START in content
        assert BLOCK_END in content

    def test_write_config_appends_to_existing(self, tmp_path: Path) -> None:
        """Existing RC content preserved, block appended."""
        # Arrange
        rc_path = tmp_path / ".zshrc"
        rc_path.write_text("# existing config\nexport PATH=/usr/bin\n", encoding="utf-8")
        service = ShellRCService()

        # Act
        service.write_config(rc_path, "https://api.openai.com/v1", "gpt-4o-mini", "sk-test", "zsh")

        # Assert
        content = rc_path.read_text(encoding="utf-8")
        assert "# existing config" in content
        assert "export PATH=/usr/bin" in content
        assert BLOCK_START in content

    def test_write_config_replaces_existing_block(self, tmp_path: Path) -> None:
        """Re-run replaces block, no duplication."""
        # Arrange
        rc_path = tmp_path / ".zshrc"
        service = ShellRCService()
        service.write_config(rc_path, "https://api.openai.com/v1", "gpt-4o-mini", "sk-old", "zsh")

        # Act
        service.write_config(rc_path, "https://api.openai.com/v1", "gpt-4o-mini", "sk-new", "zsh")

        # Assert
        content = rc_path.read_text(encoding="utf-8")
        assert content.count(BLOCK_START) == 1
        assert 'export NEST_AI_API_KEY="sk-new"' in content
        assert "sk-old" not in content

    def test_write_config_preserves_surrounding_content(self, tmp_path: Path) -> None:
        """Content before and after block intact after replace."""
        # Arrange
        rc_path = tmp_path / ".bashrc"
        initial = "# before\nexport FOO=bar\n"
        rc_path.write_text(initial, encoding="utf-8")
        service = ShellRCService()
        service.write_config(rc_path, "https://ep1", "m1", "k1", "bash")
        # Add content after block
        content = rc_path.read_text(encoding="utf-8")
        rc_path.write_text(content + "# after\nexport BAZ=qux\n", encoding="utf-8")

        # Act — replace block
        service.write_config(rc_path, "https://ep2", "m2", "k2", "bash")

        # Assert
        content = rc_path.read_text(encoding="utf-8")
        assert "# before" in content
        assert "export FOO=bar" in content
        assert "# after" in content
        assert "export BAZ=qux" in content
        assert 'export NEST_AI_ENDPOINT="https://ep2"' in content

    def test_write_config_idempotent_triple_run(self, tmp_path: Path) -> None:
        """Run 3 times → only one block exists."""
        # Arrange
        rc_path = tmp_path / ".zshrc"
        service = ShellRCService()

        # Act
        for _ in range(3):
            service.write_config(
                rc_path, "https://api.openai.com/v1", "gpt-4o-mini", "sk-test", "zsh"
            )

        # Assert
        content = rc_path.read_text(encoding="utf-8")
        assert content.count(BLOCK_START) == 1
        assert content.count(BLOCK_END) == 1


class TestRemoveConfig:
    """Tests for removing config from RC files."""

    def test_remove_config_removes_block(self, tmp_path: Path) -> None:
        """Block removed, surrounding content preserved."""
        # Arrange
        rc_path = tmp_path / ".zshrc"
        service = ShellRCService()
        rc_path.write_text(
            "# before\n"
            + service.generate_config_block("https://ep", "m", "k", "zsh")
            + "# after\n",
            encoding="utf-8",
        )

        # Act
        result = service.remove_config(rc_path)

        # Assert
        assert result is True
        content = rc_path.read_text(encoding="utf-8")
        assert BLOCK_START not in content
        assert BLOCK_END not in content
        assert "# before" in content
        assert "# after" in content

    def test_remove_config_returns_true_when_found(self, tmp_path: Path) -> None:
        """Returns True when block existed."""
        # Arrange
        rc_path = tmp_path / ".zshrc"
        service = ShellRCService()
        service.write_config(rc_path, "https://ep", "m", "k", "zsh")

        # Act
        result = service.remove_config(rc_path)

        # Assert
        assert result is True

    def test_remove_config_returns_false_when_not_found(self, tmp_path: Path) -> None:
        """Returns False when no block exists."""
        # Arrange
        rc_path = tmp_path / ".zshrc"
        rc_path.write_text("# just some config\n", encoding="utf-8")
        service = ShellRCService()

        # Act
        result = service.remove_config(rc_path)

        # Assert
        assert result is False

    def test_remove_config_no_file(self, tmp_path: Path) -> None:
        """Returns False when RC file doesn't exist."""
        # Arrange
        rc_path = tmp_path / ".zshrc"
        service = ShellRCService()

        # Act
        result = service.remove_config(rc_path)

        # Assert
        assert result is False

    def test_remove_config_preserves_other_content(self, tmp_path: Path) -> None:
        """Lines before/after block remain intact."""
        # Arrange
        rc_path = tmp_path / ".bashrc"
        service = ShellRCService()
        before = "export PATH=/usr/bin\nalias ll='ls -la'\n"
        after = "export EDITOR=vim\n"
        block = service.generate_config_block("https://ep", "m", "k", "bash")
        rc_path.write_text(before + "\n" + block + after, encoding="utf-8")

        # Act
        service.remove_config(rc_path)

        # Assert
        content = rc_path.read_text(encoding="utf-8")
        assert "export PATH=/usr/bin" in content
        assert "alias ll='ls -la'" in content
        assert "export EDITOR=vim" in content
        assert BLOCK_START not in content


class TestEscapeShellValue:
    """Tests for shell value escaping."""

    def test_escapes_double_quotes(self) -> None:
        """Double quotes are escaped."""
        service = ShellRCService()
        block = service.generate_config_block("https://ep", "m", 'sk-ab"cd', "bash")
        assert 'export NEST_AI_API_KEY="sk-ab\\"cd"' in block

    def test_escapes_backslashes(self) -> None:
        """Backslashes are escaped."""
        service = ShellRCService()
        block = service.generate_config_block("https://ep", "m", "sk-ab\\cd", "bash")
        assert 'export NEST_AI_API_KEY="sk-ab\\\\cd"' in block

    def test_escapes_backticks(self) -> None:
        """Backticks are escaped."""
        service = ShellRCService()
        block = service.generate_config_block("https://ep", "m", "sk-ab`cd", "bash")
        assert 'export NEST_AI_API_KEY="sk-ab\\`cd"' in block

    def test_escapes_dollar_signs(self) -> None:
        """Dollar signs are escaped."""
        service = ShellRCService()
        block = service.generate_config_block("https://ep", "m", "sk-ab$cd", "bash")
        assert 'export NEST_AI_API_KEY="sk-ab\\$cd"' in block

    def test_fish_escapes_double_quotes(self) -> None:
        """Fish syntax also escapes double quotes."""
        service = ShellRCService()
        block = service.generate_config_block("https://ep", "m", 'sk-ab"cd', "fish")
        assert 'set -gx NEST_AI_API_KEY "sk-ab\\"cd"' in block


class TestEscapePowershellValue:
    """Tests for PowerShell value escaping."""

    def test_escapes_single_quotes(self) -> None:
        """Single quotes are doubled in PowerShell single-quoted strings."""
        service = ShellRCService()
        block = service.generate_config_block("https://ep", "m", "sk-ab'cd", "powershell")
        assert "$Env:NEST_AI_API_KEY = 'sk-ab''cd'" in block

    def test_dollar_signs_not_escaped_in_powershell(self) -> None:
        """Dollar signs are literal inside PowerShell single-quoted strings."""
        service = ShellRCService()
        block = service.generate_config_block("https://ep", "m", "sk-ab$cd", "powershell")
        assert "$Env:NEST_AI_API_KEY = 'sk-ab$cd'" in block

    def test_backslashes_not_escaped_in_powershell(self) -> None:
        """Backslashes are literal inside PowerShell single-quoted strings."""
        service = ShellRCService()
        block = service.generate_config_block("https://ep", "m", "sk-ab\\cd", "powershell")
        assert "$Env:NEST_AI_API_KEY = 'sk-ab\\cd'" in block


class TestSentinelOrderValidation:
    """Tests for corrupted sentinel marker handling."""

    def test_write_config_appends_when_end_before_start(self, tmp_path: Path) -> None:
        """BLOCK_END before BLOCK_START → treat as no block, append new one."""
        # Arrange
        rc_path = tmp_path / ".zshrc"
        corrupted = f"# before\n{BLOCK_END}\nstuff\n{BLOCK_START}\n# after\n"
        rc_path.write_text(corrupted, encoding="utf-8")
        service = ShellRCService()

        # Act
        service.write_config(rc_path, "https://api.openai.com/v1", "gpt-4o-mini", "sk-test", "zsh")

        # Assert — should append, not corrupt
        content = rc_path.read_text(encoding="utf-8")
        assert "# before" in content
        # The appended block should be at the end
        last_start = content.rfind(BLOCK_START)
        last_end = content.rfind(BLOCK_END)
        assert last_start < last_end

    def test_remove_config_returns_false_when_end_before_start(self, tmp_path: Path) -> None:
        """BLOCK_END before BLOCK_START → returns False (corrupted, no removal)."""
        # Arrange
        rc_path = tmp_path / ".zshrc"
        corrupted = f"# before\n{BLOCK_END}\nstuff\n{BLOCK_START}\n# after\n"
        rc_path.write_text(corrupted, encoding="utf-8")
        service = ShellRCService()

        # Act
        result = service.remove_config(rc_path)

        # Assert
        assert result is False


class TestWriteConfigErrorHandling:
    """Tests for file I/O error handling."""

    def test_write_config_raises_on_read_only_file(self, tmp_path: Path) -> None:
        """PermissionError raised when RC file is read-only."""
        # Arrange
        rc_path = tmp_path / ".zshrc"
        rc_path.write_text("# existing\n", encoding="utf-8")
        rc_path.chmod(0o444)
        service = ShellRCService()

        # Act & Assert
        with pytest.raises(PermissionError, match="Permission denied"):
            service.write_config(rc_path, "https://ep", "m", "k", "zsh")
        # Cleanup
        rc_path.chmod(0o644)

    def test_write_config_raises_on_unwritable_directory(self, tmp_path: Path) -> None:
        """OSError raised when parent directory cannot be created."""
        # Arrange
        blocked_dir = tmp_path / "blocked"
        blocked_dir.mkdir()
        blocked_dir.chmod(0o444)
        rc_path = blocked_dir / "subdir" / ".zshrc"
        service = ShellRCService()

        # Act & Assert
        with pytest.raises(OSError, match="Failed to write RC file|Permission denied"):
            service.write_config(rc_path, "https://ep", "m", "k", "zsh")
        # Cleanup
        blocked_dir.chmod(0o755)
