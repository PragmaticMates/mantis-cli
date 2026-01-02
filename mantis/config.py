import os
import json
from json.decoder import JSONDecodeError
from os.path import dirname, normpath, abspath

from rich.console import Console
from rich.table import Table

from mantis.helpers import CLI


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

    console = Console()
    table = Table(show_header=True, header_style="bold")
    table.add_column("#", style="cyan")
    table.add_column("Path")
    table.add_column("Connections")

    for index, path in enumerate(paths):
        config = load_config(path)

        # Check for single connection mode
        single_connection = config.get('connection')

        if single_connection:
            # Single connection mode - display the connection string
            connections_display = '[green](single)[/green]'
        else:
            # Multi-environment mode - display connection keys
            connections = config.get('connections', {}).keys()

            # TODO: get project names from compose files

            colorful_connections = []
            for connection in connections:
                color = 'green' if connection == environment_id else 'yellow'
                colorful_connections.append(f'[{color}]{connection}[/{color}]')
            connections_display = ', '.join(colorful_connections)

        table.add_row(str(index + 1), normpath(dirname(path)), connections_display)

    console.print(table)
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
        CLI.warning(f'File {config_file} does not exist.')
        CLI.danger(f'Mantis config not found. Double check your current working directory.')
        exit()
        # CLI.warning(f'File {config_file} does not exist. Returning empty config')
        # return {}

    with open(config_file, "r") as config:
        try:
            return json.load(config)
        except JSONDecodeError as e:
            CLI.error(f"Failed to load config from file {config_file}: {e}")


def load_template_config():
    current_directory = dirname(abspath(__file__))
    template_path = normpath(f'{current_directory}/mantis.tpl')
    return load_config(template_path)


def check_config(config):
    # Load config template file
    template = load_template_config()

    # validate config file
    config_keys_only = find_keys_only_in_config(config, template)

    # remove custom connections
    config_keys_only = list(filter(lambda x: not x.startswith('connections.'), config_keys_only))

    if config_keys_only:
        template_link = CLI.link('https://github.com/PragmaticMates/mantis-cli/blob/master/mantis/mantis.tpl',
                                 'template')
        CLI.error(
            f"Config file validation failed. Unknown config keys: {config_keys_only}. Check {template_link} for available attributes.")

    CLI.success(f"Config passed validation.")
