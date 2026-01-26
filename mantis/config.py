import os
import sys
import json
from dataclasses import dataclass, field
from json.decoder import JSONDecodeError
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table

from mantis.helpers import CLI
from mantis.schema import EnvironmentConfig


SECRETS_COMMANDS = {'show-env', 'encrypt-env', 'decrypt-env', 'check-env'}

# Default environment folder from schema
DEFAULT_ENV_FOLDER = EnvironmentConfig.model_fields['folder'].default


def get_config_dir(config_path: str) -> str:
    """Get normalized directory path for a config file."""
    return str(Path(config_path).parent)


@dataclass
class ConfigAnalysis:
    """Analysis results for a single config file."""
    path: str
    index: int
    is_single_connection: bool = False
    folder_envs: list = field(default_factory=list)
    connection_envs: list = field(default_factory=list)
    has_match: bool = False

    @property
    def connection_envs_with_local(self) -> list:
        return ['local'] + [e for e in self.connection_envs if e != 'local']


def analyze_config(path: str, index: int) -> ConfigAnalysis:
    """Analyze a config file and extract environment information."""
    config = load_config(path)
    analysis = ConfigAnalysis(path=path, index=index)

    # Check for single connection mode
    if config.get('connection'):
        analysis.is_single_connection = True
        return analysis

    # Get folder-based environments
    env_folder = config.get('environment', {}).get('folder', DEFAULT_ENV_FOLDER)
    config_dir = str(Path(path).parent.resolve())
    env_path = Path(env_folder.replace('<MANTIS>', config_dir)).resolve()
    if env_path.exists() and env_path.is_dir():
        analysis.folder_envs = sorted([d.name for d in env_path.iterdir() if d.is_dir()])

    # Get connection-based environments
    analysis.connection_envs = list(config.get('connections', {}).keys())

    return analysis


def env_matches_for_command(env_id: str, cmd: str, analysis: ConfigAnalysis) -> bool:
    """Check if an environment matches for a specific command."""
    if cmd in SECRETS_COMMANDS:
        # Secrets command needs folder-based environment
        return env_id in analysis.folder_envs or any(e.startswith(env_id) for e in analysis.folder_envs)
    else:
        # Other commands need connection or 'local'
        if 'local' in env_id:
            return True
        return env_id in analysis.connection_envs or any(e.startswith(env_id) for e in analysis.connection_envs)


def env_matches_all_commands(env_id: str, commands: list, analysis: ConfigAnalysis) -> bool:
    """Check if an environment matches for ALL commands."""
    if not commands:
        return True
    return all(env_matches_for_command(env_id, cmd, analysis) for cmd in commands)


def get_valid_envs_for_commands(commands: list, analysis: ConfigAnalysis) -> set:
    """Get environments that satisfy ALL commands for a config."""
    if not commands:
        return set()

    valid = set(analysis.folder_envs) | set(analysis.connection_envs_with_local)
    for cmd in commands:
        if cmd in SECRETS_COMMANDS:
            valid &= set(analysis.folder_envs)
        else:
            valid &= set(analysis.connection_envs_with_local)
    return valid


def format_env_list(envs: list, environment_id: Optional[str]) -> str:
    """Format a list of environments with color highlighting."""
    if not envs:
        return '[dim]none[/dim]'

    colored = []
    for env in envs:
        matches = environment_id and (env == environment_id or env.startswith(environment_id))
        color = 'green' if matches else 'yellow'
        colored.append(f'[{color}]{env}[/{color}]')
    return ', '.join(colored)


def find_config(environment_id: Optional[str] = None, commands: Optional[list] = None) -> str:
    """Find and select a mantis config file."""
    # Check environment variable first
    env_path = os.environ.get('MANTIS_CONFIG', None)
    if env_path and env_path != '':
        CLI.info(f'Mantis config defined by environment variable $MANTIS_CONFIG: {env_path}')
        return env_path

    # Search for mantis.json files
    CLI.info('Environment variable $MANTIS_CONFIG not found. Looking for file mantis.json...')
    paths = sorted([str(p) for p in Path('.').rglob('mantis.json')])

    # No mantis file found
    if not paths:
        DEFAULT_PATH = 'configs/mantis.json'
        CLI.info(f'mantis.json file not found. Using default value: {DEFAULT_PATH}')
        return DEFAULT_PATH

    # Single mantis file found
    if len(paths) == 1:
        CLI.info(f'Found 1 mantis.json file: {paths[0]}')
        return paths[0]

    # Multiple mantis files found - show selection table
    CLI.info(f'Found {len(paths)} mantis.json files:')
    return _select_from_multiple_configs(paths, environment_id, commands or [])


