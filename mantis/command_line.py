#!/usr/bin/env python
import os
import sys

from mantis import VERSION
from mantis.helpers import Colors, CLI, nested_set
from mantis.logic import get_manager, execute


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

    if len(params['commands']) == 0:
        CLI.error('Missing commands')

    environment_id = params['environment_id']
    commands = params['commands']
    mode = params['settings'].get('mode', 'remote')

    if mode not in ['remote', 'ssh', 'host']:
        CLI.error('Incorrect mode. Usage of modes:\n\
    --mode=remote \truns commands remotely from local machine using DOCKER_HOST or DOCKER_CONTEXT (default)\n\
    --mode=ssh \t\tconnects to host via ssh and run all mantis commands on remote machine directly (nantis-cli needs to be installed on server)\n\
    --mode=host \truns mantis on host machine directly without invoking connection (used as proxy for ssh mode)')

    hostname = os.popen('hostname').read().rstrip("\n")

    # get manager
    manager = get_manager(environment_id, mode)

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

    if manager.connection:
        if manager.host:
            host_intro = f'{Colors.RED}{manager.host}{Colors.ENDC}, '
        else:
            CLI.error(f'Invalid host: {manager.host}')
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
