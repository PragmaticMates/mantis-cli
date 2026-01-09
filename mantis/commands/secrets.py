"""Cryptography commands: show-env, encrypt-env, decrypt-env, check-env, generate-key, read-key."""
import typer

from mantis.app import command, state
from mantis.helpers import CLI


@command(name="show-env", panel="Secrets")
def show_env(
    keyword: str = typer.Argument(None, help="Filter by filename or variable name"),
):
    """Shows environment variables from .env files"""
    env = state._manager.environment

    if not hasattr(env, 'files') or not env.files:
        print("No environment files found.")
        return

    for env_file in env.files:
        variables = env.load(env_file)

        # Filter by keyword if provided
        if keyword:
            keyword_lower = keyword.lower()
            filename_matches = keyword_lower in env_file.lower()
            matching_vars = {k: v for k, v in variables.items() if keyword_lower in k.lower()}

            if not filename_matches and not matching_vars:
                continue

            CLI.info(f"# {env_file}")
            if filename_matches:
                for key, value in variables.items():
                    print(f"{key}={value}")
            else:
                for key, value in matching_vars.items():
                    print(f"{key}={value}")
        else:
            CLI.info(f"# {env_file}")
            for key, value in variables.items():
                print(f"{key}={value}")

        print()


@command(name="encrypt-env", panel="Secrets")
def encrypt_env(
    force: bool = typer.Option(False, "--force", help="Skip confirmation"),
):
    """Encrypts environment files"""
    state.encrypt_env(params='force' if force else '')


@command(name="decrypt-env", panel="Secrets")
def decrypt_env(
    force: bool = typer.Option(False, "--force", help="Skip confirmation"),
):
    """Decrypts environment files"""
    state.decrypt_env(params='force' if force else '')


@command(name="check-env", panel="Secrets")
def check_env():
    """Compares encrypted and decrypted env files"""
    state.check_env()


@command(name="generate-key", panel="Secrets", no_env=True)
def generate_key():
    """Creates new encryption key"""
    state.generate_key()


@command(name="read-key", panel="Secrets", no_env=True)
def read_key():
    """Returns encryption key value"""
    print(state.read_key())
