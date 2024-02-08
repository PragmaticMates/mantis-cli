from base64 import b64encode, b64decode

try:
    from Crypto.Cipher import AES
    from cryptography.fernet import Fernet
except ImportError:
    # not using cryptography
    raise ImportError('Install pycryptodome and cryptography!')

from mantis.helpers import CLI, random_string


class Crypto(object):
    @staticmethod
    def generate_key(deterministically=False):
        if deterministically:
            # deterministically: length has to be 32, 48 or 64
            return random_string(64)
            
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
        data = {"ciphertext": ciphertext, "tag": tag}
        encoded_data = b64encode(str(data).encode())
        return encoded_data.decode()

    @staticmethod
    def decrypt_deterministically(secret, key):
        import ast

        try:
            data = ast.literal_eval(b64decode(secret).decode())
        except UnicodeDecodeError:
            CLI.error('Decryption failed. Check if data are not corrupted.')

        try:
            cipher = AES.new(key.encode(), AES.MODE_SIV)
            data = cipher.decrypt_and_verify(data['ciphertext'], data['tag'])
        except ValueError as e:
            if str(e) == 'MAC check failed':
                CLI.error('MAC check failed. You are probably decrypting with incorrect key.')
            CLI.error(str(e))

        return data.decode()

    @staticmethod
    def decrypt(secret, key, deterministically=False):
        if deterministically:
            return Crypto.decrypt_deterministically(secret, key)

        fernet = Fernet(key.encode())
        decrypted = fernet.decrypt(secret.encode())
        return decrypted.decode()
