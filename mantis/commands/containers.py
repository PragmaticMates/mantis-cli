"""Container commands: logs, start, stop, kill, remove, bash, sh, exec, etc."""
from typing import Optional, List

import typer

from mantis.app import command, state, join_args


@command(shortcut="l", panel="Containers")
def logs(
    container: Optional[str] = typer.Argument(None, help="Container name"),
):
    """Prints logs of containers"""
    state.logs(container)


@command(shortcut="n", panel="Containers")
def networks():
    """Prints docker networks"""
    state.networks()


@command(shortcut="hc", panel="Containers")
def healthcheck(
    container: Optional[str] = typer.Argument(None, help="Container name"),
):
    """Execute health-check of container"""
    state.healthcheck(container)


@command(panel="Containers")
def stop(
    containers: Optional[List[str]] = typer.Argument(None, help="Containers to stop"),
):
    """Stops containers"""
    state.stop(join_args(containers) or None)


@command(panel="Containers")
def start(
    containers: Optional[List[str]] = typer.Argument(None, help="Containers to start"),
):
    """Starts containers"""
    state.start(join_args(containers))


@command(panel="Containers")
def kill(
    containers: Optional[List[str]] = typer.Argument(None, help="Containers to kill"),
):
    """Kills containers"""
    state.kill(join_args(containers) or None)


@command(panel="Containers")
def remove(
    containers: Optional[List[str]] = typer.Argument(None, help="Containers to remove"),
):
    """Removes containers"""
    state.remove(join_args(containers))


@command(panel="Containers")
def bash(
    container: str = typer.Argument(..., help="Container name"),
):
    """Runs bash in container"""
    state.bash(container)


@command(panel="Containers")
def sh(
    container: str = typer.Argument(..., help="Container name"),
):
    """Runs sh in container"""
    state.sh(container)


@command(name="exec", panel="Containers")
def exec_cmd(
    container: str = typer.Argument(..., help="Container name"),
    cmd: List[str] = typer.Argument(..., help="Command to execute"),
):
    """Executes command in container"""
    state.exec(f"{container} {join_args(cmd)}")


@command(name="exec-it", panel="Containers")
def exec_it(
    container: str = typer.Argument(..., help="Container name"),
    cmd: List[str] = typer.Argument(..., help="Command to execute"),
):
    """Executes command in container (interactive)"""
    state.exec_it(f"{container} {join_args(cmd)}")


@command(name="get-container-name", panel="Containers")
def get_container_name(
    service: str = typer.Argument(..., help="Service name"),
):
    """Gets container name for service"""
    print(state.get_container_name(service))


@command(name="remove-suffixes", panel="Containers")
def remove_suffixes(
    prefix: str = typer.Argument("", help="Prefix to match"),
):
    """Removes numerical suffixes from container names"""
    state.remove_suffixes(prefix)
