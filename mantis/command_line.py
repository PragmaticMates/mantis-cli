#!/usr/bin/env python
"""
Mantis CLI - Docker deployment tool

Usage:
    mantis [OPTIONS] COMMAND [ARGS]... [COMMAND [ARGS]...]

Examples:
    mantis -e production status
    mantis -e production deploy --dirty
    mantis -e production build push deploy
    mantis status                          (single connection mode)
    mantis manage migrate
"""
import inspect
import os
from typing import Optional, List

import typer
from rich.console import Console
from rich.text import Text

from mantis import VERSION
from mantis.helpers import CLI
from mantis.logic import get_manager

EPILOG = """\
[bold]Examples:[/bold]

  mantis -e production status

  mantis -e production deploy --dirty

  mantis -e production build push deploy

  mantis -e prod manage migrate --fake

  mantis -e prod pg-dump --data-only --table users

  mantis -e prod bash web

  mantis -e prod logs django

  mantis status [dim](single connection mode)[/dim]



[bold]Get help for a specific command:[/bold]

  mantis COMMAND --help
"""

app = typer.Typer(
    chain=True,
    no_args_is_help=True,
    rich_markup_mode="rich",
    epilog=EPILOG,
    context_settings={"max_content_width": 120},
)

# Commands that don't require environment
NO_ENV_COMMANDS = {'generate-key', 'check-config', 'contexts', 'create-context', 'read-key'}


def print_heading(manager, mode: str):
    """Print the heading with environment and connection info."""
    console = Console()
    hostname = os.popen('hostname').read().rstrip("\n")

    heading = Text()
    heading.append(f'Mantis v{VERSION}')
    heading.append(", ")

    if manager.environment_id:
        heading.append("Environment ID = ")
        heading.append(str(manager.environment_id), style="bold")
        heading.append(", ")
    elif manager.single_connection_mode:
        heading.append("(single connection mode)", style="bold")
        heading.append(", ")

    if manager.connection and manager.host:
        heading.append(str(manager.host), style="red")
        heading.append(", ")

    heading.append("mode: ")
    heading.append(str(mode), style="green")
    heading.append(", hostname: ")
    heading.append(hostname, style="blue")

    console.print(heading)


class State:
    """Shared state across commands."""
    def __init__(self):
        self._manager = None
        self._mode = 'remote'
        self._heading_printed = False

    def _ensure_ready(self, command_name: str):
        """Print heading and validate environment."""
        if not self._heading_printed:
            print_heading(self._manager, self._mode)
            self._heading_printed = True

        if command_name not in NO_ENV_COMMANDS:
            if not self._manager.single_connection_mode and self._manager.environment_id is None:
                CLI.error(f'Command "{command_name}" requires environment. Use: mantis -e <environment> {command_name}')

    def __getattr__(self, name):
        """Delegate method calls to manager, handling heading and validation."""
        # Get the caller function name (the command)
        caller = inspect.stack()[1].function
        command_name = caller.replace('_', '-')
        self._ensure_ready(command_name)
        return getattr(self._manager, name)


state = State()


def add_shortcut(name: str, shortcut: str, func, panel: str = "Shortcuts"):
    """Register a command shortcut."""
    app.command(shortcut, rich_help_panel=panel, help=f"Alias for '{name}'")(func)


def version_callback(value: bool):
    if value:
        typer.echo(f"Mantis v{VERSION}")
        raise typer.Exit()


@app.callback()
def main(
    environment: Optional[str] = typer.Option(None, "--env", "-e", help="Environment ID"),
    mode: str = typer.Option("remote", "--mode", "-m", help="Execution mode: remote, ssh, host"),
    version: bool = typer.Option(False, "--version", "-v", callback=version_callback, is_eager=True, help="Show version and exit"),
):
    """Mantis CLI - Docker deployment tool."""
    state._mode = mode
    state._manager = get_manager(environment, mode)


# =============================================================================
# Core Commands
# =============================================================================

@app.command()
def status():
    """Prints images and containers"""
    state.status()


@app.command()
def deploy(
    dirty: bool = typer.Option(False, "--dirty", help="Skip clean step"),
):
    """Runs deployment process"""
    state.deploy(dirty=dirty)


@app.command(rich_help_panel="Images")
def build(
    services: Optional[List[str]] = typer.Argument(None, help="Services to build"),
):
    """Builds all services with Dockerfiles"""
    state.build(' '.join(services) if services else '')


@app.command(rich_help_panel="Images")
def pull(
    services: Optional[List[str]] = typer.Argument(None, help="Services to pull"),
):
    """Pulls required images for services"""
    state.pull(' '.join(services) if services else '')


@app.command(rich_help_panel="Images")
def push(
    services: Optional[List[str]] = typer.Argument(None, help="Services to push"),
):
    """Push built images to repository"""
    state.push(' '.join(services) if services else '')


@app.command(rich_help_panel="Files")
def upload():
    """Uploads config, compose and environment files to server"""
    state.upload()


