"""Compose commands: up, down, run."""
from typing import Optional, List

import typer

from mantis.app import command, state


@command(panel="Compose")
def up(
    params: Optional[List[str]] = typer.Argument(None, help="Compose up parameters"),
):
    """Calls compose up"""
    state.up(params=params)


@command(panel="Compose")
def down(
    params: Optional[List[str]] = typer.Argument(None, help="Compose down parameters"),
):
    """Calls compose down"""
    state.down(params=params)


@command(name="run", panel="Compose")
def run_cmd(
    params: List[str] = typer.Argument(..., help="Compose run parameters"),
):
    """Calls compose run with params"""
    state.run(params=params)
