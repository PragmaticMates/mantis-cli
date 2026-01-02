#!/usr/bin/env python
"""
Mantis CLI - Docker deployment tool

Usage:
    mantis [OPTIONS] [ENVIRONMENT] COMMAND [ARGS]...

Examples:
    mantis production status
    mantis production deploy --dirty
    mantis production build push deploy
    mantis prod logs web
    mantis manage migrate
"""
import os
import sys
from typing import List, Optional

import typer
from rich.console import Console
from rich.text import Text

from mantis import VERSION
from mantis.commands import COMMANDS, NO_ENV_COMMANDS, get_command, list_commands
from mantis.helpers import CLI
from mantis.logic import get_manager

app = typer.Typer(
    add_completion=False,
    invoke_without_command=True,
    no_args_is_help=False,
)


def print_version():
    """Print version information."""
    print(f"Mantis v{VERSION}")


def print_heading(manager, mode: str):
    """Print the heading with environment and connection info."""
    console = Console()
    hostname = os.popen('hostname').read().rstrip("\n")
    version_info = f'Mantis v{VERSION}'

    heading = Text()
    heading.append(version_info)
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


def parse_command_args(args: List[str]) -> tuple:
    """
    Parse command line arguments to extract environment, commands, and their args.

    Returns: (environment_id, command_groups)
    where command_groups is a list of (command_name, args) tuples
    """
    if not args:
        return None, []

    # Check if first arg is an environment (doesn't look like a command or option)
    first_arg = args[0]
    environment_id = None
    start_idx = 0

    # If first arg doesn't start with '-' and isn't a known command, treat as environment
    if not first_arg.startswith('-') and first_arg not in COMMANDS:
        environment_id = first_arg
        start_idx = 1

    # Parse remaining args into command groups
    command_groups = []
    current_command = None
    current_args = []

    for arg in args[start_idx:]:
        if arg.startswith('--'):
            # Long option for current command
            current_args.append(arg)
        elif arg.startswith('-') and len(arg) == 2:
            # Could be a shortcut or a short option
            if arg.lstrip('-') in COMMANDS or arg in COMMANDS:
                # It's a command shortcut
                if current_command:
                    command_groups.append((current_command, current_args))
                current_command = arg.lstrip('-')
                current_args = []
            else:
                # Short option for current command
                current_args.append(arg)
        elif arg in COMMANDS:
            # New command
            if current_command:
                command_groups.append((current_command, current_args))
            current_command = arg
            current_args = []
        else:
            # Argument for current command, or first command
            if current_command is None:
                # First positional arg is a command
                if arg in COMMANDS:
                    current_command = arg
                else:
                    # Unknown - could be command or arg
                    current_command = arg
            else:
                current_args.append(arg)

    # Don't forget the last command
    if current_command:
        command_groups.append((current_command, current_args))

    return environment_id, command_groups


def execute_commands(manager, command_groups: List[tuple], mode: str, environment_id: str, raw_args: List[str]):
    """Execute a list of commands."""
    # Handle SSH mode specially - forward all commands to remote
    if mode == 'ssh':
        env_part = f'{environment_id} ' if environment_id else ''
        # Reconstruct command string from groups
        cmd_parts = []
        for cmd_name, cmd_args in command_groups:
            cmd_parts.append(cmd_name)
            cmd_parts.extend(cmd_args)

        remote_cmd = f'mantis --mode=host {env_part}{" ".join(cmd_parts)}'
        ssh_cmd = f"ssh -t {manager.user}@{manager.host} -p {manager.port} 'cd {manager.project_path}; {remote_cmd}'"
        os.system(ssh_cmd)
        return

    # Execute each command locally
    for cmd_name, cmd_args in command_groups:
        cmd = get_command(cmd_name)

        if cmd is None:
            CLI.error(f'Unknown command: {cmd_name}. Run "mantis commands" to see available commands.')

        # Check if command requires environment
        if cmd.name not in NO_ENV_COMMANDS:
            if not manager.single_connection_mode and manager.environment_id is None:
                CLI.error(f'Command "{cmd.name}" requires an environment. Usage: mantis <environment> {cmd.name}')

        # Execute the command
        try:
            cmd.execute(manager, cmd_args)
        except TypeError as e:
            CLI.error(f'Error executing {cmd.name}: {e}')


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    args: Optional[List[str]] = typer.Argument(None, help="Environment and commands"),
    mode: str = typer.Option("remote", "--mode", "-m", help="Execution mode: remote, ssh, host"),
    version: bool = typer.Option(False, "--version", "-v", help="Show version and exit"),
    help_flag: bool = typer.Option(False, "--help", "-h", help="Show help and exit"),
):
    """
    Mantis CLI - Docker deployment tool.

    Usage: mantis [OPTIONS] [ENVIRONMENT] COMMAND [ARGS]...

    Examples:
        mantis production status
        mantis production deploy --dirty
        mantis stage build push deploy
        mantis manage migrate
    """
    # Handle --version
    if version:
        print_version()
        raise typer.Exit()

    # Handle --help or no arguments
    if help_flag or not args:
        print_help()
        raise typer.Exit()

    # Validate mode
    if mode not in ['remote', 'ssh', 'host']:
        CLI.error(f'Invalid mode: {mode}. Must be one of: remote, ssh, host')

    # Parse arguments
    environment_id, command_groups = parse_command_args(args)

    if not command_groups:
        CLI.error('No commands specified. Run "mantis commands" to see available commands.')

    # Check if any command doesn't require environment
    first_cmd = command_groups[0][0] if command_groups else None
    first_cmd_obj = get_command(first_cmd) if first_cmd else None

    # Get manager (may prompt for config selection)
    try:
        manager = get_manager(environment_id, mode)
    except SystemExit:
        raise typer.Exit(1)

    # Print heading
    print_heading(manager, mode)

    # Execute commands
    execute_commands(manager, command_groups, mode, environment_id, args)


def print_help():
    """Print help message."""
    console = Console()

    print(f"""
Mantis v{VERSION} - Docker deployment tool

Usage:
    mantis [OPTIONS] [ENVIRONMENT] COMMAND [ARGS]...

Options:
    --mode, -m     Execution mode: remote (default), ssh, host
    --version, -v  Show version and exit
    --help, -h     Show this help message

Modes:
    remote    Runs commands remotely using DOCKER_HOST or DOCKER_CONTEXT (default)
    ssh       Connects via SSH and runs mantis on remote machine
    host      Runs mantis directly on host (used as proxy for ssh mode)

Environment:
    Optional environment ID (e.g., production, staging, local)
    Required for multi-environment configs, optional for single connection mode

Examples:
    mantis production status          # Check container status
    mantis production deploy          # Full deployment
    mantis production deploy --dirty  # Deploy without cleanup
    mantis stage build push deploy    # Build, push, and deploy
    mantis production logs web        # View logs for 'web' container
    mantis manage migrate             # Run Django migration (single connection mode)

Run 'mantis commands' to see all available commands.
""")


def run():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    run()
