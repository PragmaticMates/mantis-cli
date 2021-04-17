import os, sys

from mantis import VERSION
from mantis.helpers import Colors, CLI
from mantis.manager import Mantis


def parse_args():
    import sys
    from collections import defaultdict

    d = {
        'environment_id': None,
        'commands': [],
        'settings': {}
    }

    for arg in sys.argv:
        if not arg.startswith('-'):
            d['environment_id'] = arg
        elif '=' in arg:
            s, v = arg.split('=')
            d['settings'][s.strip('-')] = v
        else:
            d['commands'].append(arg)

    return d

def main():
    # check params
    params = parse_args()

    # print(params)
    if len(params['commands']) == 0:
        CLI.error('Missing commands')

    environment_id = params['environment_id']
    commands = params['commands']
    mode = params['settings'].get('mode', 'docker-host')
    hostname = os.popen('hostname').read().rstrip("\n")

    # setup manager
    manager = Mantis(environment_id=environment_id, mode=mode)

    print(f'Mantis (v{VERSION}) attached to '
          f'{Colors.BOLD}{manager.environment_id}{Colors.ENDC}: '
          f'{Colors.RED}{manager.host}{Colors.ENDC}, '
          f'mode: {Colors.GREEN}{manager.mode}{Colors.ENDC}, '
          f'hostname: {Colors.BLUE}{hostname}{Colors.ENDC}')

    if mode == 'ssh':
        cmds = [
            f'cd {manager.project_path}',
            f'mantis {environment_id} --mode=host {" ".join(commands)}'
        ]
        cmd = ';'.join(cmds)
        exec = f"ssh -t {manager.user}@{manager.host} -p {manager.port} '{cmd}'"
        # print(exec)
        os.system(exec)
    else:
        # execute all commands
        for command in commands:
            if ':' in command:
                command, params = command.split(':')
            else:
                params = ''

            execute(manager, command, params)


def execute(manager, command, params=''):
    if manager.environment_id is None:
        CLI.error('Missing environment')

    else:
        manager_method = {
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
        }.get(command)

        methods_with_params = ['build', 'ssh', 'exec', 'manage', 'pg_restore', 'start', 'stop', 'logs', 'remove']

        if manager_method is None or not hasattr(manager, manager_method):
            CLI.error(f'Invalid command "{command}" \n\nUsage: mantis <ENVIRONMENT> '
                      '\n--no-ssh |'
                      '\n--build/-b |'
                      '\n--push |'
                      '\n--pull/-p |'
                      '\n--upload/-u | '
                      '\n--upload-docker-configs | '
                      '\n--deploy/-d | '
                      '\n--stop | '
                      '\n--start | '
                      '\n--reload | '
                      '\n--restart | '
                      '\n--remove | '
                      '\n--clean/-c | '
                      '\n--status/-s | '
                      '\n--networks/-n | '
                      '\n--logs/-l | '
                      '\n--reload-webserver | '
                      '\n--restart-proxy | '
                      '\n--manage | '
                      '\n--shell | '
                      '\n--ssh | '
                      '\n--exec | '
                      '\n--psql | '
                      '\n--pg-dump | '
                      '\n--pg-restore | '
                      '\n--send-test-email')
        else:
            if manager_method in methods_with_params:
                getattr(manager, manager_method)(params)
            else:
                getattr(manager, manager_method)()
