"""Image commands: build, pull, push, get-image-name."""
from typing import Optional, List

import typer

from mantis.app import command, state


@command(shortcut="b", panel="Images")
def build(
    services: Optional[List[str]] = typer.Argument(None, help="Services to build"),
):
    """Builds all services with Dockerfiles"""
    state.build(services=services)


@command(shortcut="pl", panel="Images")
def pull(
    services: Optional[List[str]] = typer.Argument(None, help="Services to pull"),
):
    """Pulls required images for services"""
    state.pull(services=services)


@command(shortcut="p", panel="Images")
def push(
    services: Optional[List[str]] = typer.Argument(None, help="Services to push"),
):
    """Push built images to repository"""
    state.push(services=services)


@command(name="get-image-name", panel="Images")
def get_image_name(
    service: str = typer.Argument(..., help="Service name"),
):
    """Gets image name for service"""
    print(state.get_image_name(service))
