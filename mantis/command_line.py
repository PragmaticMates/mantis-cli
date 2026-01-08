#!/usr/bin/env python
"""
Mantis CLI - Docker deployment tool

Usage:
    mantis [OPTIONS] COMMAND [ARGS]... [COMMAND [ARGS]...]

Examples:
    mantis -e production status
    mantis -e production deploy --dirty
    mantis -e production build push deploy
    mantis status                          (single connection mode)
    mantis manage migrate
"""
import sys
from typing import List, Tuple, Set

import click
import typer

from mantis import VERSION
from mantis.app import app, state, COMMAND_NAMES, print_heading
from mantis.managers import get_manager

# Import commands to register them with the app
from mantis import commands  # noqa: F401


# Global options that take a value
OPTS_WITH_VALUES = {'-e', '--env', '-m', '--mode'}


def split_args_by_commands(
    args: List[str],
    command_names: Set[str]
) -> Tuple[List[str], List[Tuple[str, List[str]]]]:
    """
    Split argv into global options and (command, args) groups.

    Input:  ['-e', 'prod', 'build', 'web', 'push', 'deploy']
    Output: (['-e', 'prod'], [('build', ['web']), ('push', []), ('deploy', [])])
    """
    global_opts = []
    cmd_groups = []
    current_cmd = None
    current_args = []

    i = 0
    while i < len(args):
        arg = args[i]

        if current_cmd is None:
            # Still parsing global options
            if arg.startswith('-'):
                global_opts.append(arg)
                # Consume value for options that take one
                if arg in OPTS_WITH_VALUES and i + 1 < len(args):
                    i += 1
                    global_opts.append(args[i])
            elif arg in command_names:
                # First command found
                current_cmd = arg
                current_args = []
            # else: unexpected positional before command - will be handled by Typer
        else:
            # After first command
            if arg in command_names:
                # New command - save previous and start new group
                cmd_groups.append((current_cmd, current_args))
                current_cmd = arg
                current_args = []
            else:
                # Argument for current command
                current_args.append(arg)
        i += 1

    # Don't forget last command
    if current_cmd is not None:
        cmd_groups.append((current_cmd, current_args))

    return global_opts, cmd_groups


def parse_global_options(global_opts: List[str]) -> dict:
    """Parse global options into a dict."""
    result = {
        'env': None,
        'mode': 'remote',
        'dry_run': False,
        'help': False,
        'version': False,
    }

    i = 0
    while i < len(global_opts):
        opt = global_opts[i]
        if opt in ('-e', '--env') and i + 1 < len(global_opts):
            result['env'] = global_opts[i + 1]
            i += 2
        elif opt in ('-m', '--mode') and i + 1 < len(global_opts):
            result['mode'] = global_opts[i + 1]
            i += 2
        elif opt in ('-n', '--dry-run'):
            result['dry_run'] = True
            i += 1
        elif opt in ('-v', '--version'):
            result['version'] = True
            i += 1
        elif opt in ('-h', '--help'):
            result['help'] = True
            i += 1
        else:
            i += 1

    return result


def invoke_command(click_app, cmd_name: str, cmd_args: List[str], parent_ctx):
    """Invoke a single command with its arguments."""
    from mantis.helpers import CLI

    cmd = click_app.get_command(parent_ctx, cmd_name)
    if cmd is None:
        CLI.error(f"Unknown command: {cmd_name}")

    state._current_command = cmd_name

    # Create context for this command and invoke
    try:
        with cmd.make_context(cmd_name, cmd_args, parent=parent_ctx) as ctx:
            cmd.invoke(ctx)
    except click.exceptions.Exit:
        # Normal exit (e.g., from --help)
        pass


def run():
    """Entry point with command-aware argument parsing."""
    args = sys.argv[1:]

    # No args - show help
    if not args:
        app()
        return

    global_opts, cmd_groups = split_args_by_commands(args, COMMAND_NAMES)

    # No commands found - delegate to Typer (handles --help, --version, errors)
    if not cmd_groups:
        sys.argv = [sys.argv[0]] + global_opts
        app()
        return

    # Parse global options
    opts = parse_global_options(global_opts)

    # Handle --version
    if opts['version']:
        print(f"Mantis v{VERSION}")
        return

    # Handle --help: show help for first command
    if opts['help']:
        sys.argv = [sys.argv[0]] + [cmd_groups[0][0], '--help']
        app()
        return

    # Check if any command has --help in its args - delegate to Typer without initializing manager
    for cmd_name, cmd_args in cmd_groups:
        if '--help' in cmd_args or '-h' in cmd_args:
            sys.argv = [sys.argv[0]] + [cmd_name, '--help']
            app()
            return

    # Initialize state (mirrors @app.callback behavior)
    state._mode = opts['mode']
    state._dry_run = opts['dry_run']
    state._manager = get_manager(opts['env'], opts['mode'], dry_run=opts['dry_run'])

    # Get Click app from Typer
    click_app = typer.main.get_command(app)

    # Create parent context for shared state
    # Use resilient_parsing to prevent Click from triggering no_args_is_help
    try:
        with click_app.make_context('mantis', [], resilient_parsing=True) as parent_ctx:
            # Invoke each command in sequence
            for cmd_name, cmd_args in cmd_groups:
                invoke_command(click_app, cmd_name, cmd_args, parent_ctx)
    except click.exceptions.Exit:
        # Normal exit (e.g., from --help in command)
        pass


if __name__ == "__main__":
    run()
