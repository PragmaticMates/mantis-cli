"""Mantis CLI app setup and shared state."""
import inspect
import os
from typing import Optional

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

  mantis -e production build push deploy

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
)

# Commands that don't require environment
NO_ENV_COMMANDS = {'generate-key', 'check-config', 'contexts', 'create-context', 'read-key'}


class State:
    """Shared state across commands."""
    def __init__(self):
        self._manager = None
        self._mode = 'remote'
        self._heading_printed = False

    def _ensure_ready(self, command_name: str):
        """Print heading and validate environment."""
        if not self._heading_printed:
            print_heading(self._manager, self._mode)
            self._heading_printed = True

        if command_name not in NO_ENV_COMMANDS:
            if not self._manager.single_connection_mode and self._manager.environment_id is None:
                CLI.error(f'Command "{command_name}" requires environment. Use: mantis -e <environment> {command_name}')

    def __getattr__(self, name):
        """Delegate method calls to manager, handling heading and validation."""
        # Get the caller function name (the command)
        caller = inspect.stack()[1].function
        command_name = caller.replace('_', '-')
        self._ensure_ready(command_name)
        return getattr(self._manager, name)


state = State()


def print_heading(manager, mode: str):
    """Print the heading with environment and connection info."""
    console = Console()
    hostname = os.popen('hostname').read().rstrip("\n")

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
    heading.append(hostname, style="blue")

    console.print(heading)


def add_shortcut(name: str, shortcut: str, func, panel: str = "Shortcuts"):
    """Register a command shortcut."""
    app.command(shortcut, rich_help_panel=panel, help=f"Alias for '{name}'")(func)


def version_callback(value: bool):
    if value:
        typer.echo(f"Mantis v{VERSION}")
        raise typer.Exit()


@app.callback()
def main(
    environment: Optional[str] = typer.Option(None, "--env", "-e", help="Environment ID"),
    mode: str = typer.Option("remote", "--mode", "-m", help="Execution mode: remote, ssh, host"),
    version: bool = typer.Option(False, "--version", "-v", callback=version_callback, is_eager=True, help="Show version and exit"),
):
    """Mantis CLI - Docker deployment tool."""
    state._mode = mode
    state._manager = get_manager(environment, mode)
