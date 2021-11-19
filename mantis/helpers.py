from cryptography.fernet import Fernet


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
    def bold(text):
        print(f'{Colors.BOLD}{text}{Colors.ENDC}')

    @staticmethod
    def info(text):
        print(f'{Colors.BLUE}{text}{Colors.ENDC}')

    @staticmethod
    def success(text):
        print(f'{Colors.GREEN}{text}{Colors.ENDC}')

    @staticmethod
    def error(text):
        exit(f'{Colors.RED}{text}{Colors.ENDC}')

    @staticmethod
    def warning(text):
        print(f'{Colors.YELLOW}{text}{Colors.ENDC}')

    @staticmethod
    def danger(text):
        print(f'{Colors.RED}{text}{Colors.ENDC}')

    @staticmethod
    def underline(text):
        print(f'{Colors.UNDERLINE}{text}{Colors.ENDC}')

    @staticmethod
    def step(index, total, text):
        print(f'{Colors.YELLOW}[{index}/{total}] {text}{Colors.ENDC}')


class Crypto(object):
    @staticmethod
    def generate_key():
        return Fernet.generate_key()

    @staticmethod
    def encrypt(data, key):
        fernet = Fernet(key.encode())
        encoded = data.encode()
        encrypted = fernet.encrypt(encoded)
        return encrypted.decode()

    @staticmethod
    def decrypt(token, key):
        fernet = Fernet(key.encode())
        decrypted = fernet.decrypt(token.encode())
        return decrypted.decode()
