import os
import json
from json.decoder import JSONDecodeError
from os.path import dirname, normpath, abspath
from prettytable import PrettyTable

from mantis.helpers import CLI, import_string


def find_config(environment_id=None):
    env_path = os.environ.get('MANTIS_CONFIG', None)

    if env_path and env_path != '':
        CLI.info(f'Mantis config defined by environment variable $MANTIS_CONFIG: {env_path}')
        return env_path

    CLI.info('Environment variable $MANTIS_CONFIG not found. Looking for file mantis.json...')
    paths = os.popen('find . -name mantis.json').read().strip().split('\n')

    # Remove empty strings
    paths = list(filter(None, paths))

    # Count found mantis files
    total_mantis_files = len(paths)

    # No mantis file found
    if total_mantis_files == 0:
        DEFAULT_PATH = 'configs/mantis.json'
        CLI.info(f'mantis.json file not found. Using default value: {DEFAULT_PATH}')
        return DEFAULT_PATH

    # Single mantis file found
    if total_mantis_files == 1:
        CLI.info(f'Found 1 mantis.json file: {paths[0]}')
        return paths[0]

    # Multiple mantis files found
    CLI.info(f'Found {total_mantis_files} mantis.json files:')

    table = PrettyTable(align='l')
    table.field_names = ["#", "Path", "Project name", "Connections"]

    for index, path in enumerate(paths):
        config = load_config(path)
        connections = config.get('connections', {}).keys()
        project_name = config.get('project_name', '')

        colorful_connections = []
        for connection in connections:
            color = 'success' if connection == environment_id else 'warning'
            colorful_connections.append(getattr(CLI, color)(connection, end='', return_value=True))

        table.add_row([index + 1, normpath(dirname(path)), project_name, ', '.join(colorful_connections)])

    print(table)
    CLI.danger(f'[0] Exit now and define $MANTIS_CONFIG environment variable')

    path_index = None
    while path_index is None:
        path_index = input('Define which one to use: ')
        if not path_index.isdigit() or int(path_index) > len(paths):
            path_index = None
        else:
            path_index = int(path_index)

    if path_index == 0:
        exit()

    return paths[path_index - 1]


def find_keys_only_in_config(config, template, parent_key=""):
    differences = []

    # Iterate over keys in config
    for key in config:
        # Construct the full key path
        full_key = parent_key + "." + key if parent_key else key

        # Check if key exists in template
        if key not in template:
            differences.append(full_key)
        else:
            # Recursively compare nested dictionaries
            if isinstance(config[key], dict) and isinstance(template[key], dict):
                nested_differences = find_keys_only_in_config(config[key], template[key], parent_key=full_key)
                differences.extend(nested_differences)

    return differences


def load_config(config_file):
    if not os.path.exists(config_file):
        CLI.warning(f'File {config_file} does not exist. Returning empty config')
        return {}

    with open(config_file, "r") as config:
        try:
            return json.load(config)
        except JSONDecodeError as e:
            CLI.error(f"Failed to load config from file {config_file}: {e}")


def check_config(config):
    # Load config template file
    current_directory = dirname(abspath(__file__))
    template_path = normpath(f'{current_directory}/mantis.tpl')
    template = load_config(template_path)

    # validate config file
    config_keys_only = find_keys_only_in_config(config, template)

    # remove custom connections
    config_keys_only = list(filter(lambda x: not x.startswith('connections.'), config_keys_only))

    if config_keys_only:
        template_link = CLI.link('https://github.com/PragmaticMates/mantis-cli/blob/master/mantis/mantis.tpl',
                                 'template')
        CLI.error(
            f"Config file validation failed. Unknown config keys: {config_keys_only}. Check {template_link} for available attributes.")


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
        CLI.error(f'Invalid command "{command}". Check mantis --help for more information.')
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
