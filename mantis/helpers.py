import json


class Colors:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    PINK = '\033[95m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


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


def load_config(config_file):
    with open(config_file) as config:
        return json.load(config)
