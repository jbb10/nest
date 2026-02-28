"""Update command for nest CLI.

Handles the `nest update` command — version discovery, display,
user prompt, uv-based install, and agent template migration.
"""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.prompt import Confirm, Prompt

from nest.adapters.filesystem import FileSystemAdapter
from nest.adapters.git_client import GitClientAdapter
from nest.adapters.manifest import ManifestAdapter
from nest.adapters.subprocess_runner import SubprocessRunnerAdapter
from nest.adapters.user_config import UserConfigAdapter, create_default_config
from nest.agents.vscode_writer import VSCodeAgentWriter
from nest.core.exceptions import ConfigError
from nest.core.models import (
    AgentMigrationCheckResult,
    UpdateCheckResult,
    UpdateResult,
    UserConfig,
)
from nest.services.agent_migration_service import AgentMigrationService
from nest.services.migration_service import MetadataMigrationService
from nest.services.update_service import UpdateService
from nest.ui.messages import error, get_console, info, success, warning


def create_update_service() -> tuple[UpdateService, UserConfigAdapter]:
    """Composition root for update service.

    Returns:
        Tuple of (UpdateService, UserConfigAdapter) — adapter returned
        separately because CLI needs it for config ensure/save.
    """
    git_client = GitClientAdapter()
    user_config = UserConfigAdapter()
    subprocess_runner = SubprocessRunnerAdapter()
    service = UpdateService(
        git_client=git_client,
        user_config=user_config,
        subprocess_runner=subprocess_runner,
    )
    return service, user_config


def create_migration_service() -> AgentMigrationService:
    """Composition root for agent migration service.

    Returns:
        Configured AgentMigrationService.
    """
    filesystem = FileSystemAdapter()
    return AgentMigrationService(
        agent_writer=VSCodeAgentWriter(filesystem=filesystem),
        filesystem=filesystem,
        manifest=ManifestAdapter(),
    )


def _ensure_config(user_config: UserConfigAdapter) -> UserConfig:
    """Ensure user config exists, creating default if needed.

    Args:
        user_config: User config adapter.

    Returns:
        The loaded or newly created UserConfig.
    """
    config = user_config.load()
    if config is not None:
        return config

    config = create_default_config()
    user_config.save(config)
    info("Created default configuration")
    return config


def _display_versions(
    check_result: UpdateCheckResult,
    console: Console,
) -> None:
    """Render version list with Rich markup.

    Args:
        check_result: Update check result with version data.
        console: Rich console for output.
    """
    console.print()
    console.print(f"  Current version: [bold]{check_result.current_version}[/bold]")
    if check_result.latest_version:
        console.print(f"  Latest version:  [bold]{check_result.latest_version}[/bold]")
    console.print()
    console.print("  Available versions:")
    for version, annotation in check_result.annotated_versions:
        if "(installed)" in annotation:
            console.print(f"    [green]•[/green] {version} [dim]{annotation}[/dim]")
        elif "(latest)" in annotation:
            console.print(f"    [cyan]•[/cyan] {version} [dim]{annotation}[/dim]")
        else:
            console.print(f"    • {version}")


def _prompt_for_version(
    check_result: UpdateCheckResult,
    console: Console,
) -> str | None:
    """Prompt user for version selection.

    Args:
        check_result: Update check result with version data.
        console: Rich console for output.

    Returns:
        Target version string, or None if user cancelled.
    """
    latest = check_result.latest_version
    response = Prompt.ask(
        f"\n  Update to {latest}? [Y/n/version]",
        default="Y",
        console=console,
    )

    if response.lower() == "n":
        return None
    elif response.upper() == "Y" or response == "":
        return latest
    else:
        # Strip optional v prefix from user input
        return response.lstrip("v")


def _run_update(
    service: UpdateService,
    version: str,
    check_result: UpdateCheckResult,
    console: Console,
) -> UpdateResult:
    """Execute update with Rich spinner.

    Args:
        service: Update service.
        version: Target version to install.
        check_result: Update check result with available versions.
        console: Rich console for output.

    Returns:
        UpdateResult from the service.
    """
    available = [v for v, _ in check_result.annotated_versions]
    with console.status(f"Installing version {version}..."):
        return service.execute_update(version, available, check_result.source)


