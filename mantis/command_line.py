#!/usr/bin/env python
"""
Mantis CLI - Docker deployment tool

Usage:
    mantis [OPTIONS] COMMAND [ARGS]... [+ COMMAND [ARGS]...]

Examples:
    mantis -e production status
    mantis -e production deploy --dirty
    mantis -e production build + push + deploy
    mantis -e production build web api + push + deploy
    mantis status                          (single connection mode)
    mantis manage migrate
"""
import sys
from typing import List, Tuple

import click
import typer

from mantis import VERSION
from mantis.app import app, state
from mantis.managers import get_manager

# Import commands to register them with the app
from mantis import commands  # noqa: F401

# Command separator for chaining
COMMAND_SEPARATOR = '+'


def split_args(args: List[str]) -> Tuple[List[str], List[List[str]]]:
    """
    Split args into global options and command groups using '+' separator.

    Input:  ['-e', 'prod', 'build', 'web', '+', 'push', '+', 'deploy']
    Output: (['-e', 'prod'], [['build', 'web'], ['push'], ['deploy']])
    """
    # Split by separator
    groups = []
    current = []

    for arg in args:
        if arg == COMMAND_SEPARATOR:
            if current:
                groups.append(current)
                current = []
        else:
            current.append(arg)

    if current:
        groups.append(current)

    if not groups:
        return [], []

    # First group: separate global options from first command
    first_group = groups[0]
    global_opts = []

    # Global options are at the start and begin with '-'
    i = 0
    while i < len(first_group):
        arg = first_group[i]
        if arg.startswith('-'):
            global_opts.append(arg)
            # Handle options with values: -e prod, --env prod
            if arg in ('-e', '--env', '-m', '--mode') and i + 1 < len(first_group):
                i += 1
                global_opts.append(first_group[i])
            i += 1
        else:
            # First non-option is start of command
            break

    # Remaining of first group is the first command
    first_cmd = first_group[i:] if i < len(first_group) else []

    # Build command groups
    cmd_groups = []
    if first_cmd:
        cmd_groups.append(first_cmd)
    cmd_groups.extend(groups[1:])

    return global_opts, cmd_groups


def parse_global_options(global_opts: List[str]) -> dict:
    """Parse global options into a dict. Only used for multi-command chaining."""
    result = {
        'env': None,
        'mode': 'remote',
        'dry_run': False,
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
    """Entry point with command chaining support using '+' separator."""
    args = sys.argv[1:]

    # No args - show help
    if not args:
        app()
        return

    global_opts, cmd_groups = split_args(args)

    # No commands found - delegate to Typer (handles --help, --version, errors)
    if not cmd_groups:
        sys.argv = [sys.argv[0]] + global_opts
        app()
        return

    # Handle --version early
    if '--version' in global_opts or '-v' in global_opts:
        print(f"Mantis v{VERSION}")
        return

    # Handle --help: show help for first command
    if '--help' in global_opts or '-h' in global_opts:
        sys.argv = [sys.argv[0]] + cmd_groups[0][:1] + ['--help']
        app()
        return

    # Check if any command has --help in its args
    for cmd_group in cmd_groups:
        if '--help' in cmd_group or '-h' in cmd_group:
            sys.argv = [sys.argv[0]] + cmd_group[:1] + ['--help']
            app()
            return

    # Single command without chaining - delegate to Typer for normal flow
    if len(cmd_groups) == 1:
        sys.argv = [sys.argv[0]] + global_opts + cmd_groups[0]
        app()
        return

    # Multiple commands - parse options and initialize state manually
    opts = parse_global_options(global_opts)
    state._mode = opts['mode']
    state._dry_run = opts['dry_run']
    state._manager = get_manager(opts['env'], opts['mode'], dry_run=opts['dry_run'])

    # Get Click app from Typer
    click_app = typer.main.get_command(app)

    # Create parent context and invoke each command
    try:
        with click_app.make_context('mantis', [], resilient_parsing=True) as parent_ctx:
            for cmd_group in cmd_groups:
                cmd_name = cmd_group[0]
                cmd_args = cmd_group[1:]
                invoke_command(click_app, cmd_name, cmd_args, parent_ctx)
    except click.exceptions.Exit:
        pass


if __name__ == "__main__":
    run()
