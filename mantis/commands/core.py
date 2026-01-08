"""Core commands: status, deploy, clean, upload."""
from typing import Optional, List

import typer

from mantis.app import command, state


@command(shortcut="s")
def status():
    """Prints images and containers"""
    state.status()


@command(shortcut="d")
def deploy(
    dirty: bool = typer.Option(False, "--dirty", help="Skip clean step"),
    strategy: str = typer.Option("blue-green", "--strategy", "-s", help="Deployment strategy: rolling (one-by-one) or blue-green (scale 2x)"),
):
    """Runs deployment process"""
    state.deploy(dirty=dirty, strategy=strategy)


@command(name="rolling-update", shortcut="ru")
def rolling_update(
    service: Optional[str] = typer.Argument(None, help="Service to update (default: all zero_downtime services)"),
):
    """Performs rolling update of containers one-by-one"""
    state.rolling_update(service=service)


@command(shortcut="c")
def clean(
    params: Optional[List[str]] = typer.Argument(None, help="Clean parameters"),
):
    """Clean images, containers, networks"""
    state.clean(params=params)


@command(shortcut="u", panel="Files")
def upload():
    """Uploads config, compose and environment files to server"""
    state.upload()
