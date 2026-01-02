#!/usr/bin/env python
import os
import sys
import inspect

from rich.console import Console
from rich.table import Table

from mantis import VERSION
from mantis.helpers import CLI, nested_set
from mantis.logic import get_manager, execute
from mantis.managers import AbstractManager, BaseManager
from mantis.extensions.django import Django
from mantis.extensions.nginx import Nginx
from mantis.extensions.postgres import Postgres


def parse_args(arguments):
    d = {
        'environment_id': None,
        'commands': [],
        'settings': {}
    }

    for arg in arguments:
        if not arg.startswith('-'):
            d['environment_id'] = arg
        # elif '=' in arg and ':' not in arg:
        elif '=' in arg:
            s, v = arg.split('=', maxsplit=1)
            d['settings'][s.strip('-')] = v
        else:
            d['commands'].append(arg)

    return d


def run():
    arguments = sys.argv.copy()
    arguments.pop(0)

    # check params
    params = parse_args(arguments)

    # version info
    version_info = f'Mantis v{VERSION}'

    if params['commands'] == ['--version']:
        return print(version_info)

    if params['commands'] == ['--help']:
        return help()

    # get params
    environment_id = params['environment_id']
    commands = params['commands']
    mode = params['settings'].get('mode', 'remote')

    # get manager
    manager = get_manager(environment_id, mode)

    if len(params['commands']) == 0:
        CLI.error('Missing commands. Check mantis --help for more information.')

    if mode not in ['remote', 'ssh', 'host']:
        CLI.error('Incorrect mode. Check mantis --help for more information.')

    hostname = os.popen('hostname').read().rstrip("\n")

    # check config settings
    settings_config = params['settings'].get('config', None)

    if settings_config:
        # override manager config
        for override_config in settings_config.split(','):
            key, value = override_config.split('=')
            nested_set(
                dic=manager.config,
                keys=key.split('.'),
                value=value
            )

    console = Console()

    if manager.environment_id:
        environment_intro = f'Environment ID = [bold]{manager.environment_id}[/bold], '
    elif manager.single_connection_mode:
        environment_intro = '[bold](single connection mode)[/bold], '
    else:
        environment_intro = ''

    if manager.connection and manager.host:
        host_intro = f'[red]{manager.host}[/red], '
    else:
        host_intro = ''

    heading = f'{version_info}, '\
              f'{environment_intro}'\
              f'{host_intro}'\
              f'mode: [green]{manager.mode}[/green], '\
              f'hostname: [blue]{hostname}[/blue]'

    console.print(heading)

    if mode == 'ssh':
        # Build mantis command - environment_id is optional in single connection mode
        env_part = f'{environment_id} ' if environment_id else ''
        cmds = [
            f'cd {manager.project_path}',
            f'mantis {env_part}--mode=host {" ".join(commands)}'
        ]
        cmd = ';'.join(cmds)
        exec = f"ssh -t {manager.user}@{manager.host} -p {manager.port} '{cmd}'"
        os.system(exec)
    else:
        # execute all commands
        for command in commands:
            if ':' in command:
                command, params = command.split(':')
                params = params.split(',')
            else:
                params = []

            execute(manager, command, params)

def get_class_commands(cls, exclude_from=None):
    """
    Extract commands from a class for help display.
    Returns list of tuples: (command_str, description)
    """
    commands = []
    exclude_methods = dir(exclude_from) if exclude_from else []

    methods = inspect.getmembers(cls, predicate=inspect.isfunction)

    for method_name, method in methods:
        # skip private methods and excluded methods
        if method_name.startswith('_') or method_name in exclude_methods:
            continue

        command = method_name.replace('_', '-')

        # Get the method signature
        signature = inspect.signature(method)

        # Parameters (skip 'self')
        parameters = [p for p in signature.parameters.keys() if p != 'self']

        # Check if parameters are optional
        params_are_optional = True

        for param_name, param in signature.parameters.items():
            if param_name == 'self':
                continue
            if param.default == inspect.Parameter.empty:
                params_are_optional = False

        # Build command string
        command = f"--{command}"
        params_str = ""

        if parameters:
            if not params_are_optional:
                params_str += '['

            params_str += ':'

            params_str += ','.join(parameters)

            if not params_are_optional:
                params_str += ']'

        docs = method.__doc__ or ''

        commands.append((f"{command}{params_str}", docs.strip()))

    return commands


def help():
    print(f'\nUsage:\n\
    mantis [--mode=remote|ssh|host] [environment] --command[:params]')

    print('\nModes:\n\
    remote \truns commands remotely from local machine using DOCKER_HOST or DOCKER_CONTEXT (default)\n\
    ssh \tconnects to host via ssh and run all mantis commands on remote machine directly (mantis-cli needs to be installed on server)\n\
    host \truns mantis on host machine directly without invoking connection (used as proxy for ssh mode)')

    print(f'\nEnvironment:\n\
    Either "local" or any custom environment identifier defined as connection in your config file.\n\
    Optional when using single connection mode (config has "connection" instead of "connections").')

    console = Console()

    # Base commands
    print(f'\nCommands:')
    table = Table(show_header=True, header_style="bold")
    table.add_column("Command", style="cyan")
    table.add_column("Description")

    for command, description in get_class_commands(BaseManager, exclude_from=AbstractManager):
        table.add_row(command, description)

    console.print(table)

    # Extension commands
    extensions = [
        ('Django', Django),
        ('Nginx', Nginx),
        ('Postgres', Postgres),
    ]

    for ext_name, ext_class in extensions:
        ext_commands = get_class_commands(ext_class)
        if ext_commands:
            print(f'\n{ext_name} extension:')
            ext_table = Table(show_header=True, header_style="bold")
            ext_table.add_column("Command", style="yellow")
            ext_table.add_column("Description")

            for command, description in ext_commands:
                ext_table.add_row(command, description)

            console.print(ext_table)
