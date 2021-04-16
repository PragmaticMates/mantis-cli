import sys

from mantis.manager import CLI, Mantis


def main():
    # check params
    if len(sys.argv) <= 1:
        CLI.error('Missing params')

    commands = sys.argv[1:]

    # first argument is environment
    environment_id = commands[0].lower()
    commands = commands[1:]
    no_ssh = False

    if '--no-ssh' in commands:
        no_ssh = True
        commands.remove('--no-ssh')

    # setup manager
    manager = Mantis(environment_id=environment_id, no_ssh=no_ssh)

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
            '-p': 'push',
            '--pull': 'pull',
            '--upload': 'upload',
            '--upload-docker-configs': 'upload_docker_configs',
            '-u': 'upload',
            '--restart': 'restart',
            '-r': 'restart',
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
                      '\n--push/-p |'
                      '\n--pull |'
                      '\n--upload/-u | '
                      '\n--upload-docker-configs | '
                      '\n--deploy/-d | '
                      '\n--stop | '
                      '\n--start | '
                      '\n--restart/-r | '
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
            getattr(manager, manager_method)(params) if manager_method in methods_with_params else getattr(manager, manager_method)()
