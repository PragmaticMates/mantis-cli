import os
import json


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
    def bold(text, end='\n'):
        print(f'{Colors.BOLD}{text}{Colors.ENDC}', end=end)

    @staticmethod
    def info(text, end='\n'):
        print(f'{Colors.BLUE}{text}{Colors.ENDC}', end=end)

    @staticmethod
    def pink(text, end='\n'):
        print(f'{Colors.PINK}{text}{Colors.ENDC}', end=end)

    @staticmethod
    def success(text, end='\n'):
        print(f'{Colors.GREEN}{text}{Colors.ENDC}', end=end)

    @staticmethod
    def error(text):
        exit(f'{Colors.RED}{text}{Colors.ENDC}')

    @staticmethod
    def warning(text, end='\n'):
        print(f'{Colors.YELLOW}{text}{Colors.ENDC}', end=end)

    @staticmethod
    def danger(text, end='\n'):
        print(f'{Colors.RED}{text}{Colors.ENDC}', end=end)

    @staticmethod
    def underline(text, end='\n'):
        print(f'{Colors.UNDERLINE}{text}{Colors.ENDC}', end=end)

    @staticmethod
    def step(index, total, text, end='\n'):
        print(f'{Colors.YELLOW}[{index}/{total}] {text}{Colors.ENDC}', end=end)


def random_string(n=10):
    import random
    import string
    
    chars = string.ascii_lowercase + string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(n))


def find_config():
    DEFAULT_PATH = 'configs/mantis.json'
    env_path = os.environ.get('MANTIS_CONFIG', None)

    if env_path and env_path != '':
        CLI.info(f'Mantis config defined by environment variable $MANTIS_CONFIG: {env_path}')
        return env_path

    CLI.warning('Environment variable $MANTIS_CONFIG not found. Looking for file mantis.json...')
    paths = os.popen('find . -name mantis.json').read().strip().split('\n')

    # Remove empty strings
    paths = list(filter(None, paths))

    total_mantis_files = len(paths)

    if total_mantis_files == 0:
        CLI.warning(f'mantis.json file not found. Using default value: {DEFAULT_PATH}')
        return DEFAULT_PATH

    if total_mantis_files == 1:
        CLI.info(f'Found 1 mantis.json file: {paths[0]}')
        return paths[0]

    paths_per_line = "\n".join(paths)
    CLI.error(f'Found {total_mantis_files} mantis.json files: \n{paths_per_line}\n\nDefine which one to use using $MANTIS_CONFIG environment variable!')


def load_config(config_file):
    with open(config_file) as config:
        return json.load(config)
