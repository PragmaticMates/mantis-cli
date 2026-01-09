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


SECRETS_COMMANDS = {'show-env', 'encrypt-env', 'decrypt-env', 'check-env'}


def find_config(environment_id=None, commands=None):
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

    # Normalize commands to a list
    if commands is None:
        commands = []
    elif isinstance(commands, str):
        commands = [commands]

    # Determine if any command is a secrets command
    has_secrets_command = any(cmd in SECRETS_COMMANDS for cmd in commands)
    has_other_command = any(cmd not in SECRETS_COMMANDS for cmd in commands)

    console = Console()
    table = Table(show_header=True, header_style="bold")
    table.add_column("#", style="cyan")
    table.add_column("Path")
    # Column(s) based on command types
    show_both_columns = has_secrets_command and has_other_command
    if show_both_columns:
        table.add_column("Connections")
        table.add_column("Environments")
    elif has_secrets_command:
        table.add_column("Environments")
    else:
        table.add_column("Connections")

    # Track which configs have matching environments and single connection configs
    matching_configs = []
    single_connection_configs = []
    all_environments = set()
    # Track environments that satisfy ALL commands (for error message)
    valid_for_all_commands = set()

    for index, path in enumerate(paths):
        config = load_config(path)

        # Check for single connection mode
        single_connection = config.get('connection')
        has_match = False

        if single_connection:
            # Single connection mode - display the connection string
            if show_both_columns:
                connections_display = '[green](single)[/green]'
                environments_display = '[dim]n/a[/dim]'
            else:
                environments_display = '[green](single)[/green]'
            single_connection_configs.append((index, path))
            # Single connection matches when no environment is specified
            has_match = not environment_id
        else:
            # Get environment folders from the environments directory
            folder_envs = []
            env_folder = config.get('environment', {}).get('folder', '<MANTIS>/../environments')
            config_dir = str(Path(path).parent.resolve())
            env_path = Path(env_folder.replace('<MANTIS>', config_dir)).resolve()
            if env_path.exists() and env_path.is_dir():
                folder_envs = sorted([d.name for d in env_path.iterdir() if d.is_dir()])

            # Get connection-based environments
            connection_envs = list(config.get('connections', {}).keys())
            connection_envs_with_local = ['local'] + [e for e in connection_envs if e != 'local']

            # Determine which environments to display based on command types
            if has_secrets_command and has_other_command:
                # Mixed commands: show intersection or both
                environments = sorted(set(folder_envs) | set(connection_envs_with_local))
            elif has_secrets_command:
                environments = folder_envs
            else:
                environments = connection_envs_with_local

            all_environments.update(environments)

            # Find environments that satisfy ALL commands for this config
            if commands:
                config_valid_envs = set(environments)
                for cmd in commands:
                    if cmd in SECRETS_COMMANDS:
                        config_valid_envs &= set(folder_envs)
                    else:
                        config_valid_envs &= set(connection_envs_with_local)
                valid_for_all_commands.update(config_valid_envs)

            # Check if environment matches for ALL commands
            env_matches_all_commands = True
            if environment_id:
                for cmd in commands:
                    if cmd in SECRETS_COMMANDS:
                        # Secrets command needs folder-based environment
                        if environment_id not in folder_envs and not any(e.startswith(environment_id) for e in folder_envs):
                            env_matches_all_commands = False
                            break
                    else:
                        # Other commands need connection or 'local'
                        if 'local' not in environment_id and environment_id not in connection_envs and not any(e.startswith(environment_id) for e in connection_envs):
                            env_matches_all_commands = False
                            break

                if env_matches_all_commands:
                    has_match = True
                    if (index, path) not in matching_configs:
                        matching_configs.append((index, path))

            # Build display strings based on column mode
            if show_both_columns:
                # Create separate displays for connections and environments
                colorful_connections = []
                for env in connection_envs_with_local:
                    matches = environment_id and (env == environment_id or env.startswith(environment_id))
                    color = 'green' if matches else 'yellow'
                    colorful_connections.append(f'[{color}]{env}[/{color}]')
                connections_display = ', '.join(colorful_connections)

                colorful_folders = []
                for env in folder_envs:
                    matches = environment_id and (env == environment_id or env.startswith(environment_id))
                    color = 'green' if matches else 'yellow'
                    colorful_folders.append(f'[{color}]{env}[/{color}]')
                environments_display = ', '.join(colorful_folders) if colorful_folders else '[dim]none[/dim]'
            else:
                # Single column display
                colorful_environments = []
                for env in environments:
                    matches = environment_id and (env == environment_id or env.startswith(environment_id))
                    color = 'green' if matches else 'yellow'
                    colorful_environments.append(f'[{color}]{env}[/{color}]')
                environments_display = ', '.join(colorful_environments)

        # Dim path if no environment match
        config_dir = get_config_dir(path)
        path_display = config_dir if has_match else f'[dim]{config_dir}[/dim]'

        if show_both_columns:
            table.add_row(str(index + 1), path_display, connections_display, environments_display)
        else:
            table.add_row(str(index + 1), path_display, environments_display)

    # Always print the table when multiple configs found
    console.print(table)

    # If environment was provided but no config has a matching environment, error out
    if environment_id and not matching_configs:
        if commands and valid_for_all_commands:
            CLI.error(f'Environment "{environment_id}" not found. Available for commands {", ".join(commands)}: {", ".join(sorted(valid_for_all_commands))}')
        elif commands:
            CLI.error(f'No environment found that satisfies all commands: {", ".join(commands)}')
        else:
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
