import json
import os
import time
import yaml
from os import path
from os.path import dirname, normpath
from time import sleep

from mantis.crypto import Crypto
from mantis.environment import Environment
from mantis.helpers import CLI, Colors, find_config, load_config, check_config


class BaseManager(object):
    environment_id = None

    def __init__(self, config_file=None, environment_id=None, mode='remote'):
        self.environment_id = environment_id
        self.mode = mode

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
        self.encrypt_deterministically = self.config.get('encryption', {}).get('deterministic', True)

    @property
    def host(self):
        return self.connection_details['host']

    @property
    def user(self):
        return self.connection_details['user']

    @property
    def port(self):
        return self.connection_details['port']

    def parse_ssh_connection(self, connection):
        return {
            'host': connection.split("@")[1].split(':')[0],
            'user': connection.split("@")[0].split('://')[1],
            'port': connection.split(":")[-1]
        }

    @property
    def connection_details(self):
        property_name = '_connection_details'
        details = {
            'host': None,
            'user': None,
            'port': None
        }

        if hasattr(self, property_name):
            return getattr(self, property_name)

        if 'local' in self.env.id:
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

                # TODO: move to own method
                context_details = json.loads(os.popen(f'docker context inspect {context_name}').read())

                try:
                    ssh_host = context_details[0]["Endpoints"]["docker"]["Host"]
                    details = self.parse_ssh_connection(ssh_host)
                except IndexError:
                    pass
            else:
                raise CLI.error(f'Invalid connection protocol {self.connection}')

        # set to singleton
        setattr(self, property_name, details)

        # set project path
        self.project_path = self.config.get('project_path', f'/home/{self.user}/public_html/web')

        return details

    @property
    def docker_connection(self):
        if 'local' in self.env.id:
            return ''

        if self.mode == 'remote':
            if self.connection is None:
                CLI.error(f'Connection for environment {self.env.id} not defined!')
            if self.connection.startswith('ssh://'):
                return f'DOCKER_HOST="{self.connection}"'
            elif self.connection.startswith('context://'):
                context_name = self.connection.replace('context://', '')
                return f'DOCKER_CONTEXT={context_name}'

        return ''

    def init_config(self, config):
        self.config = config
        self.check_config()
        self.config_file_path = path.normpath(path.join(self.config_file, os.pardir))
        self.key_path = self.config.get('encryption', {}).get('folder', '<MANTIS>').replace('<MANTIS>', self.config_file_path)
        self.configs_path = self.config.get('configs', {}).get('folder', '<MANTIS>/configs').replace('<MANTIS>', self.config_file_path)
        self.environment_path = self.config.get('environment', {}).get('folder', '<MANTIS>/environments').replace('<MANTIS>', self.config_file_path)
        self.compose_path = self.config.get('compose', {}).get('folder', '<MANTIS>/configs/compose').replace('<MANTIS>', self.config_file_path)
        self.compose_command = self.config.get('compose', {}).get('command', 'docker compose')
        self.key_file = path.normpath(path.join(self.key_path, 'mantis.key'))
        
        # Get environment settings
        self.PROJECT_NAME = self.config.get('project_name', "")

    def check_config(self):
        check_config(self.config)

    def init_environment(self):
        self.env = Environment(
            environment_id=self.environment_id,
            folder=self.environment_path,
        )

        # connection
        self.connection = self.config.get('connections', {}).get(self.env.id, None)

        # containers
        self.CONTAINER_PREFIX = self.PROJECT_NAME
        self.IMAGE_PREFIX = self.PROJECT_NAME

        compose_prefix = f"docker-compose.{self.config.get('compose', {}).get('name', '')}".rstrip('.')
        self.compose_file = os.path.join(self.compose_path, f'{compose_prefix}.{self.env.id}.yml')

    def check_environment_encryption(self, env_file):
        decrypted_environment = self.decrypt_env(env_file=env_file, return_value=True)        # .env.encrypted
        loaded_environment = self.env.load(env_file)                                          # .env

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

    def read_key(self):
        if not os.path.exists(self.key_file):
            CLI.warning(f'File {self.key_file} does not exist. Reading key from $MANTIS_KEY...')
            return os.environ.get('MANTIS_KEY', None)

        with open(self.key_file, "r") as f:
            return f.read()

    def generate_key(self):
        CLI.info(f'Deterministic encryption: ', end='')
        CLI.warning(self.encrypt_deterministically)

        key = Crypto.generate_key(self.encrypt_deterministically)
        CLI.bold('Generated cryptography key: ', end='')
        CLI.pink(key)
        CLI.danger(f'Save it to {self.key_file} and keep safe !!!')

    def encrypt_env(self, params='', env_file=None, return_value=False):
        if env_file is None:
            CLI.info(f'Environment file not specified. Walking all environment files...')

            values = {}

            for env_file in self.env.files:
                value = self.encrypt_env(params=params, env_file=env_file, return_value=return_value)
                if return_value:
                    values.update(value)

            return values if return_value else None

        CLI.info(f'Encrypting environment file {env_file}...')
        env_file_encrypted = f'{env_file}.encrypted'

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

    def decrypt_env(self, params='', env_file=None, return_value=False):
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

    def check_env(self):
        if not hasattr(self.env, 'encrypted_files'):
            CLI.error('No encrypted files')

        # check if pair file exists
        for encrypted_env_file in self.env.encrypted_files:
            env_file = encrypted_env_file.rstrip('.encrypted')
            if not os.path.exists(env_file):
                CLI.warning(f'Environment file {env_file} does not exist')

        if not hasattr(self.env, 'files'):
            CLI.error('No environment files')

        for env_file in self.env.files:
            env_file_encrypted = f'{env_file}.encrypted'

            # check if pair file exists
            if not os.path.exists(env_file_encrypted):
                CLI.warning(f'Environment file {env_file_encrypted} does not exist')
                continue

            # check encryption values
            self.check_environment_encryption(env_file)

    def cmd(self, command):
        command = command.strip()

        error_message = "Error during running command '%s'" % command

        try:
            print(command)
            if os.system(command) != 0:
                CLI.error(error_message)
                # raise Exception(error_message)
        except:
            CLI.error(error_message)
            # raise Exception(error_message)

    def contexts(self):
        self.cmd('docker context ls')

    def create_context(self):
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
            exit()

        endpoint = f'host={host}'

        # CLI.warning(f'Endpoint: {endpoint}')

        description = input("Description: ")
        name = input("Name: ")

        command = f'docker context create \\\n'\
                  f'    --docker {endpoint} \\\n'\
                  f'    --description="{description}" \\\n'\
                  f'    {name}'

        CLI.warning(command)

        if input("Confirm? (Y)es/(N)o: ").lower() != 'y':
            CLI.error('Canceled')
            exit()

        # create context
        self.cmd(command)
        self.contexts()

    def get_container_suffix(self, service):
        delimiter = '-'
        return f'{delimiter}{service}'

    def get_container_name(self, service):
        suffix = self.get_container_suffix(service)
        return f'{self.CONTAINER_PREFIX}{suffix}'.replace('_', '-')

    def get_image_suffix(self, service):
        delimiter = '_'
        return f'{delimiter}{service}'

    def get_image_name(self, service):
        suffix = self.get_image_suffix(service)
        return f'{self.IMAGE_PREFIX}{suffix}'.replace('-', '_')

    def has_healthcheck(self, container):
        healthcheck_config = self.get_healthcheck_config(container)
        return healthcheck_config and healthcheck_config.get('Test')

    def get_healthcheck_start_period(self, container):
        healthcheck_config = self.get_healthcheck_config(container)

        try:
            return healthcheck_config['StartPeriod'] / 1000000000
        except (KeyError, TypeError):
            # TODO: return default value as fallback?
            return None

    def check_health(self, container):
        if self.has_healthcheck(container):
            command = f'inspect --format="{{{{json .State.Health.Status}}}}" {container}'
            status = self.docker(command, return_output=True).strip(' \n"')

            if status == 'healthy':
                return True, status
            else:
                return False, status

    def healthcheck(self, container=None):
        if container not in self.get_containers():
            CLI.error(f"Container {container} not found")

        CLI.info(f'Health-checking {Colors.YELLOW}{container}{Colors.ENDC}...')

        if self.has_healthcheck(container):
            healthcheck_config = self.get_healthcheck_config(container)
            coeficient = 10
            healthcheck_interval = healthcheck_config.get('Interval', 1000000000) / 1000000000
            healthcheck_retries = healthcheck_config.get('Retries', 10)
            interval = healthcheck_interval / coeficient
            retries = healthcheck_retries * coeficient

            CLI.info(f'Interval: {Colors.FAINT}{healthcheck_interval}{Colors.ENDC} s -> {Colors.YELLOW}{interval} s')
            CLI.info(f'Retries: {Colors.FAINT}{healthcheck_retries}{Colors.ENDC} -> {Colors.YELLOW}{retries}')

            start = time.time()

            for retry in range(retries):
                is_healthy, status = self.check_health(container)

                if is_healthy:
                    print(f"#{retry + 1}/{retries}: Status of '{container}' is {Colors.GREEN}{status}{Colors.ENDC}.")
                    end = time.time()
                    loading_time = end - start
                    print(f'Container {Colors.YELLOW}{container}{Colors.ENDC} took {Colors.BLUE}{Colors.UNDERLINE}{loading_time} s{Colors.ENDC} to become healthy')
                    return True
                else:
                    print(f"#{retry + 1}/{retries}: Status of '{container}' is {Colors.RED}{status}{Colors.ENDC}.")

                if retries > 1:
                    sleep(interval)
        else:
            CLI.warning(f"Container '{container}' doesn't have healthcheck command defined. Looking for start period value...")
            start_period = self.get_healthcheck_start_period(container)

            if start_period is None:
                CLI.danger(f"Container '{container}' doesn't have neither healthcheck command or start period defined.")
                CLI.warning(f'Stopping and removing container {container}')
                self.docker(f'container stop {container}')
                self.docker(f'container rm {container}')
                exit()

            # If container doesn't have healthcheck command, sleep for N seconds
            CLI.info(f'Sleeping for {start_period} seconds...')
            sleep(start_period)
            return None

    def build(self, params=''):
        CLI.info(f'Building...')
        CLI.info(f'Params = {params}')

        # Construct build args from config
        build_args = self.config.get('build', {}).get('args', {})
        build_args = ','.join(map('='.join, build_args.items()))

        if build_args != '':
            build_args = build_args.split(',')
            build_args = [f'--build-arg {arg}' for arg in build_args]
            build_args = ' '.join(build_args)

        CLI.info(f'Args = {build_args}')

        build_tool = self.config.get('build', {}).get('tool', 'compose')
        available_tools = ['compose', 'docker']

        if build_tool == 'compose':
            # Build all services using docker compose
            self.docker_compose(f'build {build_args} {params} --pull', use_connection=False)
        elif build_tool == 'docker':
            for service, info in self.services_to_build().items():
                platform = f"--platform={info['platform']}" if info['platform'] != '' else ''
                image = f"-t {info['image']}" if info['image'] != '' else ''

                # build paths for docker build command (paths in compose are relative to compose file, but paths for docker command are relative to $PWD)
                context = normpath(path.join(dirname(self.compose_file), info['context']))
                dockerfile = normpath(path.join(context, info['dockerfile']))

                # Build service using docker
                self.docker(f"build {context} {build_args} {platform} {image} -f {dockerfile} {params}", use_connection=False)
        else:
            CLI.error(f'Unknown build tool: {build_tool}. Available tools: {", ".join(available_tools)}')

    def services(self):
        with open(self.compose_file, 'r') as file:
            compose_data = yaml.safe_load(file)

        return compose_data.get('services', {}).keys()
    
    def services_to_build(self):
        with open(self.compose_file, 'r') as file:
            compose_data = yaml.safe_load(file)

        data = {}

        services = compose_data.get('services', {})
        for service_name, service_config in services.items():
            build = service_config.get('build', None)

            if build:
                data[service_name] = {
                    'dockerfile': build.get('dockerfile', 'Dockerfile'),
                    'context': build.get('context', '.'),
                    'image': service_config.get('image', ''),
                    'platform': service_config.get('platform', '')
                }

        return data

    def push(self, params=''):
        CLI.info(f'Pushing...')
        CLI.info(f'Params = {params}')

        # Push using docker compose
        self.docker_compose(f'push {params}', use_connection=False)

    def pull(self, params=''):
        CLI.info('Pulling...')
        CLI.info(f'Params = {params}')

        # Pull using docker compose
        self.docker_compose(f'pull {params}')

    def upload(self):
        if self.env.id == 'local':
            print('Skipping for local...')
        elif not self.connection:
            CLI.warning('Connection not defined. Skipping uploading files')
        elif self.mode == 'host':
            CLI.warning('Not uploading due to host mode! Be sure your configs on host are up to date!')
        elif self.mode == 'ssh':
            CLI.info('Uploading docker compose configs, environment files and mantis')

            files_to_upload = [self.config_file, self.compose_file] + self.env.files

            # mantis config file
            for file in files_to_upload:
                if os.path.exists(file):
                    self.cmd(f'rsync -arvz -e \'ssh -p {self.port}\' -rvzh --progress {file} {self.user}@{self.host}:{self.project_path}/{file}')
                else:
                    CLI.info(f'{self.config_file} does not exists. Skipping...')

    def restart(self, service=None):
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

    def deploy(self):
        CLI.info('Deploying...')
        self.upload()
        self.pull()

        if len(self.get_containers()) != 0:
            self.zero_downtime()

        self.up()
        self.remove_suffixes()
        self.try_to_reload_webserver()

        self.clean()

    def zero_downtime(self, service=None):
        if not service:
            zero_downtime_services = self.config.get('zero_downtime', [])
            for index, service in enumerate(zero_downtime_services):
                CLI.step(index+1, len(zero_downtime_services), f'Zero downtime services: {zero_downtime_services}')
                self.zero_downtime(service)
            return

        container_prefix = self.get_container_name(service)

        try:
            old_container = self.get_containers(prefix=container_prefix)[0]
        except IndexError:
            CLI.danger(f'Old container for service {service} not found. Skipping zero-downtime deployment...')
            return

        # run new container
        self.up(f'--no-deps --no-recreate --scale {service}=2')

        # healthcheck
        new_containers = self.get_containers(prefix=container_prefix, exclude=[old_container])

        if len(new_containers) != 1:
            CLI.error(f'Expecting single new container. Returned value: {new_containers}')

        new_container = new_containers[0]
        self.healthcheck(container=new_container)

        # reload webserver
        self.try_to_reload_webserver()

        # Stop and remove old container
        CLI.info(f'Stopping old container of service {service}: {old_container}')

        if old_container in self.get_containers():
            CLI.info(f'Stopping old container [{old_container}]...')
            self.docker(f'container stop {old_container}')

            CLI.info(f'Removing old container [{old_container}]...')
            self.docker(f'container rm {old_container}')
        else:
            CLI.info(f'{old_container} was not running')

        # rename new container
        CLI.info(f'Renaming new container [{new_container}]...')
        self.docker(f'container rename {new_container} {container_prefix}')

        # reload webserver
        self.try_to_reload_webserver()

    def remove_suffixes(self, prefix=''):
        for container in self.get_containers(prefix=prefix):
            if container.split('-')[-1].isdigit():
                if container not in self.services():
                    CLI.info(f'Removing suffix of container {container}')
                    new_container = container.rsplit('-', maxsplit=1)[0]
                    self.docker(f'container rename {container} {new_container}')

    def restart_service(self, service):
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
        self.up(f'--no-deps --no-recreate {service}')
        self.remove_suffixes(prefix=container)

    def try_to_reload_webserver(self):
        try:
            self.reload_webserver()
        except AttributeError:
            CLI.warning('Tried to reload webserver, but no suitable extension found!')

    def stop(self, params=None):
        CLI.info('Stopping containers...')

        containers = self.get_containers() if not params else params.split(' ')

        steps = len(containers)

        for index, container in enumerate(containers):
            CLI.step(index + 1, steps, f'Stopping {container}')
            self.docker(f'container stop {container}')

    def kill(self, params=None):
        CLI.info('Killing containers...')

        containers = self.get_containers() if not params else params.split(' ')

        steps = len(containers)

        for index, container in enumerate(containers):
            CLI.step(index + 1, steps, f'Killing {container}')
            self.docker(f'container kill {container}')

    def start(self, params=''):
        CLI.info('Starting containers...')

        containers = self.get_containers() if not params else params.split(' ')

        steps = len(containers)

        for index, container in enumerate(containers):
            CLI.step(index + 1, steps, f'Starting {container}')
            self.docker(f'container start {container}')

    def run(self, params):
        CLI.info(f'Running {params}...')
        self.docker_compose(f'run {params}')

    def up(self, params=''):
        CLI.info(f'Starting up {params}...')
        self.docker_compose(f'up {params} -d')

    def down(self, params=''):
        CLI.info(f'Running down {params}...')
        self.docker_compose(f'down {params}')

    def remove(self, params=''):
        CLI.info('Removing containers...')

        containers = self.get_containers() if params == '' else params.split(' ')

        steps = len(containers)

        for index, container in enumerate(containers):
            CLI.step(index + 1, steps, f'Removing {container}')
            self.docker(f'container rm {container}')

    def clean(self, params=''):  # todo clean on all nodes
        CLI.info('Cleaning...')
        # self.docker(f'builder prune')
        self.docker(f'system prune {params} -a --force')
        # self.docker(f'container prune')
        # self.docker(f'container prune --force')

    def status(self):
        CLI.info('Getting status...')
        steps = 2

        CLI.step(1, steps, 'List of Docker images')
        self.docker(f'image ls')

        CLI.step(2, steps, 'Docker containers')
        self.docker(f'container ls -a --size')

    def networks(self):
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
                containers = self.docker(f'network inspect -f \'{{{{ range $key, $value := .Containers }}}}{{{{ .Name }}}} {{{{ end }}}}\' {network_name}', return_output=True)
                containers = ', '.join(containers.split())
                print(f'{network}\t{containers}'.strip())

    def logs(self, params=None):
        CLI.info('Reading logs...')

        containers = params.split(' ') if params else self.get_containers()
        lines = '--tail 1000 -f' if params else '--tail 10'
        steps = len(containers)

        for index, container in enumerate(containers):
            CLI.step(index + 1, steps, f'{container} logs')
            self.docker(f'logs {container} {lines}')

    def bash(self, params):
        CLI.info('Running bash...')
        self.docker(f'exec -it --user root {params} /bin/bash')
        # self.docker_compose(f'run --entrypoint /bin/bash {container}')

    def sh(self, params):
        CLI.info('Logging to container...')
        self.docker(f'exec -it --user root {params} /bin/sh')

    def exec(self, params):
        container, command = params.split(' ', maxsplit=1)
        CLI.info(f'Executing command "{command}" in container {container}...')
        self.docker(f'exec -it {container} {command}')

    def get_containers(self, prefix='', exclude=[]):
        containers = self.docker(f'container ls -a --format \'{{{{.Names}}}}\'', return_output=True)\
            .strip('\n').strip().split('\n')

        # Remove empty strings
        containers = list(filter(None, containers))

        # get project containers only
        containers = list(filter(lambda c: self.get_container_project(c) == self.PROJECT_NAME, containers))

        # find containers starting with custom prefix
        containers = list(filter(lambda s: s.startswith(prefix), containers))

        # exclude not matching containers
        containers = list(filter(lambda s: s not in exclude, containers))

        return containers

    def get_container_project(self, container):
        try:
            container_details = json.loads(self.docker(f'container inspect {container}', return_output=True))
            return container_details[0]["Config"]["Labels"]["com.docker.compose.project"]
        except (IndexError, KeyError):
            pass

        return None

    def get_healthcheck_config(self, container):
        try:
            container_details = json.loads(self.docker(f'container inspect {container}', return_output=True))
            return container_details[0]["Config"]["Healthcheck"]
        except (IndexError, KeyError):
            pass

        return None

    def docker(self, command, return_output=False, use_connection=True):
        docker_connection = self.docker_connection if use_connection else ''

        if return_output:
            return os.popen(f'{docker_connection} docker {command}').read()

        self.cmd(f'{docker_connection} docker {command}')

    def docker_compose(self, command, use_connection=True):
        docker_connection = self.docker_connection if use_connection else ''
        self.cmd(f'{docker_connection} {self.compose_command} -f {self.compose_file} --project-name={self.PROJECT_NAME} {command}')
