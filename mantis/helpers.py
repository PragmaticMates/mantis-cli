import os
import json
from base64 import b64encode, b64decode

try:
    from Crypto.Cipher import AES
    from Crypto.Random import get_random_bytes
    from cryptography.fernet import Fernet
except ImportError:
    # not using cryptography
    # pip install pycryptodome>=3.11.0
    # TODO: only if using environment encryption!
    raise ImportError('Install pycryptodome and cryptography!')


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


class Crypto(object):
    @staticmethod
    def generate_key(deterministically=False):
        if deterministically:
            # deterministically: length has to be 32, 48 or 64
            x = random_string(64)
            from icecream import ic
            return x

        return Fernet.generate_key()

    @staticmethod
    def encrypt(data, key, deterministically=False):
        if deterministically:
            return Crypto.encrypt_deterministically(data, key)

        fernet = Fernet(key.encode())
        encoded = data.encode()
        encrypted = fernet.encrypt(encoded)
        return encrypted.decode()

    @staticmethod
    def encrypt_deterministically(data, key):
        cipher = AES.new(key.encode(), AES.MODE_SIV)
        ciphertext, tag = cipher.encrypt_and_digest(data.encode())
        json_data = {"ciphertext": ciphertext, "tag": tag}
        encoded_json_data = b64encode(str(json_data).encode())
        return encoded_json_data.decode()

    @staticmethod
    def decrypt_deterministically(secret, key):
        try:
            import ast
            json_data = ast.literal_eval(b64decode(secret).decode())
            cipher = AES.new(key.encode(), AES.MODE_SIV)
            data = cipher.decrypt_and_verify(json_data['ciphertext'], json_data['tag'])
            return data.decode()
        except:
            return 'DECRYPTION_ERROR'

    @staticmethod
    def decrypt(secret, key, deterministically=False):
        if deterministically:
            return Crypto.decrypt_deterministically(secret, key)

        fernet = Fernet(key.encode())
        decrypted = fernet.decrypt(secret.encode())
        return decrypted.decode()


def load_config(config_file):
    with open(config_file) as config:
        return json.load(config)
