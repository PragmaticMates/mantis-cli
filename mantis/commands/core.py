"""Core commands: status, deploy, clean, upload."""
from typing import Optional, List

import typer

from mantis.app import command, state, join_args


@command(shortcut="s")
def status():
    """Prints images and containers"""
    state.status()


@command(shortcut="d")
def deploy(
    dirty: bool = typer.Option(False, "--dirty", help="Skip clean step"),
):
    """Runs deployment process"""
    state.deploy(dirty=dirty)


@command(shortcut="c")
def clean(
    params: Optional[List[str]] = typer.Argument(None, help="Clean parameters"),
):
    """Clean images, containers, networks"""
    state.clean(join_args(params))


@command(shortcut="u", panel="Files")
def upload():
    """Uploads config, compose and environment files to server"""
    state.upload()
