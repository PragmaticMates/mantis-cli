"""
Command registry for mantis-cli using Typer-style argument definitions.
"""
from typing import Callable, Dict, List, Optional
import typer

# Global command registry
COMMANDS: Dict[str, 'Command'] = {}

# Commands that don't require environment
NO_ENV_COMMANDS = {'generate-key', 'check-config', 'contexts', 'create-context', 'read-key', 'commands'}


class Command:
    """Wraps a command function with metadata for argument parsing."""

    def __init__(self, func: Callable, name: str, shortcuts: List[str] = None):
        self.func = func
        self.name = name
        self.shortcuts = shortcuts or []
        self.doc = func.__doc__ or ''

    def execute(self, manager, args: List[str] = None):
        """Execute command with the manager and optional arguments."""
        if args is None:
            args = []

        # For commands with no args, just call with manager
        if not args:
            return self.func(manager)

        # Parse args and call function
        # Simple approach: pass args as positional parameters
        return self.func(manager, *args)


def command(name: str = None, shortcuts: List[str] = None):
    """Decorator to register a command."""
    def decorator(func):
        cmd_name = name or func.__name__.replace('_', '-')
        cmd = Command(func, cmd_name, shortcuts)
        COMMANDS[cmd_name] = cmd
        if shortcuts:
            for shortcut in shortcuts:
                COMMANDS[shortcut] = cmd
        return func
    return decorator


def get_command(name: str) -> Optional[Command]:
    """Get a command by name or shortcut."""
    return COMMANDS.get(name)


def list_commands() -> Dict[str, Command]:
    """Return all registered commands (excluding shortcuts)."""
    return {name: cmd for name, cmd in COMMANDS.items() if len(name) > 2 or name == cmd.name}


# =============================================================================
# Base Commands (from BaseManager)
# =============================================================================

@command(shortcuts=['s'])
def status(manager):
    """Prints images and containers"""
    manager.status()


@command(shortcuts=['d'])
def deploy(manager, *args):
    """Runs deployment process"""
    dirty = 'dirty' in args or '--dirty' in args
    manager.deploy(dirty=dirty)


@command(shortcuts=['b'])
def build(manager, *args):
    """Builds all services with Dockerfiles"""
    params = ' '.join(args) if args else ''
    manager.build(params)


@command(shortcuts=['p'])
def pull(manager, *args):
    """Pulls required images for services"""
    params = ' '.join(args) if args else ''
    manager.pull(params)


@command(shortcuts=['u'])
def upload(manager):
    """Uploads mantis config, compose file and environment files to server"""
    manager.upload()


@command(shortcuts=['c'])
def clean(manager, *args):
    """Clean images, containers, networks"""
    params = ' '.join(args) if args else ''
    manager.clean(params)


@command(shortcuts=['l'])
def logs(manager, *args):
    """Prints logs of all or given project container"""
    params = ' '.join(args) if args else None
    manager.logs(params)


@command(shortcuts=['n'])
def networks(manager):
    """Prints docker networks"""
    manager.networks()


@command(shortcuts=['hc'])
def healthcheck(manager, container: str = None):
    """Execute health-check of given project container"""
    manager.healthcheck(container)


@command()
def up(manager, *args):
    """Calls compose up (with optional params)"""
    params = ' '.join(args) if args else ''
    manager.up(params)


@command()
def down(manager, *args):
    """Calls compose down (with optional params)"""
    params = ' '.join(args) if args else ''
    manager.down(params)


@command()
def restart(manager, service: str = None):
    """Restarts all containers by calling compose down and up"""
    manager.restart(service)


@command()
def stop(manager, *args):
    """Stops all or given project container"""
    params = ' '.join(args) if args else None
    manager.stop(params)


@command()
def start(manager, *args):
    """Starts all or given project container"""
    params = ' '.join(args) if args else ''
    manager.start(params)


@command()
def kill(manager, *args):
    """Kills all or given project container"""
    params = ' '.join(args) if args else None
    manager.kill(params)


@command()
def remove(manager, *args):
    """Removes all or given project container"""
    params = ' '.join(args) if args else ''
    manager.remove(params)


@command()
def run(manager, *args):
    """Calls compose run with params"""
    if not args:
        typer.echo("Error: run requires parameters", err=True)
        raise typer.Exit(1)
    params = ' '.join(args)
    manager.run(params)


@command()
def bash(manager, container: str):
    """Runs bash in container"""
    if not container:
        typer.echo("Error: bash requires container name", err=True)
        raise typer.Exit(1)
    manager.bash(container)


@command()
def sh(manager, container: str):
    """Runs sh in container"""
    if not container:
        typer.echo("Error: sh requires container name", err=True)
        raise typer.Exit(1)
    manager.sh(container)


@command()
def ssh(manager):
    """Connects to remote host via SSH"""
    manager.ssh()


@command(name='exec')
def exec_cmd(manager, *args):
    """Executes command in container"""
    if not args:
        typer.echo("Error: exec requires container and command", err=True)
        raise typer.Exit(1)
    params = ' '.join(args)
    manager.exec(params)


@command(name='exec-it')
def exec_it(manager, *args):
    """Executes command in container using interactive pseudo-TTY"""
    if not args:
        typer.echo("Error: exec-it requires container and command", err=True)
        raise typer.Exit(1)
    params = ' '.join(args)
    manager.exec_it(params)


@command()
def scale(manager, service: str, num: str):
    """Scales service to given scale"""
    if not service or not num:
        typer.echo("Error: scale requires service and number", err=True)
        raise typer.Exit(1)
    manager.scale(service, int(num))


