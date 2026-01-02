from rich.console import Console
from rich.text import Text

# Shared console instance
_console = Console()


class CLI(object):
    @staticmethod
    def _print(text, style, end='\n'):
        styled_text = Text(str(text), style=style)
        _console.print(styled_text, end=end)

    @staticmethod
    def error(text):
        styled_text = Text(str(text), style='red')
        _console.print(styled_text)
        exit(1)

    @staticmethod
    def bold(text, end='\n'):
        return CLI._print(text=text, style='bold', end=end)

    @staticmethod
    def info(text, end='\n'):
        return CLI._print(text=text, style='blue', end=end)

    @staticmethod
    def pink(text, end='\n'):
        return CLI._print(text=text, style='magenta', end=end)

    @staticmethod
    def success(text, end='\n'):
        return CLI._print(text=text, style='green', end=end)

    @staticmethod
    def warning(text, end='\n'):
        return CLI._print(text=text, style='yellow', end=end)

    @staticmethod
    def danger(text, end='\n'):
        return CLI._print(text=text, style='red', end=end)

    @staticmethod
    def underline(text, end='\n'):
        return CLI._print(text=text, style='underline', end=end)

    @staticmethod
    def step(index, total, text, end='\n'):
        return CLI._print(text=f'[{index}/{total}] {text}', style='yellow', end=end)

    @staticmethod
    def link(uri, label=None):
        if label is None:
            label = uri
        return f'[link={uri}]{label}[/link]'


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

def merge_json(obj1, obj2):
    # Base case: if both values are dictionaries, merge recursively
    if isinstance(obj1, dict) and isinstance(obj2, dict):
        merged = {}
        for key in obj1.keys() | obj2.keys():  # Union of both sets of keys
            if key in obj1 and key in obj2:
                merged[key] = merge_json(obj1[key], obj2[key])
            elif key in obj1:
                merged[key] = obj1[key]
            else:
                merged[key] = obj2[key]
        return merged
    # If both are lists, combine them
    elif isinstance(obj1, list) and isinstance(obj2, list):
        return obj1 + obj2
    # If both values are not dicts or lists, return value from obj2
    else:
        if obj1 == obj2:
            return obj1
        else:
            raise ValueError(f'Trying to merge objects: {obj1} and {obj2}')
