import os, sys

from mantis import VERSION
from mantis.helpers import Colors, CLI, find_config, load_config


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
        # elif '=' in arg and ':' not in arg:
        elif '=' in arg:
            s, v = arg.split('=', maxsplit=1)
            d['settings'][s.strip('-')] = v
        else:
            d['commands'].append(arg)

    return d


def nested_set(dic, keys, value):
    for key in keys[:-1]:
        dic = dic.setdefault(key, {})
    dic[keys[-1]] = value


def import_string(path):
    components = path.split('.')
    mod = __import__('.'.join(components[0:-1]), globals(), locals(), [components[-1]])
    return getattr(mod, components[-1])


def get_extension_classes(extensions):
    extension_classes = []

    # extensions
    for extension in extensions:
        extension_class_name = extension if '.' in extension else f"mantis.extensions.{extension.lower()}.{extension}"
        extension_class = import_string(extension_class_name)
        extension_classes.append(extension_class)

    return extension_classes


def get_manager(environment_id, mode):
    # config file
    config_file = find_config(environment_id)
    config = load_config(config_file)

    # class name of the manager
    manager_class_name = config.get('manager_class', 'mantis.managers.BaseManager')

    # get manager class
    manager_class = import_string(manager_class_name)

    # setup extensions
    extensions = config.get('extensions', {})
    extension_classes = get_extension_classes(extensions.keys())

    CLI.info(f"Extensions: {', '.join(extensions.keys())}")

    # create dynamic manager class
    class MantisManager(*[manager_class] + extension_classes):
        pass

    manager = MantisManager(config_file=config_file, environment_id=environment_id, mode=mode)

    # set extensions data
    for extension, extension_params in extensions.items():
        if 'service' in extension_params:
            setattr(manager, f'{extension}_service'.lower(), extension_params['service'])

    return manager


def main():
    # check params
    params = parse_args()

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
    --mode=remote \tconnects to host remotely from local machine (default)\n\
    --mode=ssh \t\tconnects to host via ssh and run mantis on remote machine\n\
    --mode=host \truns mantis on remote machine directly')

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
                params = []

            execute(manager, command, params)


def execute(manager, command, params):
    shortcuts = {
        '-hc': 'healthcheck',
        '-b': 'build',
        '-p': 'pull',
        '-u': 'upload',
        '-d': 'deploy',
        '-c': 'clean',
        '-s': 'status',
        '-n': 'networks',
        '-l': 'logs',
    }

    manager_method = shortcuts.get(command, None)

    if manager_method is None:
        manager_method = command.lstrip('-').replace('-', '_')

    if manager_method is None or not hasattr(manager, manager_method):
        CLI.error(f'Invalid command "{command}"')

        # TODO: more sophisticated way to print usage/help
        # commands = '\n'.join(manager_methods.keys())
        # CLI.error(f'\n\nUsage: mantis <ENVIRONMENT> \n{commands}')
    else:
        methods_without_environment = ['contexts', 'create_context', 'check_config', 'generate_key', 'read_key']

        if manager.environment_id is None and manager_method not in methods_without_environment:
            CLI.error('Missing environment')
        elif manager.environment_id is not None and manager_method in methods_without_environment:
            CLI.error('Redundant environment')

        # Execute manager method
        returned_value = getattr(manager, manager_method)(*params)

        if returned_value:
            print(returned_value)
