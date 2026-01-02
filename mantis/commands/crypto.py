"""Cryptography commands: encrypt-env, decrypt-env, check-env, generate-key, read-key."""
import typer

from mantis.app import command, state


@command(name="encrypt-env", panel="Cryptography")
def encrypt_env(
    force: bool = typer.Option(False, "--force", help="Skip confirmation"),
):
    """Encrypts environment files"""
    state.encrypt_env(params='force' if force else '')


@command(name="decrypt-env", panel="Cryptography")
def decrypt_env(
    force: bool = typer.Option(False, "--force", help="Skip confirmation"),
):
    """Decrypts environment files"""
    state.decrypt_env(params='force' if force else '')


@command(name="check-env", panel="Cryptography")
def check_env():
    """Compares encrypted and decrypted env files"""
    state.check_env()


@command(name="generate-key", panel="Cryptography", no_env=True)
def generate_key():
    """Creates new encryption key"""
    state.generate_key()


@command(name="read-key", panel="Cryptography", no_env=True)
def read_key():
    """Returns encryption key value"""
    print(state.read_key())
