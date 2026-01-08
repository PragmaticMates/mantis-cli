import asyncio
import json
import os
import subprocess
import sys
import time
import yaml
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from time import sleep
from typing import Optional, List, Dict, Any, Tuple

from rich.console import Console
from rich.table import Table

from mantis.crypto import Crypto
from mantis.environment import Environment
from mantis.helpers import CLI, import_string, merge_json
from mantis.config import find_config, load_config, check_config, load_template_config


class AbstractManager(object):
    """
    Abstract manager contains methods which should not be available to call using CLI
    """
    environment_id = None

    def __init__(self, config_file: str = None, environment_id: str = None, mode: str = 'remote', dry_run: bool = False):
        self.environment_id = environment_id
        self.mode = mode
        self.dry_run = dry_run

        # config file
        self.config_file = config_file

        if not config_file:
            self.config_file = find_config(self.environment_id)

        config = load_config(self.config_file)

        # init config
        self.init_config(config)

        # init environment
        self.init_environment()

        self.KEY = self.read_key()
        self.encrypt_deterministically = self.config['encryption']['deterministic']

    @property
    def host(self) -> Optional[str]:
        return self.connection_details['host'] if self.connection_details else None

    @property
    def user(self) -> Optional[str]:
        return self.connection_details['user'] if self.connection_details else None

    @property
    def port(self) -> Optional[str]:
        return self.connection_details['port'] if self.connection_details else None

    def parse_ssh_connection(self, connection: str) -> Dict[str, str]:
        return {
            'host': connection.split("@")[1].split(':')[0],
            'user': connection.split("@")[0].split('://')[1],
            'port': connection.split(":")[-1]
        }

    @property
    def connection_details(self) -> Optional[Dict[str, Optional[str]]]:
        # In single connection mode, env.id is None but we still have a connection
        if not self.single_connection_mode and self.env.id is None:
            return None

        property_name = '_connection_details'
        details = {
            'host': None,
            'user': None,
            'port': None
        }

        if hasattr(self, property_name):
            return getattr(self, property_name)

        if self.env.id and 'local' in self.env.id:
            details = {
                'host': 'localhost',
                'user': None,
                'port': None
            }
        elif self.connection:
            if self.connection.startswith('ssh://'):
                details = self.parse_ssh_connection(self.connection)

            elif self.connection.startswith('context://'):
                context_name = self.connection.replace('context://', '')

                result = subprocess.run(
                    ['docker', 'context', 'inspect', context_name],
                    capture_output=True, text=True
                )
                try:
                    context_details = json.loads(result.stdout)
                    ssh_host = context_details[0]["Endpoints"]["docker"]["Host"]
                    details = self.parse_ssh_connection(ssh_host)
                except (json.JSONDecodeError, IndexError, KeyError):
                    pass
            else:
                raise CLI.error(f'Invalid connection protocol {self.connection}')

        # set to singleton
        setattr(self, property_name, details)

        # set project path
        self.project_path = self.config['project_path']

        return details

    @property
    def docker_connection(self) -> str:
        # In single connection mode or when env.id contains 'local', no extra connection needed
        if not self.single_connection_mode and (self.env.id is None or 'local' in self.env.id):
            return ''

        if self.mode == 'remote':
            if self.connection is None:
                env_info = f' for environment {self.env.id}' if self.env.id else ''
                CLI.error(f'Connection{env_info} not defined!')
            if self.connection.startswith('ssh://'):
                return f'DOCKER_HOST="{self.connection}"'
            elif self.connection.startswith('context://'):
                context_name = self.connection.replace('context://', '')
                return f'DOCKER_CONTEXT={context_name}'

        return ''

    def init_config(self, config: Dict[str, Any]) -> None:
        check_config(config)
        config_file_path = str(Path(self.config_file).parent)

        def normalize(p):
            return str(Path(p.replace('<MANTIS>', config_file_path)).resolve())

        # Load config template file
        defaults = load_template_config()

        # Merge custom config and default values
        defaults.update(config)

        # Save merged config to variable
        self.config = defaults.copy()

        # Detect single connection mode (connection string instead of connections dict)
        has_single_connection = self.config.get('connection') is not None
        has_multiple_connections = bool(self.config.get('connections', {}))

        # Validate: only one of connection or connections should be defined
        if has_single_connection and has_multiple_connections:
            CLI.error('Config error: Cannot define both "connection" and "connections". Use either single connection mode or named environments, not both.')

        self.single_connection_mode = has_single_connection

        # Validate: environment_id should not be provided in single connection mode
        if self.single_connection_mode and self.environment_id:
            CLI.error(f'Config error: Environment "{self.environment_id}" was provided, but config uses single connection mode. Remove the environment argument or switch to named environments using "connections".')

        self.key_file = normalize(str(Path(self.config['encryption']['folder']) / 'mantis.key'))
        self.environment_path = normalize(self.config['environment']['folder'])

        if self.single_connection_mode:
            # In single connection mode, compose files are directly in compose folder
            self.compose_path = normalize(self.config['compose']['folder'])
        elif self.environment_id:
            self.compose_path = normalize(str(Path(self.config['compose']['folder']) / self.environment_id))

    def init_environment(self) -> None:
        if self.single_connection_mode:
            # Single connection mode: no environment_id required
            self.env = Environment(
                environment_id=None,
                folder=self.environment_path,
                single_mode=True,
            )

            # connection from single 'connection' key
            self.connection = self.config.get('connection')

            # compose files directly in compose folder (non-recursive)
            compose_dir = Path(self.compose_path)
            self.compose_files = [str(p) for p in compose_dir.glob('*.yml')] + \
                                 [str(p) for p in compose_dir.glob('*.yaml')]

            # Read compose files
            self.compose_config = self.read_compose_configs()
            return

        if not self.environment_id:
            self.env = Environment(
                environment_id=None,
                folder=self.environment_path,
            )
            self.connection = None
            return

        self.env = Environment(
            environment_id=self.environment_id,
            folder=self.environment_path,
        )

        # connection
        self.connection = self.config['connections'].get(self.env.id, None)

        # compose files (recursive)
        compose_dir = Path(self.compose_path)
        self.compose_files = [str(p) for p in compose_dir.rglob('*.yml')] + \
                             [str(p) for p in compose_dir.rglob('*.yaml')]

        # Read compose files
        self.compose_config = self.read_compose_configs()

    def are_env_files_in_sync(self, env_file: str) -> bool:
        """
        Checks if .env and .env.encrypted files are in sync.
        Returns True if they match, False otherwise.
        """
        env_file_encrypted = f'{env_file}.encrypted'

        # Check if both files exist
        if not Path(env_file).exists():
            return False
        if not Path(env_file_encrypted).exists():
            return False

        try:
            decrypted_environment = self.decrypt_env(env_file=env_file, return_value=True)
            loaded_environment = self.env.load(env_file)

            if decrypted_environment is None or loaded_environment is None:
                return False

            return loaded_environment == decrypted_environment
        except Exception:
            return False

    def check_environment_encryption(self, env_file: str) -> None:
        decrypted_environment = self.decrypt_env(env_file=env_file, return_value=True)  # .env.encrypted
        loaded_environment = self.env.load(env_file)  # .env

        if decrypted_environment is None:
            env_file_encrypted = f'{env_file}.encrypted'
            CLI.error(f'Encrypted environment {env_file_encrypted} is empty!')

        if loaded_environment is None:
            CLI.error(f'Loaded environment {env_file} is empty!')

        if loaded_environment != decrypted_environment:
            CLI.danger('Encrypted and decrypted environment files do NOT match!')

            if loaded_environment is None:
                CLI.danger('Decrypted env from file is empty !')
            elif decrypted_environment is None:
                CLI.danger('Decrypted env is empty !')
            else:
                set1 = set(loaded_environment.items())
                set2 = set(decrypted_environment.items())
                difference = set1 ^ set2

                for var in dict(difference).keys():
                    CLI.info(var, end=': ')

                    encrypted_value = loaded_environment.get(var, '')

                    if encrypted_value == '':
                        CLI.bold('-- empty --', end=' ')
                    else:
                        CLI.warning(encrypted_value, end=' ')

                    print(f'[{env_file}]', end=' / ')

                    decrypted_value = decrypted_environment.get(var, '')

                    if decrypted_value == '':
                        CLI.bold('-- empty --', end=' ')
                    else:
                        CLI.danger(decrypted_value, end=' ')

                    print(f'[{env_file}.encrypted]', end='\n')

        else:
            CLI.success(f'Encrypted and decrypted environments DO match [{env_file}]...')

    def cmd(self, command: str) -> None:
        command = command.strip()

        if self.dry_run:
            CLI.warning(f'[DRY-RUN] {command}')
            return

        error_message = "Error during running command '%s'" % command

        try:
            print(command)
            result = subprocess.run(command, shell=True)
            if result.returncode != 0:
                CLI.error(error_message)
        except OSError as e:
            CLI.error(f"{error_message}: {e}")

    def docker_command(self, command: str, return_output: bool = False, use_connection: bool = True) -> Optional[str]:
        docker_connection = self.docker_connection if use_connection else ''

        cmd = f'{docker_connection} {command}'

        if return_output:
            if self.dry_run:
                CLI.warning(f'[DRY-RUN] {cmd}')
                return ''
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            return result.stdout

        self.cmd(cmd)

    def docker(self, command: str, return_output: bool = False, use_connection: bool = True) -> Optional[str]:
        return self.docker_command(
            command=f'docker {command}',
            return_output=return_output,
            use_connection=use_connection
        )

    def docker_compose(self, command: str, return_output: bool = False, use_connection: bool = True) -> Optional[str]:
        compose_command = self.config['compose']['command']

        compose_files = ' '.join([f'-f {compose_file}' for compose_file in self.compose_files])

        return self.docker_command(
            command=f'{compose_command} {compose_files} {command}',
            return_output=return_output,
            use_connection=use_connection
        )

    def run_parallel(self, commands: List[str], description: str = "Running") -> List[Any]:
        """
        Execute multiple shell commands in parallel using thread pool.

        Args:
            commands: List of shell command strings to execute
            description: Description for progress display
        """
        if not commands:
            return []

        if self.dry_run:
            for cmd in commands:
                CLI.warning(f'[DRY-RUN] {cmd}')
            return []

        def run_cmd(cmd):
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            return result

        with CLI.progress() as progress:
            task = progress.add_task(description, total=len(commands))
            results = []

            with ThreadPoolExecutor(max_workers=min(len(commands), 4)) as executor:
                futures = {executor.submit(run_cmd, cmd): cmd for cmd in commands}

                for future in futures:
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        CLI.warning(f"Command failed: {e}")
                    progress.advance(task)

        return results

    def get_container_project(self, container: str) -> Optional[str]:
        """
        Prints project name of given container
        :param container: container name
        :return: project name
        """
        try:
            container_details = json.loads(self.docker(f'container inspect {container}', return_output=True))
            return container_details[0]["Config"]["Labels"]["com.docker.compose.project"]
        except (IndexError, KeyError):
            pass

        return None

    def get_containers(self, prefix: str = '', exclude: List[str] = None, only_running: bool = False) -> List[str]:
        """
        Prints all project containers
        :param prefix: container prefix
        :param exclude: exclude containers
        :return: list of container names
        """
        if exclude is None:
            exclude = []
        containers = self.docker(f'container ls {"" if only_running else "-a"} --format \'{{{{.Names}}}}\'', return_output=True) \
            .strip('\n').strip().split('\n')

        # Remove empty strings
        containers = list(filter(None, containers))

        # get project containers only
        containers = list(filter(lambda c: self.get_container_project(c) in self.project_services().keys(), containers))

        # find containers starting with custom prefix
        containers = list(filter(lambda s: s.startswith(prefix), containers))

        # exclude not matching containers
        containers = list(filter(lambda s: s not in exclude, containers))

        return containers


