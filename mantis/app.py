"""Mantis CLI app setup and shared state."""
import socket
from functools import wraps
from typing import Optional, List, Callable

import typer
from rich.console import Console
from rich.text import Text

from mantis import VERSION
from mantis.helpers import CLI
from mantis.managers import get_manager

EPILOG = """\
[bold]Examples:[/bold]

  mantis -e production status

  mantis -e production deploy --dirty

  mantis -e production build + push + deploy

  mantis -e prod manage migrate --fake

  mantis -e prod pg-dump --data-only --table users

  mantis -e prod bash web

  mantis -e prod logs django

  mantis status [dim](single connection mode)[/dim]



[bold]Get help for a specific command:[/bold]

  mantis COMMAND --help
"""

app = typer.Typer(
    chain=True,
    no_args_is_help=True,
    rich_markup_mode="rich",
    epilog=EPILOG,
    context_settings={"max_content_width": 120},
    add_completion=True,
)

# Commands that don't require environment (populated by @no_env_required decorator)
NO_ENV_COMMANDS: set[str] = set()

# Cache hostname
_hostname = socket.gethostname()


def join_args(args: Optional[List[str]], separator: str = ' ') -> str:
    """Join optional list of arguments into a string."""
    return separator.join(args) if args else ''


class State:
    """Shared state across commands."""

    def __init__(self):
        self._manager = None
        self._mode = 'remote'
        self._dry_run = False
        self._heading_printed = False
        self._current_command = None

    def _ensure_ready(self):
        """Print heading and validate environment."""
        if not self._heading_printed:
            print_heading(self._manager, self._mode)
            self._heading_printed = True

        command_name = self._current_command
        if command_name and command_name not in NO_ENV_COMMANDS:
            if not self._manager.single_connection_mode and self._manager.environment_id is None:
                CLI.error(f'Command "{command_name}" requires environment. Use: mantis -e <environment> {command_name}')

    def __getattr__(self, name):
        """Delegate method calls to manager, handling heading and validation."""
        self._ensure_ready()
        return getattr(self._manager, name)


state = State()


def print_heading(manager, mode: str):
    """Print the heading with environment and connection info."""
    console = Console()

    heading = Text()
    heading.append(f'Mantis v{VERSION}')
    heading.append(", ")

    if manager.environment_id:
        heading.append("Environment ID = ")
        heading.append(str(manager.environment_id), style="bold")
        heading.append(", ")
    elif manager.single_connection_mode:
        heading.append("(single connection mode)", style="bold")
        heading.append(", ")

    if manager.connection and manager.host:
        heading.append(str(manager.host), style="red")
        heading.append(", ")

    heading.append("mode: ")
    heading.append(str(mode), style="green")
    heading.append(", hostname: ")
    heading.append(_hostname, style="blue")

    if manager.dry_run:
        heading.append(" ")
        heading.append("[DRY-RUN]", style="bold yellow")

    console.print(heading)


# =============================================================================
# Decorators
# =============================================================================

def command(
    name: str = None,
    shortcut: str = None,
    panel: str = None,
    no_env: bool = False,
):
    """
    Enhanced command decorator with shortcut and no_env support.

    Args:
        name: Command name (defaults to function name with underscores replaced by dashes)
        shortcut: Short alias for the command
        panel: Rich help panel name
        no_env: If True, command doesn't require environment
    """
    def decorator(func: Callable) -> Callable:
        cmd_name = name or func.__name__.replace('_', '-')

        # Mark as no-env command
        if no_env:
            NO_ENV_COMMANDS.add(cmd_name)
            if shortcut:
                NO_ENV_COMMANDS.add(shortcut)

        @wraps(func)
        def wrapper(*args, **kwargs):
            state._current_command = cmd_name
            return func(*args, **kwargs)

        # Register main command
        kwargs = {}
        if panel:
            kwargs['rich_help_panel'] = panel
        registered = app.command(cmd_name, **kwargs)(wrapper)

        # Register shortcut
        if shortcut:
            app.command(shortcut, rich_help_panel="Shortcuts", help=f"Alias for '{cmd_name}'")(wrapper)

        return registered

    return decorator


def version_callback(value: bool):
    if value:
        typer.echo(f"Mantis v{VERSION}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    environment: Optional[str] = typer.Option(None, "--env", "-e", help="Environment ID"),
    mode: str = typer.Option("remote", "--mode", "-m", help="Execution mode: remote, ssh, host"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show commands without executing"),
    version: bool = typer.Option(False, "--version", "-v", callback=version_callback, is_eager=True, help="Show version and exit"),
):
    """Mantis CLI - Docker deployment tool."""
    import sys

    # Skip initialization when showing help or completions
    if ctx.resilient_parsing or '--help' in sys.argv or '-h' in sys.argv:
        return

    state._mode = mode
    state._dry_run = dry_run
    state._manager = get_manager(environment, mode, dry_run=dry_run)
