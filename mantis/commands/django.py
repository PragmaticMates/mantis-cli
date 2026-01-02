"""Django extension commands: shell, manage, send-test-email."""
from typing import Optional, List

import typer

from mantis.app import command, state, join_args


@command(panel="Django")
def shell():
    """Runs Django shell"""
    state.shell()


@command(panel="Django")
def manage(
    cmd: str = typer.Argument(..., help="Django management command"),
    args: Optional[List[str]] = typer.Argument(None, help="Command arguments"),
):
    """Runs Django manage command"""
    full_cmd = cmd + (' ' + join_args(args) if args else '')
    state.manage(full_cmd)


@command(name="send-test-email", panel="Django")
def send_test_email():
    """Sends test email to admins"""
    state.send_test_email()