class BaseManager(AbstractManager):
    """
    Base manager contains methods which should be available to call using CLI
    """

    def check_config(self) -> None:
        """
        Validates config file according to template
        """
        check_config(self.config)

    def read_key(self) -> Optional[str]:
        """
        Returns value of mantis encryption key
        """
        if not Path(self.key_file).exists():
            CLI.warning(f'File {self.key_file} does not exist. Reading key from $MANTIS_KEY...')
            return os.environ.get('MANTIS_KEY', None)

        with open(self.key_file, "r") as f:
            return f.read().strip()

    def generate_key(self) -> None:
        """
        Creates new encryption key
        """
        CLI.info(f'Deterministic encryption: ', end='')
        CLI.warning(self.encrypt_deterministically)

        key = Crypto.generate_key(self.encrypt_deterministically)
        CLI.bold('Generated cryptography key: ', end='')
        CLI.pink(key)
        CLI.danger(f'Save it to {self.key_file} and keep safe !!!')

    def encrypt_env(self, params: str = '', env_file: Optional[str] = None, return_value: bool = False) -> Optional[Dict[str, str]]:
        """
        Encrypts all environment files (force param skips user confirmation)
        """
        if env_file is None:
            CLI.info(f'Environment file not specified. Walking all environment files...')

            values = {}

            for env_file in self.env.files:
                value = self.encrypt_env(params=params, env_file=env_file, return_value=return_value)
                if return_value:
                    values.update(value)

            return values if return_value else None

        env_file_encrypted = f'{env_file}.encrypted'

        # Skip if files are already in sync (unless return_value is True, which is used for internal checks)
        if not return_value and self.are_env_files_in_sync(env_file):
            CLI.success(f'Skipping {env_file} - already in sync with {env_file_encrypted}')
            return None

        CLI.info(f'Encrypting environment file {env_file}...')

        if not self.KEY:
            CLI.error('Missing mantis key! (%s)' % self.key_file)

        decrypted_lines = self.env.read(env_file)

        if not decrypted_lines:
            return None

        encrypted_lines = []
        encrypted_env = {}

        for line in decrypted_lines:
            if Environment.is_valid_line(line):
                var, decrypted_value = Environment.parse_line(line)
                encrypted_value = Crypto.encrypt(decrypted_value, self.KEY, self.encrypt_deterministically)
                encrypted_lines.append(f'{var}={encrypted_value}')
                encrypted_env[var] = encrypted_value
            else:
                encrypted_lines.append(line)

            if not return_value and 'force' not in params:
                print(encrypted_lines[-1])

        if return_value:
            return encrypted_env

        if 'force' in params:
            Environment.save(env_file_encrypted, encrypted_lines)
            CLI.success(f'Saved to file {env_file_encrypted}')
        else:
            # save to file?
            CLI.warning(f'Save to file {env_file_encrypted}?')

            save_to_file = input("(Y)es or (N)o: ")

            if save_to_file.lower() == 'y':
                Environment.save(env_file_encrypted, encrypted_lines)
                CLI.success(f'Saved to file {env_file_encrypted}')
            else:
                CLI.warning(f'Save it to {env_file_encrypted} manually.')

    def decrypt_env(self, params: str = '', env_file: Optional[str] = None, return_value: bool = False) -> Optional[Dict[str, str]]:
        """
        Decrypts all environment files (force param skips user confirmation)
        """
        if env_file is None:
            CLI.info(f'Environment file not specified. Walking all environment files...')

            values = {}

            for encrypted_env_file in self.env.encrypted_files:
                env_file = encrypted_env_file.rstrip('.encrypted')
                value = self.decrypt_env(params=params, env_file=env_file, return_value=return_value)
                if return_value:
                    values.update(value)

            return values if return_value else None

        env_file_encrypted = f'{env_file}.encrypted'

        # Skip if files are already in sync (unless return_value is True, which is used for internal checks)
        if not return_value and self.are_env_files_in_sync(env_file):
            CLI.success(f'Skipping {env_file_encrypted} - already in sync with {env_file}')
            return None

        if not return_value:
            CLI.info(f'Decrypting environment file {env_file_encrypted}...')

        if not self.KEY:
            CLI.error('Missing mantis key!')

        encrypted_lines = self.env.read(env_file_encrypted)

        if encrypted_lines is None:
            return None

        if not encrypted_lines:
            return {}

        decrypted_lines = []
        decrypted_env = {}

        for line in encrypted_lines:
            if Environment.is_valid_line(line):
                var, encrypted_value = Environment.parse_line(line)
                decrypted_value = Crypto.decrypt(encrypted_value, self.KEY, self.encrypt_deterministically)
                decrypted_lines.append(f'{var}={decrypted_value}')
                decrypted_env[var] = decrypted_value
            else:
                decrypted_lines.append(line)

            if not return_value and 'force' not in params:
                print(decrypted_lines[-1])

        if return_value:
            return decrypted_env

        if 'force' in params:
            Environment.save(env_file, decrypted_lines)
            CLI.success(f'Saved to file {env_file}')
        else:
            # save to file?
            CLI.warning(f'Save to file {env_file}?')

            save_to_file = input("(Y)es or (N)o: ")

            if save_to_file.lower() == 'y':
                Environment.save(env_file, decrypted_lines)
                CLI.success(f'Saved to file {env_file}')
            else:
                CLI.warning(f'Save it to {env_file} manually.')

    def check_env(self) -> None:
        """
        Compares encrypted and decrypted env files
        """
        if not hasattr(self.env, 'encrypted_files'):
            CLI.error('No encrypted files')

        # check if pair file exists
        for encrypted_env_file in self.env.encrypted_files:
            env_file = encrypted_env_file.rstrip('.encrypted')
            if not Path(env_file).exists():
                CLI.warning(f'Environment file {env_file} does not exist')

        if not hasattr(self.env, 'files'):
            CLI.error('No environment files')

        for env_file in self.env.files:
            env_file_encrypted = f'{env_file}.encrypted'

            # check if pair file exists
            if not Path(env_file_encrypted).exists():
                CLI.warning(f'Environment file {env_file_encrypted} does not exist')
                continue

            # check encryption values
            self.check_environment_encryption(env_file)

    def contexts(self) -> None:
        """
        Prints all docker contexts
        """
        self.cmd('docker context ls')

    def create_context(self) -> None:
        """
        Creates docker context using user inputs
        """
        CLI.info('Creating docker context')
        protocol = input("Protocol: (U)nix or (S)sh: ")

        if protocol.lower() == 'u':
            protocol = 'unix'
            socket = input("Socket: ")
            host = f'{protocol}://{socket}'
        elif protocol.lower() == 's':
            protocol = 'ssh'
            host_address = input("Host address: ")
            username = input("Username: ")
            port = input("Port: ")
            host = f'{protocol}://{username}@{host_address}:{port}'
        else:
            CLI.error('Invalid protocol')

        endpoint = f'host={host}'

        # CLI.warning(f'Endpoint: {endpoint}')

        description = input("Description: ")
        name = input("Name: ")

        command = f'docker context create \\\n' \
                  f'    --docker {endpoint} \\\n' \
                  f'    --description="{description}" \\\n' \
                  f'    {name}'

        CLI.warning(command)

        if input("Confirm? (Y)es/(N)o: ").lower() != 'y':
            CLI.error('Canceled')

        # create context
        self.cmd(command)
        self.contexts()

    def get_container_suffix(self, service: str) -> str:
        """
        Returns the suffix used for containers for given service
        """
        delimiter = '-'
        return f'{delimiter}{service}'

    def get_container_name(self, service: str) -> str:
        """
        Constructs container name with project prefix for given service
        """
        suffix = self.get_container_suffix(service)
        prefix = self.get_project_by_service(service)
        return f'{prefix}{suffix}'.replace('_', '-')

    def get_service_containers(self, service: str) -> List[str]:
        """
        Prints container names of given service
        """
        containers = self.docker_compose("ps --format '{{.Names}}' %s" % service, return_output=True)
        return containers.strip().split('\n')

    def get_number_of_containers(self, service: str) -> int:
        """
        Prints number of containers for given service
        """
        return len(self.get_service_containers(service))

    def get_image_suffix(self, service: str) -> str:
        """
        Returns the suffix used for image for given service
        """
        delimiter = '_'
        return f'{delimiter}{service}'

    def get_image_name(self, service: str) -> str:
        """
        Constructs image name for given service
        """
        suffix = self.get_image_suffix(service)
        prefix = self.get_project_by_service(service)
        return f'{prefix}{suffix}'.replace('-', '_')

    def has_healthcheck(self, container: str) -> bool:
        """
        Checks if given container has defined healthcheck
        """
        healthcheck_config = self.get_healthcheck_config(container)

        return healthcheck_config and healthcheck_config.get('Test') != ['NONE']

    def get_healthcheck_start_period(self, container: str) -> Optional[float]:
        """
        Returns healthcheck start period for given container (if any)
        """
        healthcheck_config = self.get_healthcheck_config(container)

        try:
            return healthcheck_config['StartPeriod'] / 1000000000
        except (KeyError, TypeError):
            # TODO: return default value as fallback?
            return None

    def check_health(self, container: str) -> Optional[Tuple[bool, str]]:
        """
        Checks current health of given container
        """
        if self.has_healthcheck(container):
            command = f'inspect --format="{{{{json .State.Health.Status}}}}" {container}'
            status = self.docker(command, return_output=True).strip(' \n"')

            if status == 'healthy':
                return True, status
            else:
                return False, status

    def healthcheck(self, container: str) -> Optional[bool]:
        """
        Execute health-check of given project container
        """
        if container not in self.get_containers():
            CLI.error(f"Container {container} not found")

        console = Console()
        console.print(f'[blue]Health-checking [yellow]{container}[/yellow]...[/blue]')

        if self.has_healthcheck(container):
            healthcheck_config = self.get_healthcheck_config(container)
            coeficient = 10
            healthcheck_interval = healthcheck_config.get('Interval', 1000000000) / 1000000000
            healthcheck_retries = healthcheck_config.get('Retries', 10)
            interval = healthcheck_interval / coeficient
            retries = healthcheck_retries * coeficient

            console.print(f'[blue]Interval: [dim]{healthcheck_interval}[/dim] s -> [yellow]{interval} s[/yellow][/blue]')
            console.print(f'[blue]Retries: [dim]{healthcheck_retries}[/dim] -> [yellow]{retries}[/yellow][/blue]')

            start = time.time()

            for retry in range(retries):
                is_healthy, status = self.check_health(container)

                if is_healthy:
                    console.print(f"#{retry + 1}/{retries}: Status of '{container}' is [green]{status}[/green].")
                    end = time.time()
                    loading_time = end - start
                    console.print(f'Container [yellow]{container}[/yellow] took [blue underline]{loading_time} s[/blue underline] to become healthy')
                    return True
                else:
                    console.print(f"#{retry + 1}/{retries}: Status of '{container}' is [red]{status}[/red].")

                if retries > 1:
                    sleep(interval)

            # All retries exhausted, container is unhealthy
            console.print(f'[red bold]Container {container} failed to become healthy after {retries} retries[/red bold]')
            return False
        else:
            CLI.warning(f"Container '{container}' doesn't have healthcheck command defined. Looking for start period value...")
            start_period = self.get_healthcheck_start_period(container)

            if start_period is None:
                CLI.danger(f"Container '{container}' doesn't have neither healthcheck command or start period defined.")
                CLI.warning(f'Stopping and removing container {container}')
                self.docker(f'container stop {container}')
                self.docker(f'container rm {container}')
                sys.exit(1)

            # If container doesn't have healthcheck command, sleep for N seconds
            CLI.info(f'Sleeping for {start_period} seconds...')
            sleep(start_period)
            return None

    def build(self, services: Optional[List[str]] = None) -> None:
        """
        Builds all services with Dockerfiles
        """
        CLI.info(f'Building...')
        params = ' '.join(services) if services else ''
        CLI.info(f'Services = {params}')

        # Construct build args from config
        build_args = self.config['build']['args']
        build_args = ','.join(map('='.join, build_args.items()))

        if build_args != '':
            build_args = build_args.split(',')
            build_args = [f'--build-arg {arg}' for arg in build_args]
            build_args = ' '.join(build_args)

        CLI.info(f'Args = {build_args}')

        build_tool = self.config['build']['tool']
        available_tools = ['compose', 'docker']

        if build_tool == 'compose':
            # Build all services using docker compose
            self.docker_compose(f'build {build_args} {params} --pull', use_connection=False)
        elif build_tool == 'docker':
            # Build commands for parallel execution
            docker_connection = ''  # use_connection=False
            build_commands = []

            for service, info in self.services_to_build().items():
                platform = f"--platform={info['platform']}" if info['platform'] != '' else ''
                cache_from = ' '.join([f"--cache-from {cache}" for cache in info['cache_from']]) if info['cache_from'] != [] else ''
                args = ' '.join([f"--build-arg {key}={value}" for key, value in info['args'].items()]) if info['args'] != {} else ''
                image = info['image'] if info['image'] != '' else f"{info['project_name']}-{service}".lstrip('-')

                # build paths for docker build command (paths in compose are relative to compose file, but paths for docker command are relative to $PWD)
                context = str(Path(self.compose_path) / info['context'])
                dockerfile = str(Path(context) / info['dockerfile'])

                cmd = f"{docker_connection} docker build {context} {build_args} {args} {platform} {cache_from} -t {image} -f {dockerfile} {params}"
                build_commands.append(cmd.strip())

            # Run builds in parallel
            if build_commands:
                CLI.info(f'Building {len(build_commands)} services in parallel...')
                self.run_parallel(build_commands, "Building services")
        else:
            CLI.error(f'Unknown build tool: {build_tool}. Available tools: {", ".join(available_tools)}')

    def project_services(self) -> Dict[str, List[str]]:
        """
        Returns project names by compose files
        """
        projects = defaultdict(list)

        for compose_file in self.compose_files:
            with open(compose_file, 'r') as file:
                compose_data = yaml.safe_load(file)
                name = compose_data.get('name', '')
                services = compose_data.get('services', {}).keys()
                projects[name].extend(services)

        return projects

    def get_project_by_service(self, service: str) -> Optional[str]:
        project_services = self.project_services()

        for project, services in project_services.items():
            if service in services:
                return project

        return None

    def services(self, compose_file: Optional[str] = None) -> List[str]:
        """
        Returns all defined services
        """
        services = []

        compose_files = [compose_file] if compose_file else self.compose_files

        for compose_file in compose_files:
            with open(compose_file, 'r') as file:
                compose_data = yaml.safe_load(file)
                compose_services = compose_data.get('services', {}).keys()

                services += compose_services

        return services

    def services_to_build(self, compose_file: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """
        Prints all services which will be build
        """
        data = {}

        compose_files = [compose_file] if compose_file else self.compose_files

        for compose_file in compose_files:
            with open(compose_file, 'r') as file:
                compose_data = yaml.safe_load(file)

            services = compose_data.get('services', {})
            for service_name, service_config in services.items():
                build = service_config.get('build', None)

                if build:
                    data[service_name] = {
                        'project_name': compose_data.get('name', ''),
                        'dockerfile': build.get('dockerfile', 'Dockerfile'),
                        'context': build.get('context', '.'),
                        'cache_from': build.get('cache_from', []),
                        'args': build.get('args', {}),
                        'image': service_config.get('image', ''),
                        'platform': service_config.get('platform', '')
                    }

        return data

    def push(self, services: Optional[List[str]] = None) -> None:
        """
        Push built images to repository
        """
        CLI.info(f'Pushing...')
        params = ' '.join(services) if services else ''
        CLI.info(f'Services = {params}')

        # Push using docker compose
        self.docker_compose(f'push {params}', use_connection=False)

    def pull(self, services: Optional[List[str]] = None) -> None:
        """
        Pulls required images for services
        """
        CLI.info('Pulling...')
        params = ' '.join(services) if services else ''
        CLI.info(f'Services = {params}')

        # Pull using docker compose
        self.docker_compose(f'pull {params}')

    def upload(self) -> None:
        """
        Uploads mantis config, compose file <br/>and environment files to server
        """
        if self.env.id == 'local':
            print('Skipping for local...')
        elif not self.connection:
            CLI.warning('Connection not defined. Skipping uploading files')
        elif self.mode == 'host':
            CLI.warning('Not uploading due to host mode! Be sure your configs on host are up to date!')
        elif self.mode == 'ssh':
            CLI.info('Uploading docker compose configs, environment files and mantis')

            files_to_upload = [self.config_file] + self.compose_files + self.env.files

            # mantis config file
            for file in files_to_upload:
                if Path(file).exists():
                    self.cmd(f'rsync -arvz -e \'ssh -p {self.port}\' -rvzh --progress {file} {self.user}@{self.host}:{self.project_path}/{file}')
                else:
                    CLI.info(f'{self.config_file} does not exists. Skipping...')

    def restart(self, service: Optional[str] = None) -> None:
        """
        Restarts all containers by calling compose down and up
        """
        if service:
            return self.restart_service(service)

        CLI.info('Restarting...')

        # run down project containers
        CLI.step(1, 3, 'Running down project containers...')
        self.down()

        # recreate project
        CLI.step(2, 3, 'Recreating project containers...')
        self.up()

        # remove suffixes and reload webserver
        self.remove_suffixes()
        self.try_to_reload_webserver()

        # clean
        CLI.step(3, 3, 'Prune Docker images')
        self.clean()

    def deploy(self, dirty: bool = False, strategy: str = 'blue-green') -> None:
        """
        Runs deployment process: uploads files, pulls images, runs zero-downtime deployment, removes suffixes, reloads webserver, clean

        Args:
            dirty: Skip zero-downtime and cleaning steps
            strategy: Deployment strategy - 'rolling' (one-by-one) or 'blue-green' (scale 2x)
        """
        CLI.info('Deploying...')

        if dirty:
            CLI.warning('...but dirty (no zero-downtime, without cleaning)')

        self.upload()
        self.pull()

        is_running = len(self.get_containers(only_running=True)) != 0

        if is_running and not dirty:
            if strategy == 'rolling':
                CLI.info('Using rolling update strategy (one-by-one)...')
                success = self.rolling_update()
            else:  # blue-green
                CLI.info('Using blue-green strategy (scale 2x)...')
                success = self.zero_downtime()

            if not success:
                CLI.danger('Deployment aborted due to rollback.')
                return

        # Preserve number of scaled containers
        scale_param: List[str] = []
        if is_running:
            scales = {}
            for service in self.services():
                replicas = self.get_deploy_replicas(service)
                number_of_containers = self.get_number_of_containers(service)

                # ensure the number of containers is at least as default number of replicas
                if number_of_containers > replicas:
                    scales[service] = number_of_containers

            scale_param = [f'--scale {service}={scale}' for service, scale in scales.items()]

        self.up(scale_param if scale_param else None)
        self.remove_suffixes()
        self.try_to_reload_webserver()

        if not dirty:
            self.clean()

        CLI.success('Deployment complete!')

    def zero_downtime(self, service: Optional[str] = None) -> bool:
        """
        Runs zero-downtime deployment of services (or given service).
        Returns True if zero downtime was successful, False otherwise (rollback performed).
        """
        if not service:
            zero_downtime_services = self.config['zero_downtime']
            for index, service in enumerate(zero_downtime_services):
                CLI.step(index + 1, len(zero_downtime_services), f'Zero downtime services: {zero_downtime_services}')
                if not self.zero_downtime(service):
                    return False  # Rollback happened, stop processing
            return True

        container_prefix = self.get_container_name(service)

        old_containers = self.get_containers(prefix=container_prefix, only_running=True)
        num_containers = len(old_containers)

        if num_containers == 0:
            CLI.danger(f'Old container for service {service} not found. Skipping zero-downtime deployment...')
            return True

        # run new containers
        scale = num_containers * 2
        self.scale(service, scale)

        # healthcheck
        new_containers = self.get_containers(prefix=container_prefix, exclude=old_containers, only_running=True)
        unhealthy_containers = []

        for new_container in new_containers:
            is_healthy = self.healthcheck(container=new_container)
            if is_healthy is False:
                unhealthy_containers.append(new_container)

        # Handle unhealthy containers
        if unhealthy_containers:
            console = Console()
            console.print(f'\n[red bold]⚠ Unhealthy containers detected: {", ".join(unhealthy_containers)}[/red bold]\n')

            # Show logs of unhealthy containers
            for container in unhealthy_containers:
                console.print(f'[yellow]Logs for {container}:[/yellow]')
                self.docker(f'logs {container} --tail 50')
                console.print('')

            # Ask user if they want to rollback
            rollback = CLI.timed_confirm(
                "Rollback deployment? (stop new containers and keep old ones)",
                timeout=10,
                default=False
            )

            if rollback:
                console.print(f'\n[yellow]Rolling back deployment for service {service}...[/yellow]')

                # Stop and remove unhealthy new containers
                for new_container in new_containers:
                    if new_container in self.get_containers():
                        CLI.info(f'Stopping new container [{new_container}]...')
                        self.docker(f'container stop {new_container}')
                        CLI.info(f'Removing new container [{new_container}]...')
                        self.docker(f'container rm {new_container}')

                CLI.success(f'Rollback complete. Old containers preserved: {old_containers}')
                return False  # Not successful zero-downtime. Rollback performed
            else:
                console.print(f'\n[yellow]Continuing deployment with potentially unhealthy containers...[/yellow]')

        # reload webserver
        self.try_to_reload_webserver()

        # Stop and remove old container
        CLI.info(f'Stopping old containers of service {service}: {old_containers}')

        for old_container in old_containers:
            if old_container in self.get_containers():
                CLI.info(f'Stopping old container [{old_container}]...')
                self.docker(f'container stop {old_container}')

                CLI.info(f'Removing old container [{old_container}]...')
                self.docker(f'container rm {old_container}')
            else:
                CLI.info(f'{old_container} was not running')

        # rename new container
        for index, new_container in enumerate(new_containers):
            CLI.info(f'Renaming new container [{new_container}]...')
            self.docker(f'container rename {new_container} {container_prefix}-{index + 1}')

        self.remove_suffixes(prefix=container_prefix)

        # reload webserver
        self.try_to_reload_webserver()

        return True  # Successful zero-downtime. No rollback

    def rolling_update(self, service: Optional[str] = None) -> bool:
        """
        Performs rolling update of service containers one at a time.

        Flow for each container:
        1. Start 1 new container
        2. Wait for healthy
        3. Reload webserver
        4. Remove 1 old container

        Returns True if successful, False if rollback was performed.
        """
        if not service:
            # Process all zero_downtime services
            zero_downtime_services = self.config['zero_downtime']
            for index, service in enumerate(zero_downtime_services):
                CLI.step(index + 1, len(zero_downtime_services), f'Rolling update: {service}')
                if not self.rolling_update(service):
                    return False  # Rollback happened, stop processing
            return True

        console = Console()
        container_prefix = self.get_container_name(service)
        old_containers = self.get_containers(prefix=container_prefix, only_running=True)
        num_containers = len(old_containers)

        if num_containers == 0:
            CLI.danger(f'No running containers for service {service}. Skipping rolling update...')
            return True

        console.print(f'\n[blue]Starting rolling update for [yellow]{service}[/yellow] ({num_containers} containers)[/blue]\n')

        # Track containers we've successfully replaced
        replaced_count = 0

        for i, old_container in enumerate(old_containers):
            step = i + 1
            console.print(f'[cyan]━━━ Container {step}/{num_containers} ━━━[/cyan]')

            # Step 1: Scale up by 1 (start new container)
            current_count = len(self.get_containers(prefix=container_prefix, only_running=True))
            CLI.info(f'Starting new container (scaling {current_count} → {current_count + 1})...')
            self.scale(service, current_count + 1)

            # Get the new container (the one that wasn't there before)
            all_current = self.get_containers(prefix=container_prefix, only_running=True)
            new_container = None
            for c in all_current:
                if c not in old_containers and c != old_container:
                    # Check if this is a newly created container
                    if new_container is None or c > new_container:  # Higher suffix = newer
                        new_container = c

            if not new_container:
                # Fallback: get the container with highest suffix
                new_container = sorted(all_current)[-1]

            CLI.info(f'New container: {new_container}')

            # Step 2: Wait for healthy
            is_healthy = self.healthcheck(container=new_container)

            if is_healthy is False:
                # Show logs
                console.print(f'\n[red bold]⚠ Container {new_container} failed health check[/red bold]\n')
                console.print(f'[yellow]Logs for {new_container}:[/yellow]')
                self.docker(f'logs {new_container} --tail 50')
                console.print('')

                # Ask for rollback
                rollback = CLI.timed_confirm(
                    "Rollback? (stop new container, keep remaining old ones)",
                    timeout=10,
                    default=False
                )

                if rollback:
                    console.print(f'\n[yellow]Rolling back...[/yellow]')

                    # Stop and remove the failed new container
                    if new_container in self.get_containers():
                        self.docker(f'container stop {new_container}')
                        self.docker(f'container rm {new_container}')

                    remaining_old = old_containers[i:]  # Containers we haven't replaced yet
                    CLI.success(f'Rollback complete. Preserved: {remaining_old}')
                    CLI.info(f'Successfully replaced {replaced_count}/{num_containers} containers before failure.')
                    return False
                else:
                    console.print(f'[yellow]Continuing with potentially unhealthy container...[/yellow]')

            # Step 3: Reload webserver (new container now receiving traffic)
            self.try_to_reload_webserver()

            # Step 4: Stop and remove old container
            CLI.info(f'Removing old container: {old_container}')
            if old_container in self.get_containers():
                self.docker(f'container stop {old_container}')
                self.docker(f'container rm {old_container}')

            replaced_count += 1
            console.print(f'[green]✓ Replaced {old_container} → {new_container}[/green]\n')

        # Rename containers to clean suffixes
        final_containers = self.get_containers(prefix=container_prefix, only_running=True)
        for index, container in enumerate(sorted(final_containers)):
            new_name = f'{container_prefix}-{index + 1}'
            if container != new_name:
                CLI.info(f'Renaming {container} → {new_name}')
                self.docker(f'container rename {container} {new_name}')

        self.remove_suffixes(prefix=container_prefix)
        self.try_to_reload_webserver()

        console.print(f'\n[green bold]✓ Rolling update complete for {service}[/green bold]\n')
        return True

    def remove_suffixes(self, prefix: str = '') -> None:
        """
        Removes numerical suffixes from container names (if scale == 1)
        """
        for service in self.services():
            containers = self.get_service_containers(service)

            num_containers = len(containers)

            if num_containers != 1:
                CLI.info(f'Service {service} has {num_containers} containers. Skipping removing suffix.')
                continue

            container = containers[0]

            if not container.split('-')[-1].isdigit():
                continue

            new_container = container.rsplit('-', maxsplit=1)[0]
            defined_container_name = self.compose_config.get('services', {}).get(service, {}).get('container_name', None)

            if container == defined_container_name:
                CLI.info(f'Service {service} has defined the same container name ({defined_container_name}). Skipping removing suffix.')
                continue

            if container not in self.services():
                CLI.info(f'Removing suffix of container {container}')
                self.docker(f'container rename {container} {new_container}')

    def restart_service(self, service: str) -> None:
        """
        Stops, removes and recreates container for given service
        """
        container = self.get_container_name(service)

        CLI.underline(f'Recreating {service} container ({container})...')

        app_containers = self.get_containers(prefix=container)
        for app_container in app_containers:
            if app_container in self.get_containers():
                CLI.info(f'Stopping container [{app_container}]...')
                self.docker(f'container stop {app_container}')

                CLI.info(f'Removing container [{app_container}]...')
                self.docker(f'container rm {app_container}')
            else:
                CLI.info(f'{app_container} was not running')

        CLI.info(f'Creating new container [{container}]...')
        self.up(['--no-deps', '--no-recreate', service])
        self.remove_suffixes(prefix=container)

    def try_to_reload_webserver(self) -> None:
        """
        Tries to reload webserver (if suitable extension is available)
        """
        try:
            self.reload_webserver()
        except AttributeError:
            CLI.warning('Tried to reload webserver, but no suitable extension found!')

    def stop(self, containers: Optional[List[str]] = None) -> None:
        """
        Stops all or given project containers
        """
        CLI.info('Stopping containers...')

        if not containers:
            containers = self.get_containers()

        steps = len(containers)

        for index, container in enumerate(containers):
            CLI.step(index + 1, steps, f'Stopping {container}')
            self.docker(f'container stop {container}')

    def kill(self, containers: Optional[List[str]] = None) -> None:
        """
        Kills all or given project containers
        """
        CLI.info('Killing containers...')

        if not containers:
            containers = self.get_containers()

        steps = len(containers)

        for index, container in enumerate(containers):
            CLI.step(index + 1, steps, f'Killing {container}')
            self.docker(f'container kill {container}')

    def start(self, containers: Optional[List[str]] = None) -> None:
        """
        Starts all or given project containers
        """
        CLI.info('Starting containers...')

        if not containers:
            containers = self.get_containers()

        steps = len(containers)

        for index, container in enumerate(containers):
            CLI.step(index + 1, steps, f'Starting {container}')
            self.docker(f'container start {container}')

    def run(self, params: List[str]) -> None:
        """
        Calls compose run with params
        """
        params_str = ' '.join(params) if params else ''
        CLI.info(f'Running {params_str}...')
        self.docker_compose(f'run {params_str}')

    def up(self, params: Optional[List[str]] = None) -> None:
        """
        Calls compose up (with optional params)
        """
        params_str = ' '.join(params) if params else ''
        CLI.info(f'Starting up {params_str}...')
        self.docker_compose(f'up {params_str} -d')

    def down(self, params: Optional[List[str]] = None) -> None:
        """
        Calls compose down (with optional params)
        """
        params_str = ' '.join(params) if params else ''
        CLI.info(f'Running down {params_str}...')
        self.docker_compose(f'down {params_str}')

    def scale(self, service: str, scale: int) -> None:
        """
        Scales service to given scale
        """
        self.up([f'--no-deps', '--no-recreate', '--scale', f'{service}={scale}'])

    def remove(self, containers: Optional[List[str]] = None, force: bool = False) -> None:
        """
        Removes all or given project containers
        """
        CLI.info('Removing containers...')

        if not containers:
            containers = self.get_containers()

        steps = len(containers)
        force_flag = '-f ' if force else ''

        for index, container in enumerate(containers):
            CLI.step(index + 1, steps, f'Removing {container}')
            self.docker(f'container rm {force_flag}{container}')

    def rename(self, container: str, new_name: str) -> None:
        """
        Renames container to a new name
        """
        CLI.info(f'Renaming container {container} to {new_name}')
        self.docker(f'container rename {container} {new_name}')

    def clean(self, params: Optional[List[str]] = None) -> None:  # todo clean on all nodes
        """
        Clean images, containers, networks
        """
        CLI.info('Cleaning...')
        params_str = ' '.join(params) if params else ''
        # self.docker(f'builder prune')
        self.docker(f'system prune {params_str} -a --force')
        # self.docker(f'container prune')
        # self.docker(f'container prune --force')

    def status(self) -> None:
        """
        Prints images and containers
        """
        console = Console()

        CLI.info('Getting status...')
        steps = 2

        CLI.step(1, steps, 'List of Docker images')
        images_output = self.docker('image ls --format "{{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.CreatedSince}}\t{{.Size}}"', return_output=True)

        if images_output.strip():
            images_table = Table(show_header=True, header_style="bold")
            images_table.add_column("REPOSITORY", style="cyan")
            images_table.add_column("TAG", style="yellow")
            images_table.add_column("IMAGE ID", style="bright_blue")
            images_table.add_column("CREATED", style="magenta")
            images_table.add_column("SIZE", style="green")

            for line in images_output.strip().split('\n'):
                parts = line.split('\t')
                if len(parts) >= 5:
                    repo, tag, image_id, created, size = parts[0], parts[1], parts[2], parts[3], parts[4]
                    images_table.add_row(repo, tag, image_id, created, size)

            console.print(images_table)

        CLI.step(2, steps, 'Docker containers')
        containers_output = self.docker('container ls -a --format "{{.Names}}\t{{.Status}}\t{{.Image}}\t{{.Ports}}\t{{.Size}}"', return_output=True)

        if containers_output.strip():
            containers_table = Table(show_header=True, header_style="bold")
            containers_table.add_column("NAME", style="blue")
            containers_table.add_column("STATUS")
            containers_table.add_column("IMAGE", style="magenta")
            containers_table.add_column("PORTS")
            containers_table.add_column("SIZE", style="dark_orange")

            for line in containers_output.strip().split('\n'):
                parts = line.split('\t')
                if len(parts) >= 5:
                    name, status, image, ports, size = parts[0], parts[1], parts[2], parts[3], parts[4]

                    # Colorize status based on state
                    if 'Up' in status:
                        status_colored = f'[green]{status}[/green]'
                    elif 'Exited' in status:
                        status_colored = f'[red]{status}[/red]'
                    elif 'Created' in status:
                        status_colored = f'[yellow]{status}[/yellow]'
                    elif 'Paused' in status:
                        status_colored = f'[yellow]{status}[/yellow]'
                    else:
                        status_colored = status

                    # Split ports into multiple lines with different colors for IPv4/IPv6
                    ports_list = ports.split(', ') if ports else ['']
                    colored_ports = []
                    for port in ports_list:
                        if '::' in port or '[' in port:
                            # IPv6 port
                            colored_ports.append(f'[bright_white]{port}[/bright_white]')
                        else:
                            # IPv4 port
                            colored_ports.append(f'[cyan]{port}[/cyan]')
                    ports_formatted = '\n'.join(colored_ports)

                    containers_table.add_row(name, status_colored, image, ports_formatted, size)

            console.print(containers_table)

    def networks(self) -> None:
        """
        Prints docker networks
        """
        CLI.info('Getting networks...')
        CLI.warning('List of Docker networks')

        networks = self.docker('network ls', return_output=True)
        networks = networks.strip().split('\n')

        for index, network in enumerate(networks):
            network_data = list(filter(lambda x: x != '', network.split(' ')))
            network_name = network_data[1]

            if index == 0:
                print(f'{network}\tCONTAINERS')
            else:
                containers = self.docker(
                    command=f'network inspect -f \'{{{{ range $key, $value := .Containers }}}}{{{{ .Name }}}} {{{{ end }}}}\' {network_name}',
                    return_output=True
                )
                containers = ', '.join(containers.split())
                print(f'{network}\t{containers}'.strip())

    def logs(self, params: Optional[str] = None) -> None:
        """
        Prints logs of all or given project container
        """
        CLI.info('Reading logs...')

        containers = params.split(' ') if params else self.get_containers()
        lines = '--tail 1000 -f' if params else '--tail 10'
        steps = len(containers)

        for index, container in enumerate(containers):
            CLI.step(index + 1, steps, f'{container} logs')
            self.docker(f'logs {container} {lines}')

    def bash(self, params: str) -> None:
        """
        Runs bash in container
        """
        CLI.info('Running bash...')
        self.docker(f'exec -it --user root {params} /bin/bash')
        # self.docker_compose(f'run --entrypoint /bin/bash {container}')

    def sh(self, params: str) -> None:
        """
        Runs sh in container
        """
        CLI.info('Logging to container...')
        self.docker(f'exec -it --user root {params} /bin/sh')

    def ssh(self) -> None:
        if not self.connection:
            CLI.error('Missing connection details')

        if not self.host:
            CLI.error('Unknown host')

        CLI.info(f'Executing SSH connection: {self.connection}')
        subprocess.run(['ssh', f'{self.user}@{self.host}', '-p', str(self.port or 22)])

    def exec(self, container: str, cmd: list):
        """
        Executes command in container
        """
        command = ' '.join(cmd)
        CLI.info(f'Executing command "{command}" in container {container}...')
        self.docker(f'exec {container} {command}')

    def exec_it(self, container: str, cmd: list):
        """
        Executes command in container using interactive pseudo-TTY
        """
        command = ' '.join(cmd)
        CLI.info(f'Executing command "{command}" in container {container}...')
        self.docker(f'exec -it {container} {command}')

    def get_healthcheck_config(self, container: str) -> Optional[Dict[str, Any]]:
        """
        Prints health-check config (if any) of given container
        """
        try:
            container_details = json.loads(self.docker(f'container inspect {container}', return_output=True))
            return container_details[0]["Config"]["Healthcheck"]
        except (IndexError, KeyError):
            pass

        return None

    def read_compose_configs(self) -> Dict[str, Any]:
        """
        Returns merged compose configs
        """
        config = {}

        for compose_file in self.compose_files:
            with open(compose_file, 'r') as file:
                compose_data = yaml.safe_load(file)
                config = merge_json(config, compose_data)

        return config

    def get_deploy_replicas(self, service: str) -> int:
        """
        Returns default number of deploy replicas of given services
        """
        replicas = 1

        for compose_file in self.compose_files:
            with open(compose_file, 'r') as file:
                compose_data = yaml.safe_load(file)

            try:
                replicas = compose_data['services'][service]['deploy']['replicas']
            except KeyError:
                pass

        return replicas

    def backup_volume(self, volume: str) -> None:
        # backups folder
        backup_path = str(Path.cwd() / 'backups')

        # Get current date, time and timezone name
        current_datetime = datetime.now()
        formatted_datetime = current_datetime.strftime('%Y-%m-%dT%H-%M-%S')
        timezone_name = current_datetime.astimezone().tzname()

        command = f'run --rm \
        -v {volume}:/{volume} \
        -v "{backup_path}":/backup \
        busybox \
        tar -czvf /backup/{volume}-{formatted_datetime}_{timezone_name}.tar.gz /{volume}'

        self.docker(command)

    def restore_volume(self, volume: str, file: str) -> None:
        # backups folder
        backup_path = str(Path.cwd() / 'backups')

        command = f'run --rm \
        -v {volume}:/{volume} \
        -v "{backup_path}":/backup \
        busybox \
        tar -xzvf /backup/{file}'

        self.docker(command)


def get_extension_classes(extensions: List[str]) -> List[type]:
    extension_classes: List[type] = []

    # extensions
    for extension in extensions:
        extension_class_name = extension if '.' in extension else f"mantis.extensions.{extension.lower()}.{extension}"
        extension_class = import_string(extension_class_name)
        extension_classes.append(extension_class)

    return extension_classes


def resolve_environment(environment_id: Optional[str], config: Dict[str, Any]) -> Optional[str]:
    """
    Resolves environment prefix to full environment ID.

    If the prefix matches exactly one environment, returns that environment ID.
    If multiple environments match, raises an error with the ambiguous options.
    If no environments match, raises an error with available options.
    """
    if not environment_id:
        return None

    # Single connection mode - no environment resolution needed
    if config.get('connection'):
        return environment_id

    connections = config.get('connections', {})
    available_envs = list(connections.keys())

    # Check for exact match first
    if environment_id in available_envs:
        return environment_id

    # Find all environments that start with the prefix
    matches = [env for env in available_envs if env.startswith(environment_id)]

    if len(matches) == 1:
        CLI.info(f'Environment "{environment_id}" resolved to "{matches[0]}"')
        return matches[0]
    elif len(matches) > 1:
        CLI.error(f'Ambiguous environment prefix "{environment_id}". Matches: {", ".join(sorted(matches))}')
    else:
        CLI.error(f'Environment "{environment_id}" not found. Available: {", ".join(sorted(available_envs))}')


def get_manager(environment_id: Optional[str], mode: str, dry_run: bool = False) -> BaseManager:
    # config file
    config_file = find_config(environment_id)
    config = load_config(config_file)

    # Resolve environment prefix to full ID
    environment_id = resolve_environment(environment_id, config)

    # class name of the manager
    manager_class_name = config.get('manager_class', 'mantis.managers.BaseManager')

    # get manager class
    manager_class = import_string(manager_class_name)

    # setup extensions
    extensions = config.get('extensions', {})
    extension_classes = get_extension_classes(extensions.keys())

    CLI.info(f"Extensions: {', '.join(extensions.keys())}")

    # create dynamic manager class
    class MantisManager(*[manager_class] + extension_classes):
        pass

    manager = MantisManager(config_file=config_file, environment_id=environment_id, mode=mode, dry_run=dry_run)

    # set extensions data
    for extension, extension_params in extensions.items():
        if 'service' in extension_params:
            setattr(manager, f'{extension}_service'.lower(), extension_params['service'])

    return manager
