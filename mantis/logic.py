import os, sys

from mantis import VERSION
from mantis.helpers import Colors, CLI
from mantis.manager import Mantis


def parse_args():
    import sys

    d = {
        'environment_id': None,
        'commands': [],
        'settings': {}
    }

    arguments = sys.argv.copy()
    arguments.pop(0)

    for arg in arguments:
        if not arg.startswith('-'):
            d['environment_id'] = arg
        elif '=' in arg and ':' not in arg:
            s, v = arg.split('=', maxsplit=1)
            d['settings'][s.strip('-')] = v
        else:
            d['commands'].append(arg)

    return d


def nested_set(dic, keys, value):
    for key in keys[:-1]:
        dic = dic.setdefault(key, {})
    dic[keys[-1]] = value


def main():
    # check params
    params = parse_args()

    if len(params['commands']) == 0:
        CLI.error('Missing commands')

    environment_id = params['environment_id']
    commands = params['commands']
    mode = params['settings'].get('mode', 'docker-host')
    hostname = os.popen('hostname').read().rstrip("\n")

    # setup manager
    manager = Mantis(environment_id=environment_id, mode=mode)

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

    if manager.environment_id:
        print(f'Mantis (v{VERSION}) attached to '
              f'{Colors.BOLD}{manager.environment_id}{Colors.ENDC}: '
              f'{Colors.RED}{manager.host}{Colors.ENDC}, '
              f'mode: {Colors.GREEN}{manager.mode}{Colors.ENDC}, '
              f'hostname: {Colors.BLUE}{hostname}{Colors.ENDC}')

    if mode == 'ssh':
        cmds = [
            f'cd {manager.project_path}',
            f'time mantis {environment_id} --mode=host {" ".join(commands)}'
        ]
        cmd = ';'.join(cmds)
        exec = f"ssh -t {manager.user}@{manager.host} -p {manager.port} '{cmd}'"
        os.system(exec)
    else:
        # execute all commands
        for command in commands:
            if ':' in command:
                command, params = command.split(':')
            else:
                params = None

            execute(manager, command, params)


def execute(manager, command, params=None):
    manager_methods = {
        '--generate-key': 'generate_key',
        '--encrypt-env': 'encrypt_env',
        '--decrypt-env': 'decrypt_env',
        '--build': 'build',
        '-b': 'build',
        '--push': 'push',
        '--pull': 'pull',
        '-p': 'pull',
        '--upload': 'upload',
        '--upload-docker-configs': 'upload_docker_configs',
        '-u': 'upload',
        '--reload': 'reload',
        '--restart': 'restart',
        '--run': 'run',
        '--up': 'up',
        '--deploy': 'deploy',
        '-d': 'deploy',
        '--stop': 'stop',
        '--start': 'start',
        '--clean': 'clean',
        '-c': 'clean',
        '--remove': 'remove',
        '--reload-webserver': 'reload_webserver',
        '--restart-proxy': 'restart_proxy',
        '--status': 'status',
        '-s': 'status',
        '--networks': 'networks',
        '-n': 'networks',
        '--logs': 'logs',
        '-l': 'logs',
        '--shell': 'shell',
        '--ssh': 'ssh',
        '--manage': 'manage',
        '--exec': 'exec',
        '--psql': 'psql',
        '--pg-dump': 'pg_dump',
        '--pg-restore': 'pg_restore',
        '--send-test-email': 'send_test_email',
    }

    manager_method = manager_methods.get(command)

    if manager_method is None or not hasattr(manager, manager_method):
        commands = '\n'.join(manager_methods.keys())
        
        CLI.error(f'Invalid command "{command}" \n\nUsage: mantis <ENVIRONMENT> \n{commands}')
    else:
        methods_without_environment = ['generate_key']
        methods_with_params = ['build', 'ssh', 'exec', 'manage', 'pg_restore', 'start', 'stop', 'logs', 'remove',
                               'upload', 'run', 'up']

        if manager.environment_id is None and manager_method not in methods_without_environment:
            CLI.error('Missing environment')

        if manager_method in methods_with_params and params:
            getattr(manager, manager_method)(params)
        else:
            getattr(manager, manager_method)()
