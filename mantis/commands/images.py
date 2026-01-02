"""Image commands: build, pull, push, get-image-name."""
from typing import Optional, List

import typer

from mantis.app import command, state, join_args


@command(shortcut="b", panel="Images")
def build(
    services: Optional[List[str]] = typer.Argument(None, help="Services to build"),
):
    """Builds all services with Dockerfiles"""
    state.build(join_args(services))


@command(shortcut="pl", panel="Images")
def pull(
    services: Optional[List[str]] = typer.Argument(None, help="Services to pull"),
):
    """Pulls required images for services"""
    state.pull(join_args(services))


@command(shortcut="p", panel="Images")
def push(
    services: Optional[List[str]] = typer.Argument(None, help="Services to push"),
):
    """Push built images to repository"""
    state.push(join_args(services))


@command(name="get-image-name", panel="Images")
def get_image_name(
    service: str = typer.Argument(..., help="Service name"),
):
    """Gets image name for service"""
    print(state.get_image_name(service))
