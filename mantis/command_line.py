#!/usr/bin/env python
import os
import sys
import inspect
import prettytable

from mantis import VERSION
from mantis.helpers import Colors, CLI, nested_set
from mantis.logic import get_manager, execute
from mantis.managers import AbstractManager


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

    # get params
    environment_id = params['environment_id']
    commands = params['commands']
    mode = params['settings'].get('mode', 'remote')

    # get manager
    manager = get_manager(environment_id, mode)

    if params['commands'] == ['--help']:
        return help(manager)

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

    environment_intro = f'Environment ID = {Colors.BOLD}{manager.environment_id}{Colors.ENDC}, ' if manager.environment_id else ''

    if manager.connection and manager.host:
        host_intro = f'{Colors.RED}{manager.host}{Colors.ENDC}, '
    else:
        host_intro = ''

    heading = f'{version_info}, '\
              f'{environment_intro}'\
              f'{host_intro}'\
              f'mode: {Colors.GREEN}{manager.mode}{Colors.ENDC}, '\
              f'hostname: {Colors.BLUE}{hostname}{Colors.ENDC}'

    print(heading)

    if mode == 'ssh':
        cmds = [
            f'cd {manager.project_path}',
            f'mantis {environment_id} --mode=host {" ".join(commands)}'
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

def help(manager):
    print(f'\nUsage:\n\
    mantis [--mode=remote|ssh|host] [environment] --command[:params]')

    print('\nModes:\n\
    remote \truns commands remotely from local machine using DOCKER_HOST or DOCKER_CONTEXT (default)\n\
    ssh \tconnects to host via ssh and run all mantis commands on remote machine directly (nantis-cli needs to be installed on server)\n\
    host \truns mantis on host machine directly without invoking connection (used as proxy for ssh mode)')

    print(f'\nEnvironment:\n\
    Either "local" or any custom environment identifier defined as connection in your config file.')

    print(f'\nCommands:')

    table = prettytable.PrettyTable(align='l')
    table.set_style(prettytable.SINGLE_BORDER)
    table.field_names = ["Command", "Description"]

    # Get all methods of the class
    methods = inspect.getmembers(manager, predicate=inspect.ismethod)

    # Iterate over each method
    for method_name, method in methods:
        # skip methods of abstract manager
        if method_name in dir(AbstractManager):
            continue

        command = method_name.replace('_', '-')

        # Get the method signature
        signature = inspect.signature(method)

        # Parameters
        parameters = list(signature.parameters.keys())

        # Check if parameters are optional
        params_are_optional = True

        for param_name, param in signature.parameters.items():
            if not param.default:
                params_are_optional = False

        # Print method name and its parameters
        command = f"--{command}"
        params = ""

        if signature.parameters:
            if not params_are_optional:
                params += '['

            params += ':'

            params += ','.join(parameters)

            if not params_are_optional:
                params += ']'

        docs = method.__doc__ or ''

        table.add_row([f"{command}{params}", docs.strip()])

    print(table)
