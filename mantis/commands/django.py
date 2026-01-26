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
    if_healthy: bool = typer.Option(False, "--if-healthy", help="Only execute if container is healthy"),
    healthy_timeout: Optional[int] = typer.Option(None, "--healthy-timeout", help="Wait up to N seconds for container to become healthy"),
):
    """Runs Django manage command"""
    state.manage(cmd=cmd, args=args, if_healthy=if_healthy, healthy_timeout=healthy_timeout)


@command(name="send-test-email", panel="Django")
def send_test_email():
    """Sends test email to admins"""
    state.send_test_email()


@command(name="reset-migrations", panel="Django")
def reset_migrations():
    """Clears migration history and fakes all migrations"""
    state.reset_migrations()
