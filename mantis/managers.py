import json
import os
import time
import yaml
from collections import defaultdict
from datetime import datetime
from os import path
from os.path import normpath
from time import sleep

from mantis.crypto import Crypto
from mantis.environment import Environment
from mantis.helpers import CLI, Colors, merge_json
from mantis.logic import find_config, load_config, check_config, load_template_config


class AbstractManager(object):
    """
    Abstract manager contains methods which should not be available to call using CLI
    """
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
        self.encrypt_deterministically = self.config['encryption']['deterministic']

    @property
    def host(self):
        return self.connection_details['host'] if self.connection_details else None

    @property
    def user(self):
        return self.connection_details['user'] if self.connection_details else None

    @property
    def port(self):
        return self.connection_details['port'] if self.connection_details else None

    def parse_ssh_connection(self, connection):
        return {
            'host': connection.split("@")[1].split(':')[0],
            'user': connection.split("@")[0].split('://')[1],
            'port': connection.split(":")[-1]
        }

    @property
    def connection_details(self):
        if self.env.id is None:
            return None

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
        self.project_path = self.config['project_path']

        return details

    @property
    def docker_connection(self):
        if self.env.id is None or 'local' in self.env.id:
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
        check_config(config)
        config_file_path = path.normpath(path.join(self.config_file, os.pardir))

        def normalize(path):
            return os.path.normpath(path.replace('<MANTIS>', config_file_path))

        # Load config template file
        defaults = load_template_config()

        # Merge custom config and default values
        defaults.update(config)

        # Save merged config to variable
        self.config = defaults.copy()

        self.key_file = normalize(path.join(self.config['encryption']['folder'], 'mantis.key'))
        self.environment_path = normalize(self.config['environment']['folder'])
        self.compose_path = normalize(path.join(self.config['compose']['folder'], self.environment_id))

    def init_environment(self):
        self.env = Environment(
            environment_id=self.environment_id,
            folder=self.environment_path,
        )

        # connection
        self.connection = self.config['connections'].get(self.env.id, None)

        # compose files
        compose_file_paths = os.popen(f'find {self.compose_path} -name "*.yml" -o -name "*.yaml"').read().strip().split('\n')

        # Remove empty strings
        self.compose_files = list(filter(None, compose_file_paths))

        # Read compose files
        self.compose_config = self.read_compose_configs()

    def check_environment_encryption(self, env_file):
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

    def docker_command(self, command, return_output=False, use_connection=True):
        docker_connection = self.docker_connection if use_connection else ''

        cmd = f'{docker_connection} {command}'

        if return_output:
            return os.popen(cmd).read()

        self.cmd(cmd)

    def docker(self, command, return_output=False, use_connection=True):
        return self.docker_command(
            command=f'docker {command}',
            return_output=return_output,
            use_connection=use_connection
        )

    def docker_compose(self, command, return_output=False, use_connection=True):
        compose_command = self.config['compose']['command']

        compose_files = ' '.join([f'-f {compose_file}' for compose_file in self.compose_files])

        return self.docker_command(
            command=f'{compose_command} {compose_files} {command}',
            return_output=return_output,
            use_connection=use_connection
        )

    def get_container_project(self, container):
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

    def get_containers(self, prefix='', exclude=[], only_running=False):
        """
        Prints all project containers
        :param prefix: container prefix
        :param exclude: exclude containers
        :return: list of container names
        """
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

    def check_config(self):
        """
        Validates config file according to template
        """
        check_config(self.config)

    def read_key(self):
        """
        Returns value of mantis encryption key
        """
        if not os.path.exists(self.key_file):
            CLI.warning(f'File {self.key_file} does not exist. Reading key from $MANTIS_KEY...')
            return os.environ.get('MANTIS_KEY', None)

        with open(self.key_file, "r") as f:
            return f.read().strip()

    def generate_key(self):
        """
        Creates new encryption key
        """
        CLI.info(f'Deterministic encryption: ', end='')
        CLI.warning(self.encrypt_deterministically)

        key = Crypto.generate_key(self.encrypt_deterministically)
        CLI.bold('Generated cryptography key: ', end='')
        CLI.pink(key)
        CLI.danger(f'Save it to {self.key_file} and keep safe !!!')

    def encrypt_env(self, params='', env_file=None, return_value=False):
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
        """
        Compares encrypted and decrypted env files
        """
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

    def contexts(self):
        """
        Prints all docker contexts
        """
        self.cmd('docker context ls')

    def create_context(self):
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
            exit()

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
            exit()

        # create context
        self.cmd(command)
        self.contexts()

    def get_container_suffix(self, service):
        """
        Returns the suffix used for containers for given service
        """
        delimiter = '-'
        return f'{delimiter}{service}'

    def get_container_name(self, service):
        """
        Constructs container name with project prefix for given service
        """
        suffix = self.get_container_suffix(service)
        prefix = self.get_project_by_service(service)
        return f'{prefix}{suffix}'.replace('_', '-')

    def get_service_containers(self, service):
        """
        Prints container names of given service
        """
        containers = self.docker_compose("ps --format '{{.Names}}' %s" % service, return_output=True)
        return containers.strip().split('\n')

    def get_number_of_containers(self, service):
        """
        Prints number of containers for given service
        """
        return len(self.get_service_containers(service))

    def get_image_suffix(self, service):
        """
        Returns the suffix used for image for given service
        """
        delimiter = '_'
        return f'{delimiter}{service}'

    def get_image_name(self, service):
        """
        Constructs image name for given service
        """
        suffix = self.get_image_suffix(service)
        prefix = self.get_project_by_service(service)
        return f'{prefix}{suffix}'.replace('-', '_')

    def has_healthcheck(self, container):
        """
        Checks if given container has defined healthcheck
        """
        healthcheck_config = self.get_healthcheck_config(container)

        return healthcheck_config and healthcheck_config.get('Test') != ['NONE']

    def get_healthcheck_start_period(self, container):
        """
        Returns healthcheck start period for given container (if any)
        """
        healthcheck_config = self.get_healthcheck_config(container)

        try:
            return healthcheck_config['StartPeriod'] / 1000000000
        except (KeyError, TypeError):
            # TODO: return default value as fallback?
            return None

    def check_health(self, container):
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

    def healthcheck(self, container=None):
        """
        Execute health-check of given project container
        """
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
        """
        Builds all services with Dockerfiles
        """
        CLI.info(f'Building...')
        CLI.info(f'Params = {params}')

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
            for service, info in self.services_to_build().items():
                platform = f"--platform={info['platform']}" if info['platform'] != '' else ''
                cache_from = ' '.join([f"--cache-from {cache}" for cache in info['cache_from']]) if info['cache_from'] != [] else ''
                args = ' '.join([f"--build-arg {key}={value}" for key, value in info['args'].items()]) if info['args'] != {} else ''
                image = info['image'] if info['image'] != '' else f"{info['project_name']}-{service}".lstrip('-')

                # build paths for docker build command (paths in compose are relative to compose file, but paths for docker command are relative to $PWD)
                context = normpath(path.join(self.compose_path, info['context']))
                dockerfile = normpath(path.join(context, info['dockerfile']))

                # Build service using docker
                self.docker(f"build {context} {build_args} {args} {platform} {cache_from} -t {image} -f {dockerfile} {params}",
                            use_connection=False)
        else:
            CLI.error(f'Unknown build tool: {build_tool}. Available tools: {", ".join(available_tools)}')

    def project_services(self):
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

    def get_project_by_service(self, service):
        project_services = self.project_services()

        for project, services in project_services.items():
            if service in services:
                return project

        return None

    def services(self, compose_file=None):
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

    def services_to_build(self, compose_file=None):
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

    def push(self, params=''):
        """
        Push built images to repository
        """
        CLI.info(f'Pushing...')
        CLI.info(f'Params = {params}')

        # Push using docker compose
        self.docker_compose(f'push {params}', use_connection=False)

    def pull(self, params=''):
        """
        Pulls required images for services
        """
        CLI.info('Pulling...')
        CLI.info(f'Params = {params}')

        # Pull using docker compose
        self.docker_compose(f'pull {params}')

    def upload(self):
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
                if os.path.exists(file):
                    self.cmd(f'rsync -arvz -e \'ssh -p {self.port}\' -rvzh --progress {file} {self.user}@{self.host}:{self.project_path}/{file}')
                else:
                    CLI.info(f'{self.config_file} does not exists. Skipping...')

    def restart(self, service=None):
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

    def deploy(self, dirty=False):
        """
        Runs deployment process: uploads files, pulls images, runs zero-downtime deployment, removes suffixes, reloads webserver, clean
        """
        CLI.info('Deploying...')

        if dirty:
            CLI.warning('...but dirty (no zero-downtime, without cleaning)') 

        self.upload()
        self.pull()

        is_running = len(self.get_containers(only_running=True)) != 0

        if is_running and not dirty:
            self.zero_downtime()

        # Preserve number of scaled containers
        scale_param = ''
        if is_running:
            scales = {}
            for service in self.services():
                replicas = self.get_deploy_replicas(service)
                number_of_containers = self.get_number_of_containers(service)

                # ensure the number of containers is at least as default number of replicas
                if number_of_containers > replicas:
                    scales[service] = number_of_containers

            scale_param = ' '.join([f'--scale {service}={scale}' for service, scale in scales.items()])

        self.up(scale_param)
        self.remove_suffixes()
        self.try_to_reload_webserver()

        if not dirty:
            self.clean()

    def zero_downtime(self, service=None):
        """
        Runs zero-downtime deployment of services (or given service)
        """
        if not service:
            zero_downtime_services = self.config['zero_downtime']
            for index, service in enumerate(zero_downtime_services):
                CLI.step(index + 1, len(zero_downtime_services), f'Zero downtime services: {zero_downtime_services}')
                self.zero_downtime(service)
            return

        container_prefix = self.get_container_name(service)

        old_containers = self.get_containers(prefix=container_prefix, only_running=True)
        num_containers = len(old_containers)

        if num_containers == 0:
            CLI.danger(f'Old container for service {service} not found. Skipping zero-downtime deployment...')
            return

        # run new containers
        scale = num_containers * 2
        self.scale(service, scale)

        # healthcheck
        new_containers = self.get_containers(prefix=container_prefix, exclude=old_containers, only_running=True)

        for new_container in new_containers:
            self.healthcheck(container=new_container)

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

    def remove_suffixes(self, prefix=''):
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

    def restart_service(self, service):
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
        self.up(f'--no-deps --no-recreate {service}')
        self.remove_suffixes(prefix=container)

    def try_to_reload_webserver(self):
        """
        Tries to reload webserver (if suitable extension is available)
        """
        try:
            self.reload_webserver()
        except AttributeError:
            CLI.warning('Tried to reload webserver, but no suitable extension found!')

    def stop(self, params=None):
        """
        Stops all or given project container
        """
        CLI.info('Stopping containers...')

        containers = self.get_containers() if not params else params.split(' ')

        steps = len(containers)

        for index, container in enumerate(containers):
            CLI.step(index + 1, steps, f'Stopping {container}')
            self.docker(f'container stop {container}')

    def kill(self, params=None):
        """
        Kills all or given project container
        """
        CLI.info('Killing containers...')

        containers = self.get_containers() if not params else params.split(' ')

        steps = len(containers)

        for index, container in enumerate(containers):
            CLI.step(index + 1, steps, f'Killing {container}')
            self.docker(f'container kill {container}')

    def start(self, params=''):
        """
        Starts all or given project container
        """
        CLI.info('Starting containers...')

        containers = self.get_containers() if not params else params.split(' ')

        steps = len(containers)

        for index, container in enumerate(containers):
            CLI.step(index + 1, steps, f'Starting {container}')
            self.docker(f'container start {container}')

    def run(self, params):
        """
        Calls compose run with params
        """
        CLI.info(f'Running {params}...')
        self.docker_compose(f'run {params}')

    def up(self, params=''):
        """
        Calls compose up (with optional params)
        """
        CLI.info(f'Starting up {params}...')
        self.docker_compose(f'up {params} -d')

    def down(self, params=''):
        """
        Calls compose down (with optional params)
        """
        CLI.info(f'Running down {params}...')
        self.docker_compose(f'down {params}')

    def scale(self, service, scale):
        """
        Scales service to given scale
        """
        self.up(f'--no-deps --no-recreate --scale {service}={scale}')

    def remove(self, params=''):
        """
        Removes all or given project container
        """
        CLI.info('Removing containers...')

        containers = self.get_containers() if params == '' else params.split(' ')

        steps = len(containers)

        for index, container in enumerate(containers):
            CLI.step(index + 1, steps, f'Removing {container}')
            self.docker(f'container rm {container}')

    def clean(self, params=''):  # todo clean on all nodes
        """
        Clean images, containers, networks
        """
        CLI.info('Cleaning...')
        # self.docker(f'builder prune')
        self.docker(f'system prune {params} -a --force')
        # self.docker(f'container prune')
        # self.docker(f'container prune --force')

    def status(self):
        """
        Prints images and containers
        """
        CLI.info('Getting status...')
        steps = 2

        CLI.step(1, steps, 'List of Docker images')
        self.docker(f'image ls')

        CLI.step(2, steps, 'Docker containers')
        self.docker(f'container ls -a --size')

    def networks(self):
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

    def logs(self, params=None):
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

    def bash(self, params):
        """
        Runs bash in container
        """
        CLI.info('Running bash...')
        self.docker(f'exec -it --user root {params} /bin/bash')
        # self.docker_compose(f'run --entrypoint /bin/bash {container}')

    def sh(self, params):
        """
        Runs sh in container
        """
        CLI.info('Logging to container...')
        self.docker(f'exec -it --user root {params} /bin/sh')

    def ssh(self):
        if not self.connection:
            CLI.error('Missing connection details')

        if not self.host:
            CLI.error('Unknown host')

        CLI.info(f'Executing SSH connection: {self.connection}')
        os.system(f'ssh {self.user}@{self.host} -p {self.port or 22}')

    def exec(self, params):
        """
        Executes command in container
        """
        container, command = params.split(' ', maxsplit=1)
        CLI.info(f'Executing command "{command}" in container {container}...')
        self.docker(f'exec -it {container} {command}')

    def get_healthcheck_config(self, container):
        """
        Prints health-check config (if any) of given container
        """
        try:
            container_details = json.loads(self.docker(f'container inspect {container}', return_output=True))
            return container_details[0]["Config"]["Healthcheck"]
        except (IndexError, KeyError):
            pass

        return None

    def read_compose_configs(self):
        """
        Returns merged compose configs
        """
        config = {}

        for compose_file in self.compose_files:
            with open(compose_file, 'r') as file:
                compose_data = yaml.safe_load(file)
                config = merge_json(config, compose_data)

        return config

    def get_deploy_replicas(self, service):
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

    def backup_volume(self, volume):
        # backups folder
        backup_path = os.getcwd() + '/backups/'

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

    def restore_volume(self, volume, file):
        # backups folder
        backup_path = os.getcwd() + '/backups/'

        command = f'run --rm \
        -v {volume}:/{volume} \
        -v "{backup_path}":/backup \
        busybox \
        tar -xzvf /backup/{file}'

        self.docker(command)
