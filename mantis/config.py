import os
import sys
import json
from json.decoder import JSONDecodeError
from pathlib import Path

from rich.console import Console
from rich.table import Table

from mantis.helpers import CLI


def get_config_dir(config_path: str) -> str:
    """Get normalized directory path for a config file."""
    return str(Path(config_path).parent)


def find_config(environment_id=None):
    env_path = os.environ.get('MANTIS_CONFIG', None)

    if env_path and env_path != '':
        CLI.info(f'Mantis config defined by environment variable $MANTIS_CONFIG: {env_path}')
        return env_path

    CLI.info('Environment variable $MANTIS_CONFIG not found. Looking for file mantis.json...')
    paths = [str(p) for p in Path('.').rglob('mantis.json')]

    # Sort for consistent ordering
    paths.sort()

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

    # Track which configs have matching environments and single connection configs
    matching_configs = []
    single_connection_configs = []
    all_environments = set()

    for index, path in enumerate(paths):
        config = load_config(path)

        # Check for single connection mode
        single_connection = config.get('connection')
        has_match = False

        if single_connection:
            # Single connection mode - display the connection string
            connections_display = '[green](single)[/green]'
            single_connection_configs.append((index, path))
            # Single connection matches when no environment is specified
            has_match = not environment_id
        else:
            # Multi-environment mode - display connection keys
            connections = list(config.get('connections', {}).keys())
            all_environments.update(connections)

            # Check if any connection matches the environment prefix
            colorful_connections = []
            for connection in connections:
                # Highlight in green if exact match or prefix match
                matches = environment_id and (connection == environment_id or connection.startswith(environment_id))
                if matches:
                    has_match = True
                color = 'green' if matches else 'yellow'
                colorful_connections.append(f'[{color}]{connection}[/{color}]')
            connections_display = ', '.join(colorful_connections)

            if has_match:
                matching_configs.append((index, path))

        # Dim path if no environment match
        config_dir = get_config_dir(path)
        path_display = config_dir if has_match else f'[dim]{config_dir}[/dim]'
        table.add_row(str(index + 1), path_display, connections_display)

    # Always print the table when multiple configs found
    console.print(table)

    # If environment was provided but no config has a matching environment, error out
    if environment_id and not matching_configs:
        CLI.error(f'Environment "{environment_id}" not found in any config. Available: {", ".join(sorted(all_environments))}')

    # If exactly one config has matching environment, auto-select it
    if environment_id and len(matching_configs) == 1:
        selected_path = matching_configs[0][1]
        CLI.info(f'Auto-selected config: {get_config_dir(selected_path)}')
        return selected_path

    # If no environment provided and only one single connection config exists, auto-select it
    if not environment_id and len(single_connection_configs) == 1:
        selected_path = single_connection_configs[0][1]
        CLI.info(f'Auto-selected single connection config: {get_config_dir(selected_path)}')
        return selected_path

    CLI.danger(f'[0] Exit now and define $MANTIS_CONFIG environment variable')

    path_index = None
    while path_index is None:
        path_index = input('Define which one to use: ')
        if not path_index.isdigit() or int(path_index) > len(paths):
            path_index = None
        else:
            path_index = int(path_index)

    if path_index == 0:
        sys.exit(0)

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


def load_config(config_file: str) -> dict:
    if not Path(config_file).exists():
        CLI.warning(f'File {config_file} does not exist.')
        CLI.danger(f'Mantis config not found. Double check your current working directory.')
        sys.exit(1)

    with open(config_file, "r") as config:
        try:
            return json.load(config)
        except JSONDecodeError as e:
            CLI.error(f"Failed to load config from file {config_file}: {e}")


def load_template_config() -> dict:
    template_path = Path(__file__).parent / 'mantis.tpl'
    return load_config(str(template_path))


def check_config(config):
    """Validate config using Pydantic schema."""
    from pydantic import ValidationError
    from mantis.schema import validate_config

    try:
        validate_config(config)
        CLI.success("Config passed validation.")
    except ValidationError as e:
        errors = []
        for error in e.errors():
            loc = '.'.join(str(l) for l in error['loc'])
            msg = error['msg']
            errors.append(f"  - {loc}: {msg}")

        template_link = CLI.link(
            'https://github.com/PragmaticMates/mantis-cli/blob/master/mantis/mantis.tpl',
            'template'
        )
        CLI.error(
            f"Config validation failed:\n" +
            '\n'.join(errors) +
            f"\n\nCheck {template_link} for available attributes."
        )
