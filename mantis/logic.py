import sys

from mantis.manager import CLI, Mantis


def main():
    # check params
    if len(sys.argv) <= 1:
        CLI.error('Missing params')

    commands = sys.argv[1:]

    # get environment ID
    environment_id = None

    # first argument could be environment
    if commands[0].lower() in ['dev', 'stage', 'production', 'test']:
        environment_id = commands[0].lower()
        commands = commands[1:]

    # setup manager
    manager = Mantis(environment_id=environment_id)

    # execute all commands
    for command in commands:
        if ':' in command:
            command, params = command.split(':')
        else:
            params = ''

        execute(manager, command, params)


def execute(manager, command, params=''):
    if command in ['--build', '-b', '--build-no-cache']:
        no_cache = '--no-cache' if command == '--build-no-cache' else ''
        manager.build(no_cache, params)

    elif manager.environment_id is None:
        CLI.error('Missing environment')

    manager_method = {
        '--upload': 'upload',
        '-u': 'upload',
        '--restart': 'restart',
        '-r': 'restart',
        '--deploy': 'deploy',
        '-d': 'deploy',
        '--stop': 'stop',
        '--start': 'start',
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
        '--psql': 'psql',
        '--send-test-email': 'send_test_email',
    }.get(command)

    if not hasattr(manager, manager_method):
        CLI.error(f'Invalid command "{command}" \n\nUsage: python deploy.py <ENVIRONMENT> '
                  '--build/-b/--build-no-cache | '
                  '--upload/-u | '
                  '--deploy/-d | '
                  '--stop | '
                  '--start | '
                  '--restart/-r | '
                  '--remove | '
                  '--status/-s | '
                  '--networks/-n | '
                  '--logs/-l | '
                  '--reload-webserver | '
                  '--restart-proxy | '
                  '--manage | '
                  '--shell | '
                  '--ssh | '
                  '--psql | '
                  '--send-test-email')
    else:
        getattr(manager, manager_method)(params) if manager_method in ['ssh', 'manage'] else getattr(manager, manager_method)()