@app.command()
def clean(
    params: Optional[List[str]] = typer.Argument(None, help="Clean parameters"),
):
    """Clean images, containers, networks"""
    state.clean(' '.join(params) if params else '')


@app.command(rich_help_panel="Containers")
def logs(
    container: Optional[str] = typer.Argument(None, help="Container name"),
):
    """Prints logs of containers"""
    state.logs(container)


@app.command(rich_help_panel="Containers")
def networks():
    """Prints docker networks"""
    state.networks()


@app.command(rich_help_panel="Containers")
def healthcheck(
    container: Optional[str] = typer.Argument(None, help="Container name"),
):
    """Execute health-check of container"""
    state.healthcheck(container)


@app.command(rich_help_panel="Compose")
def up(
    params: Optional[List[str]] = typer.Argument(None, help="Compose up parameters"),
):
    """Calls compose up"""
    state.up(' '.join(params) if params else '')


@app.command(rich_help_panel="Compose")
def down(
    params: Optional[List[str]] = typer.Argument(None, help="Compose down parameters"),
):
    """Calls compose down"""
    state.down(' '.join(params) if params else '')


@app.command(rich_help_panel="Services")
def restart(
    service: Optional[str] = typer.Argument(None, help="Service to restart"),
):
    """Restarts containers"""
    state.restart(service)


@app.command(rich_help_panel="Containers")
def stop(
    containers: Optional[List[str]] = typer.Argument(None, help="Containers to stop"),
):
    """Stops containers"""
    state.stop(' '.join(containers) if containers else None)


@app.command(rich_help_panel="Containers")
def start(
    containers: Optional[List[str]] = typer.Argument(None, help="Containers to start"),
):
    """Starts containers"""
    state.start(' '.join(containers) if containers else '')


@app.command(rich_help_panel="Containers")
def kill(
    containers: Optional[List[str]] = typer.Argument(None, help="Containers to kill"),
):
    """Kills containers"""
    state.kill(' '.join(containers) if containers else None)


@app.command(rich_help_panel="Containers")
def remove(
    containers: Optional[List[str]] = typer.Argument(None, help="Containers to remove"),
):
    """Removes containers"""
    state.remove(' '.join(containers) if containers else '')


@app.command("run", rich_help_panel="Compose")
def run_cmd(
    params: List[str] = typer.Argument(..., help="Compose run parameters"),
):
    """Calls compose run with params"""
    state.run(' '.join(params))


@app.command(rich_help_panel="Containers")
def bash(
    container: str = typer.Argument(..., help="Container name"),
):
    """Runs bash in container"""
    state.bash(container)


@app.command(rich_help_panel="Containers")
def sh(
    container: str = typer.Argument(..., help="Container name"),
):
    """Runs sh in container"""
    state.sh(container)


@app.command("ssh", rich_help_panel="Connections")
def ssh_cmd():
    """Connects to remote host via SSH"""
    state.ssh()


@app.command("exec", rich_help_panel="Containers")
def exec_cmd(
    container: str = typer.Argument(..., help="Container name"),
    command: List[str] = typer.Argument(..., help="Command to execute"),
):
    """Executes command in container"""
    state.exec(f"{container} {' '.join(command)}")


@app.command("exec-it", rich_help_panel="Containers")
def exec_it(
    container: str = typer.Argument(..., help="Container name"),
    command: List[str] = typer.Argument(..., help="Command to execute"),
):
    """Executes command in container (interactive)"""
    state.exec_it(f"{container} {' '.join(command)}")


@app.command(rich_help_panel="Services")
def scale(
    service: str = typer.Argument(..., help="Service name"),
    num: int = typer.Argument(..., help="Number of instances"),
):
    """Scales service to given number"""
    state.scale(service, num)


@app.command("zero-downtime", rich_help_panel="Services")
def zero_downtime(
    service: Optional[str] = typer.Argument(None, help="Service name"),
):
    """Runs zero-downtime deployment"""
    state.zero_downtime(service)


@app.command("restart-service", rich_help_panel="Services")
def restart_service(
    service: str = typer.Argument(..., help="Service name"),
):
    """Restarts a specific service"""
    state.restart_service(service)


@app.command("remove-suffixes", rich_help_panel="Containers")
def remove_suffixes(
    prefix: str = typer.Argument("", help="Prefix to match"),
):
    """Removes numerical suffixes from container names"""
    state.remove_suffixes(prefix)


# =============================================================================
# Encryption Commands
# =============================================================================

@app.command("encrypt-env", rich_help_panel="Cryptography")
def encrypt_env(
    force: bool = typer.Option(False, "--force", help="Skip confirmation"),
):
    """Encrypts environment files"""
    state.encrypt_env(params='force' if force else '')


@app.command("decrypt-env", rich_help_panel="Cryptography")
def decrypt_env(
    force: bool = typer.Option(False, "--force", help="Skip confirmation"),
):
    """Decrypts environment files"""
    state.decrypt_env(params='force' if force else '')