def _select_from_multiple_configs(paths: list, environment_id: Optional[str], commands: list) -> str:
    """Handle selection when multiple config files are found."""
    # Determine command types
    has_secrets_command = any(cmd in SECRETS_COMMANDS for cmd in commands)
    has_other_command = any(cmd not in SECRETS_COMMANDS for cmd in commands)
    show_both_columns = has_secrets_command and has_other_command

    # Build table
    console = Console()
    table = Table(show_header=True, header_style="bold")
    table.add_column("#", style="cyan")
    table.add_column("Path")

    if show_both_columns:
        table.add_column("Connections")
        table.add_column("Environments")
    elif has_secrets_command:
        table.add_column("Environments")
    else:
        table.add_column("Connections")

    # Analyze all configs and build table rows
    matching_configs = []
    single_connection_configs = []
    all_environments = set()
    valid_for_all_commands = set()

    for index, path in enumerate(paths):
        analysis = analyze_config(path, index)

        if analysis.is_single_connection:
            single_connection_configs.append((index, path))
            analysis.has_match = not environment_id

            if show_both_columns:
                connections_display = '[green](single)[/green]'
                environments_display = '[dim]n/a[/dim]'
            else:
                environments_display = '[green](single)[/green]'
                connections_display = ''
        else:
            # Collect all environments
            if has_secrets_command and has_other_command:
                display_envs = sorted(set(analysis.folder_envs) | set(analysis.connection_envs_with_local))
            elif has_secrets_command:
                display_envs = analysis.folder_envs
            else:
                display_envs = analysis.connection_envs_with_local

            all_environments.update(display_envs)

            # Find valid environments for all commands
            config_valid = get_valid_envs_for_commands(commands, analysis)
            valid_for_all_commands.update(config_valid)

            # Check if environment matches
            if environment_id and env_matches_all_commands(environment_id, commands, analysis):
                analysis.has_match = True
                matching_configs.append((index, path))

            # Format display strings
            if show_both_columns:
                connections_display = format_env_list(analysis.connection_envs_with_local, environment_id)
                environments_display = format_env_list(analysis.folder_envs, environment_id)
            else:
                environments_display = format_env_list(display_envs, environment_id)
                connections_display = ''

        # Add table row
        path_display = get_config_dir(path) if analysis.has_match else f'[dim]{get_config_dir(path)}[/dim]'

        if show_both_columns:
            table.add_row(str(index + 1), path_display, connections_display, environments_display)
        else:
            table.add_row(str(index + 1), path_display, environments_display)

    console.print(table)

    # Handle no matching configs
    if environment_id and not matching_configs:
        _error_no_matching_config(environment_id, commands, all_environments, valid_for_all_commands)

    # Auto-select if exactly one match
    if environment_id and len(matching_configs) == 1:
        selected_path = matching_configs[0][1]
        CLI.info(f'Auto-selected config: {get_config_dir(selected_path)}')
        return selected_path

    # Auto-select single connection config if no environment specified
    if not environment_id and len(single_connection_configs) == 1:
        selected_path = single_connection_configs[0][1]
        CLI.info(f'Auto-selected single connection config: {get_config_dir(selected_path)}')
        return selected_path

    # Prompt user to select
    return _prompt_config_selection(paths)


def _error_no_matching_config(environment_id: str, commands: list, all_environments: set, valid_for_all_commands: set):
    """Show error message when no config matches the environment."""
    if commands and valid_for_all_commands:
        CLI.error(
            f'Environment "{environment_id}" not found. '
            f'Available for commands {", ".join(commands)}: {", ".join(sorted(valid_for_all_commands))}'
        )
    elif commands:
        CLI.error(f'No environment found that satisfies all commands: {", ".join(commands)}')
    else:
        CLI.error(
            f'Environment "{environment_id}" not found in any config. '
            f'Available: {", ".join(sorted(all_environments))}'
        )


def _prompt_config_selection(paths: list) -> str:
    """Prompt user to select a config file."""
    CLI.danger('[0] Exit now and define $MANTIS_CONFIG environment variable')

    while True:
        path_index = input('Define which one to use: ')
        if path_index.isdigit():
            idx = int(path_index)
            if idx == 0:
                sys.exit(0)
            if 1 <= idx <= len(paths):
                return paths[idx - 1]


def find_keys_only_in_config(config, template, parent_key=""):
    differences = []

    for key in config:
        full_key = f"{parent_key}.{key}" if parent_key else key

        if key not in template:
            differences.append(full_key)
        elif isinstance(config[key], dict) and isinstance(template[key], dict):
            nested_differences = find_keys_only_in_config(config[key], template[key], parent_key=full_key)
            differences.extend(nested_differences)

    return differences


def load_config(config_file: str) -> dict:
    if not Path(config_file).exists():
        CLI.warning(f'File {config_file} does not exist.')
        CLI.danger('Mantis config not found. Double check your current working directory.')
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
