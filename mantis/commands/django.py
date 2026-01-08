"""Django extension commands: shell, manage, send-test-email."""
from typing import Optional, List

import typer

from mantis.app import command, state


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
    state.manage(cmd=cmd, args=args)


@command(name="send-test-email", panel="Django")
def send_test_email():
    """Sends test email to admins"""
    state.send_test_email()