@app.command("check-env", rich_help_panel="Cryptography")
def check_env():
    """Compares encrypted and decrypted env files"""
    state.check_env()


@app.command("generate-key", rich_help_panel="Cryptography")
def generate_key():
    """Creates new encryption key"""
    state.generate_key()


@app.command("read-key", rich_help_panel="Cryptography")
def read_key():
    """Returns encryption key value"""
    print(state.read_key())


# =============================================================================
# Config Commands
# =============================================================================

@app.command("check-config")
def check_config():
    """Validates config file"""
    state.check_config()


@app.command(rich_help_panel="Connections")
def contexts():
    """Prints all docker contexts"""
    state.contexts()


@app.command("create-context", rich_help_panel="Connections")
def create_context():
    """Creates docker context"""
    state.create_context()


# =============================================================================
# Service Info Commands
# =============================================================================

@app.command(rich_help_panel="Services")
def services():
    """Lists all defined services"""
    for service in state.services():
        print(service)


@app.command("services-to-build", rich_help_panel="Services")
def services_to_build():
    """Lists services that will be built"""
    for service, info in state.services_to_build().items():
        print(f"{service}: {info}")


@app.command("get-container-name", rich_help_panel="Containers")
def get_container_name(
    service: str = typer.Argument(..., help="Service name"),
):
    """Gets container name for service"""
    print(state.get_container_name(service))


@app.command("get-image-name", rich_help_panel="Images")
def get_image_name(
    service: str = typer.Argument(..., help="Service name"),
):
    """Gets image name for service"""
    print(state.get_image_name(service))


# =============================================================================
# Volume Commands
# =============================================================================

@app.command("backup-volume", rich_help_panel="Volumes")
def backup_volume(
    volume: str = typer.Argument(..., help="Volume name"),
):
    """Backups volume to a file"""
    state.backup_volume(volume)


@app.command("restore-volume", rich_help_panel="Volumes")
def restore_volume(
    volume: str = typer.Argument(..., help="Volume name"),
    file: str = typer.Argument(..., help="Backup file"),
):
    """Restores volume from a file"""
    state.restore_volume(volume, file)


# =============================================================================
# Django Extension Commands
# =============================================================================

@app.command(rich_help_panel="Django")
def shell():
    """Runs Django shell"""
    state.shell()


@app.command(rich_help_panel="Django")
def manage(
    command: str = typer.Argument(..., help="Django management command"),
    args: Optional[List[str]] = typer.Argument(None, help="Command arguments"),
):
    """Runs Django manage command"""
    full_cmd = command + (' ' + ' '.join(args) if args else '')
    state.manage(full_cmd)


@app.command("send-test-email", rich_help_panel="Django")
def send_test_email():
    """Sends test email to admins"""
    state.send_test_email()


# =============================================================================
# PostgreSQL Extension Commands
# =============================================================================

@app.command(rich_help_panel="PostgreSQL")
def psql():
    """Starts psql console"""
    state.psql()


@app.command("pg-dump", rich_help_panel="PostgreSQL")
def pg_dump(
    data_only: bool = typer.Option(False, "--data-only", "-d", help="Dump data only"),
    table: Optional[str] = typer.Option(None, "--table", "-t", help="Specific table"),
):
    """Backups PostgreSQL database"""
    state.pg_dump(data_only=data_only, table=table)


@app.command("pg-dump-data", rich_help_panel="PostgreSQL")
def pg_dump_data(
    table: Optional[str] = typer.Option(None, "--table", "-t", help="Specific table"),
):
    """Backups PostgreSQL database (data only)"""
    state.pg_dump_data(table=table)


@app.command("pg-restore", rich_help_panel="PostgreSQL")
def pg_restore(
    filename: str = typer.Argument(..., help="Backup filename"),
    table: Optional[str] = typer.Option(None, "--table", "-t", help="Specific table"),
):
    """Restores database from backup"""
    state.pg_restore(filename=filename, table=table)


@app.command("pg-restore-data", rich_help_panel="PostgreSQL")
def pg_restore_data(
    filename: str = typer.Argument(..., help="Backup filename"),
    table: str = typer.Argument(..., help="Table name"),
):
    """Restores database data from backup"""
    state.pg_restore(filename=filename, table=table)


# =============================================================================
# Nginx Extension Commands
# =============================================================================

@app.command("reload-webserver", rich_help_panel="Nginx")
def reload_webserver():
    """Reloads nginx webserver"""
    state.reload_webserver()


# =============================================================================
# Command Shortcuts (hidden from help)
# =============================================================================

add_shortcut("status", "s", status)
add_shortcut("deploy", "d", deploy)
add_shortcut("build", "b", build)
add_shortcut("pull", "pl", pull)
add_shortcut("push", "p", push)
add_shortcut("upload", "u", upload)
add_shortcut("clean", "c", clean)
add_shortcut("logs", "l", logs)
add_shortcut("networks", "n", networks)
add_shortcut("healthcheck", "hc", healthcheck)


def run():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    run()
