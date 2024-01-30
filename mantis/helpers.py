import os
import json
from json.decoder import JSONDecodeError
from os.path import dirname, normpath, abspath
from prettytable import PrettyTable


class Colors:
    # https://stackoverflow.com/questions/5947742/how-to-change-the-output-color-of-echo-in-linux
    BLACK = "\033[0;30m"
    BLUE = '\033[94m'
    # BLUE = "\033[0;34m"
    GREEN = '\033[92m'
    # GREEN = "\033[0;32m"
    YELLOW = '\033[93m'
    # YELLOW = "\033[1;33m"
    RED = '\033[91m'
    # RED = "\033[0;31m"
    PINK = '\033[95m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    BROWN = "\033[0;33m"
    PURPLE = "\033[0;35m"
    CYAN = "\033[0;36m"
    LIGHT_GRAY = "\033[0;37m"
    DARK_GRAY = "\033[1;30m"
    LIGHT_RED = "\033[1;31m"
    LIGHT_GREEN = "\033[1;32m"
    LIGHT_BLUE = "\033[1;34m"
    LIGHT_PURPLE = "\033[1;35m"
    LIGHT_CYAN = "\033[1;36m"
    LIGHT_WHITE = "\033[1;37m"
    FAINT = "\033[2m"
    ITALIC = "\033[3m"
    BLINK_SLOW = "\033[5m"
    BLINK_FAST = "\033[6m"
    NEGATIVE = "\033[7m"
    CROSSED = "\033[9m"
    RESET = "\033[0m"
    ENDC = '\033[0m'


class CLI(object):
    @staticmethod
    def print_or_return(text, color, end='\n', return_value=False):
        s = f'{color}{text}{Colors.ENDC}'
        if return_value:
            return f'{s}{end}'
        print(s, end=end)

    @staticmethod
    def error(text):
        exit(f'{Colors.RED}{text}{Colors.ENDC}')

    @staticmethod
    def bold(text, end='\n', return_value=False):
        return CLI.print_or_return(text=text, color=Colors.BOLD, end=end, return_value=return_value)

    @staticmethod
    def info(text, end='\n', return_value=False):
        return CLI.print_or_return(text=text, color=Colors.BLUE, end=end, return_value=return_value)

    @staticmethod
    def pink(text, end='\n', return_value=False):
        return CLI.print_or_return(text=text, color=Colors.PINK, end=end, return_value=return_value)

    @staticmethod
    def success(text, end='\n', return_value=False):
        return CLI.print_or_return(text=text, color=Colors.GREEN, end=end, return_value=return_value)

    @staticmethod
    def warning(text, end='\n', return_value=False):
        return CLI.print_or_return(text=text, color=Colors.YELLOW, end=end, return_value=return_value)

    @staticmethod
    def danger(text, end='\n', return_value=False):
        return CLI.print_or_return(text=text, color=Colors.RED, end=end, return_value=return_value)

    @staticmethod
    def underline(text, end='\n', return_value=False):
        return CLI.print_or_return(text=text, color=Colors.UNDERLINE, end=end, return_value=return_value)

    @staticmethod
    def step(index, total, text, end='\n', return_value=False):
        return CLI.print_or_return(text=f'[{index}/{total}] {text}', color=Colors.YELLOW, end=end, return_value=return_value)


def random_string(n=10):
    import random
    import string
    
    chars = string.ascii_lowercase + string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(n))


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
            
        table.add_row([index+1, normpath(dirname(path)), project_name, ', '.join(colorful_connections)])
            
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

    return paths[path_index-1]


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
        CLI.error(f"Config file validation failed. Unknown config keys: {config_keys_only}")
