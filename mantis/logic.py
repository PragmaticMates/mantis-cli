import os, sys

from mantis import VERSION
from mantis.helpers import Colors, CLI, load_config


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
    mode = params['settings'].get('mode', 'remote')

    if mode not in ['remote', 'ssh', 'host']:
        CLI.error('Incorrect mode. Usage of modes:\n\
    --mode=remote \tconnects to host remotely from local machine (default)\n\
    --mode=ssh \t\tconnects to host via ssh and run mantis on remote machine\n\
    --mode=host \truns mantis on remote machine directly')

    hostname = os.popen('hostname').read().rstrip("\n")

    # config file
    config_file = os.environ.get('MANTIS_CONFIG', 'configs/mantis.json')
    config = load_config(config_file)
    manager_class_name = config.get('manager_class', 'mantis.manager.Mantis')

    # setup manager
    components = manager_class_name.split('.')
    mod = __import__('.'.join(components[0:-1]), globals(), locals(), [components[-1]])
    manager_class = getattr(mod, components[-1])
    manager = manager_class(config=config, environment_id=environment_id, mode=mode)

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

    environment_intro = f'attached to {Colors.BOLD}{manager.environment_id}{Colors.ENDC}: ' if manager.environment_id else ''

    if manager.environment_id:
        if manager.host:
            host_intro = f'{Colors.RED}{manager.host}{Colors.ENDC}, '
        else:
            CLI.error(f'Invalid host: {manager.host}')
    else:
        host_intro = ''

    heading = f'Mantis (v{VERSION}) '\
              f'{environment_intro}'\
              f'{host_intro}'\
              f'mode: {Colors.GREEN}{manager.mode}{Colors.ENDC}, '\
              f'hostname: {Colors.BLUE}{hostname}{Colors.ENDC}'

    print(heading)

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
                params = params.split(',')
            else:
                params = None

            execute(manager, command, params)


def execute(manager, command, params=None):
    manager_methods = {
        '--contexts': 'contexts',
        '--create-context': 'create_context',
        '--generate-key': 'generate_key',
        '--encrypt-env': 'encrypt_env',
        '--decrypt-env': 'decrypt_env',
        '--check-env': 'check_env',
        '--healthcheck': 'healthcheck',
        '-hc': 'healthcheck',
        '--bash': 'bash',
        '--build': 'build',
        '--build-image': 'build_image',
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
        '--sh': 'sh',
        '--bash': 'bash',
        '--manage': 'manage',
        '--exec': 'exec',
        '--psql': 'psql',
        '--pg-dump': 'pg_dump',
        '--pg-dump-data': 'pg_dump_data',
        '--pg-restore': 'pg_restore',
        '--pg-restore-data': 'pg_restore_data',
        '--send-test-email': 'send_test_email',
    }

    manager_method = manager_methods.get(command)

    if manager_method is None or not hasattr(manager, manager_method):
        commands = '\n'.join(manager_methods.keys())
        
        CLI.error(f'Invalid command "{command}" \n\nUsage: mantis <ENVIRONMENT> \n{commands}')
    else:
        methods_without_environment = ['contexts', 'create_context', 'generate_key', 'build', 'build_image', 'push']
        methods_with_params = ['healthcheck', 'sh', 'bash', 'build_image', 'exec', 'bash', 'manage', 'pg_restore', 'pg_restore_data', 'pg_dump_data',
                               'start', 'stop', 'logs', 'remove', 'upload', 'run', 'up', 'encrypt_env', 'decrypt_env']

        if manager.environment_id is None and manager_method not in methods_without_environment:
            CLI.error('Missing environment')
        elif manager.environment_id is not None and manager_method in methods_without_environment:
            CLI.error('Redundant environment')

        if manager_method in methods_with_params and params:
            getattr(manager, manager_method)(*params)
        else:
            getattr(manager, manager_method)()
