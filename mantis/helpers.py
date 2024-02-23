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

    @staticmethod
    def link(uri, label=None):
        if label is None: 
            label = uri
        parameters = ''

        # OSC 8 ; params ; URI ST <name> OSC 8 ;; ST 
        escape_mask = '\033]8;{};{}\033\\{}\033]8;;\033\\'

        return escape_mask.format(parameters, uri, label)


def nested_set(dic, keys, value):
    for key in keys[:-1]:
        dic = dic.setdefault(key, {})
    dic[keys[-1]] = value


def import_string(path):
    components = path.split('.')
    mod = __import__('.'.join(components[0:-1]), globals(), locals(), [components[-1]])
    return getattr(mod, components[-1])


def random_string(n=10):
    import random
    import string
    
    chars = string.ascii_lowercase + string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(n))



