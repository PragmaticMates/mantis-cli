"""Service commands: restart, scale, zero-downtime, services, etc."""
from typing import Optional

import typer

from mantis.app import command, state


@command(panel="Services")
def restart(
    service: Optional[str] = typer.Argument(None, help="Service to restart"),
):
    """Restarts containers"""
    state.restart(service)


@command(panel="Services")
def scale(
    service: str = typer.Argument(..., help="Service name"),
    num: int = typer.Argument(..., help="Number of instances"),
):
    """Scales service to given number"""
    state.scale(service, num)


@command(name="zero-downtime", panel="Services")
def zero_downtime(
    service: Optional[str] = typer.Argument(None, help="Service name"),
):
    """Runs zero-downtime deployment"""
    state.zero_downtime(service)


@command(name="restart-service", panel="Services")
def restart_service(
    service: str = typer.Argument(..., help="Service name"),
):
    """Restarts a specific service"""
    state.restart_service(service)


@command(panel="Services")
def services():
    """Lists all defined services"""
    for service in state.services():
        print(service)


@command(name="services-to-build", panel="Services")
def services_to_build():
    """Lists services that will be built"""
    for service, info in state.services_to_build().items():
        print(f"{service}: {info}")