def _handle_agent_migration(
    migration_service: AgentMigrationService,
    project_dir: Path,
    console: Console,
) -> None:
    """Handle post-update agent template migration.

    Args:
        migration_service: Agent migration service.
        project_dir: Project directory to check.
        console: Rich console for output.
    """
    migration_check: AgentMigrationCheckResult = migration_service.check_migration_needed(
        project_dir
    )

    # AC9: Silently skip if not a Nest project
    if migration_check.skipped:
        return

    # AC8: No prompt if up to date
    if not migration_check.migration_needed:
        success("Agent file is up to date")
        return

    # AC7: Prompt for migration
    if migration_check.agent_file_missing:
        confirm_msg = "Agent file is missing. Create it?"
    else:
        confirm_msg = "Agent template has changed. Update?"

    if Confirm.ask(confirm_msg, default=False, console=console):
        migration_result = migration_service.execute_migration(project_dir)
        if migration_result.success:
            if migration_result.backed_up:
                success("Agent file updated (backup: nest.agent.md.bak)")
            else:
                success("Agent file created")
        else:
            # AC14: Non-critical failure
            warning(f"Agent file update failed: {migration_result.error}")
    else:
        info("Keeping existing agent file. Run nest doctor to update later.")


def _handle_metadata_migration(
    project_dir: Path,
    console: Console,
) -> None:
    """Migrate old-layout metadata files to .nest/ directory.

    Args:
        project_dir: Project directory to check.
        console: Rich console for output.
    """
    migration_service = MetadataMigrationService()

    if not migration_service.detect_legacy_layout(project_dir):
        return  # Already new layout or not a Nest project

    result = migration_service.migrate(project_dir)

    if result.migrated:
        for item in result.files_moved:
            info(item)
        success("Migrated metadata to .nest/ directory")

    if result.errors:
        for err in result.errors:
            warning(err)


def update_command(
    check: Annotated[
        bool,
        typer.Option("--check", help="Only check for updates without installing"),
    ] = False,
    target_dir: Annotated[
        Path | None,
        typer.Option("--dir", "-d", help="Project directory for agent migration check"),
    ] = None,
) -> None:
    """Check for and install Nest updates.

    Queries available versions, displays comparison, and optionally
    installs a selected version via uv.

    Examples:
        nest update
        nest update --check
        nest update --dir /path/to/project
    """
    console = get_console()

    # Step 1: Create services
    service, user_config_adapter = create_update_service()
    migration_service = create_migration_service()

    # Step 2: Ensure config exists (AC6)
    _ensure_config(user_config_adapter)

    # Step 3: Check for updates
    try:
        check_result = service.check_for_updates()
    except ConfigError:
        # AC13: Network/config error
        error("Cannot check for updates")
        console.print(
            "  [dim]Reason: Cannot reach update server. Check your internet connection.[/dim]"
        )
        console.print("  [dim]Action: Verify your network connection and try again[/dim]")
        raise typer.Exit(1) from None

    # Step 4: Handle edge cases
    # AC12: No versions found
    if not check_result.annotated_versions:
        info("No releases found. You may be on a development version.")
        raise typer.Exit(0) from None

    # AC11: Already up-to-date
    if not check_result.update_available:
        if check:
            _display_versions(check_result, console)
        success(f"Already up to date (version {check_result.current_version})")
        raise typer.Exit(0) from None

    # AC10: --check flag — display only
    if check:
        _display_versions(check_result, console)
        raise typer.Exit(1) from None

    # Step 5: Display versions and prompt
    _display_versions(check_result, console)
    target_version = _prompt_for_version(check_result, console)

    # AC5: User cancellation
    if target_version is None:
        info("Update cancelled")
        raise typer.Exit(0) from None

    # Step 6: Execute update (AC3, AC4)
    result = _run_update(service, target_version, check_result, console)

    if result.success:
        console.print()
        success(f"Updated to version {result.version}")
        console.print()
        console.print(
            "  [dim]What's new: https://github.com/jbb10/nest/blob/main/CHANGELOG.md[/dim]"
        )

        # Step 7: Agent migration check (AC7, AC8, AC9)
        console.print()
        project_dir = target_dir or Path.cwd()
        _handle_agent_migration(migration_service, project_dir, console)

        # Step 8: Metadata directory migration
        _handle_metadata_migration(project_dir, console)
    else:
        # AC4: Update failure
        console.print()
        error("Update failed")
        console.print(f"  [dim]Reason: {result.error}[/dim]")
        console.print("  [dim]Action: Check `uv` is working: `uv --version`[/dim]")
        raise typer.Exit(1) from None