@command()
def push(manager, *args):
    """Push built images to repository"""
    params = ' '.join(args) if args else ''
    manager.push(params)


@command(name='zero-downtime')
def zero_downtime(manager, service: str = None):
    """Runs zero-downtime deployment of services (or given service)"""
    manager.zero_downtime(service)


@command(name='restart-service')
def restart_service(manager, service: str):
    """Stops, removes and recreates container for given service"""
    if not service:
        typer.echo("Error: restart-service requires service name", err=True)
        raise typer.Exit(1)
    manager.restart_service(service)


@command(name='remove-suffixes')
def remove_suffixes(manager, prefix: str = ''):
    """Removes numerical suffixes from container names (if scale == 1)"""
    manager.remove_suffixes(prefix)


@command(name='try-to-reload-webserver')
def try_to_reload_webserver(manager):
    """Tries to reload webserver (if suitable extension is available)"""
    manager.try_to_reload_webserver()


# Encryption commands

@command(name='encrypt-env')
def encrypt_env(manager, *args):
    """Encrypts all environment files (force param skips user confirmation)"""
    params = 'force' if 'force' in args or '--force' in args else ''
    manager.encrypt_env(params=params)


@command(name='decrypt-env')
def decrypt_env(manager, *args):
    """Decrypts all environment files (force param skips user confirmation)"""
    params = 'force' if 'force' in args or '--force' in args else ''
    manager.decrypt_env(params=params)


@command(name='check-env')
def check_env(manager):
    """Compares encrypted and decrypted env files"""
    manager.check_env()


@command(name='generate-key')
def generate_key(manager):
    """Creates new encryption key"""
    manager.generate_key()


@command(name='read-key')
def read_key(manager):
    """Returns value of mantis encryption key"""
    print(manager.read_key())


# Config commands

@command(name='check-config')
def check_config(manager):
    """Validates config file according to template"""
    manager.check_config()


# Docker context commands

@command()
def contexts(manager):
    """Prints all docker contexts"""
    manager.contexts()


@command(name='create-context')
def create_context(manager):
    """Creates docker context using user inputs"""
    manager.create_context()


# Service info commands

@command()
def services(manager):
    """Returns all defined services"""
    for service in manager.services():
        print(service)


@command(name='services-to-build')
def services_to_build(manager):
    """Prints all services which will be build"""
    for service, info in manager.services_to_build().items():
        print(f"{service}: {info}")


@command(name='get-container-name')
def get_container_name(manager, service: str):
    """Constructs container name with project prefix for given service"""
    print(manager.get_container_name(service))


@command(name='get-container-suffix')
def get_container_suffix(manager, service: str):
    """Returns the suffix used for containers for given service"""
    print(manager.get_container_suffix(service))


@command(name='get-image-name')
def get_image_name(manager, service: str):
    """Constructs image name for given service"""
    print(manager.get_image_name(service))


@command(name='get-image-suffix')
def get_image_suffix(manager, service: str):
    """Returns the suffix used for image for given service"""
    print(manager.get_image_suffix(service))


@command(name='get-service-containers')
def get_service_containers(manager, service: str):
    """Prints container names of given service"""
    for container in manager.get_service_containers(service):
        print(container)


@command(name='get-number-of-containers')
def get_number_of_containers(manager, service: str):
    """Prints number of containers for given service"""
    print(manager.get_number_of_containers(service))


@command(name='get-deploy-replicas')
def get_deploy_replicas(manager, service: str):
    """Returns default number of deploy replicas of given services"""
    print(manager.get_deploy_replicas(service))


# Health check commands

@command(name='has-healthcheck')
def has_healthcheck(manager, container: str):
    """Checks if given container has defined healthcheck"""
    print(manager.has_healthcheck(container))


@command(name='get-healthcheck-config')
def get_healthcheck_config(manager, container: str):
    """Prints health-check config (if any) of given container"""
    print(manager.get_healthcheck_config(container))


@command(name='get-healthcheck-start-period')
def get_healthcheck_start_period(manager, container: str):
    """Returns healthcheck start period for given container (if any)"""
    print(manager.get_healthcheck_start_period(container))


@command(name='check-health')
def check_health(manager, container: str):
    """Checks current health of given container"""
    result = manager.check_health(container)
    if result:
        is_healthy, status = result
        print(f"Healthy: {is_healthy}, Status: {status}")


# Volume commands

@command(name='backup-volume')
def backup_volume(manager, volume: str):
    """Backups volume to a file"""
    if not volume:
        typer.echo("Error: backup-volume requires volume name", err=True)
        raise typer.Exit(1)
    manager.backup_volume(volume)


@command(name='restore-volume')
def restore_volume(manager, volume: str, file: str):
    """Restores volume from a file"""
    if not volume or not file:
        typer.echo("Error: restore-volume requires volume and file", err=True)
        raise typer.Exit(1)
    manager.restore_volume(volume, file)


# Help command

@command()
def commands(manager):
    """Lists all available commands"""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(show_header=True, header_style="bold")
    table.add_column("Command", style="cyan")
    table.add_column("Shortcuts", style="yellow")
    table.add_column("Description")

    # Get unique commands (not shortcuts)
    seen = set()
    for name, cmd in sorted(COMMANDS.items()):
        if cmd.name not in seen:
            seen.add(cmd.name)
            shortcuts = ', '.join(cmd.shortcuts) if cmd.shortcuts else ''
            table.add_row(cmd.name, shortcuts, cmd.doc.strip())

    console.print(table)
