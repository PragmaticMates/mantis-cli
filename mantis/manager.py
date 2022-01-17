import json
import os
import datetime
from distutils.util import strtobool
from os.path import dirname
from time import sleep

from mantis.helpers import CLI, Crypto


class Mantis(object):
    environment_id = None

    def __init__(self, config=None, environment_id=None, mode='remote'):
        self.environment_id = environment_id
        self.mode = mode
        self.init_config(config)
        self.KEY = self.read_key()
        self.encrypt_deterministically = self.config.get('encrypt_deterministically', False)
        if self.KEY:
            self.check_environment_encryption()

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

        if 'dev' in self.environment_id:
            details = {
                'host': 'localhost',
                'user': None,
                'port': None
            }
        else:
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

        return details

    @property
    def docker_connection(self):
        if 'dev' in self.environment_id:
            return ''

        if self.mode == 'remote':
            if self.connection.startswith('ssh://'):
                return f'DOCKER_HOST="{self.connection}"'
            elif self.connection.startswith('context://'):
                context_name = self.connection.replace('context://', '')
                return f'DOCKER_CONTEXT={context_name}'

        return ''

    def init_config(self, config):
        self.config_file = os.environ.get('MANTIS_CONFIG', 'configs/mantis.json')
        self.config = config or self.load_config()

        configs_folder_path = self.config.get('configs_folder_path', '')
        configs_folder_name = self.config.get('configs_folder_name', 'configs')
        self.configs_path = f'{configs_folder_path}{configs_folder_name}'
        self.key_file = f'{dirname(self.config_file)}/mantis.key'
        self.environment_file_prefix = self.config.get('environment_file_prefix', '')
        self.environment_file = f'{self.configs_path}/environments/{self.environment_file_prefix}{self.environment_id}.env'
        self.environment_file_encrypted = f'{self.configs_path}/environments/{self.environment_file_prefix}{self.environment_id}.env.encrypted'
        self.project_path = self.config.get('project_path', None)
        self.connection = self.config.get('connections', {}).get(self.environment_id, None)

        # Get environment settings
        self.PROJECT_NAME = self.config['project_name']
        self.IMAGE_NAME = self.config['build']['image']
        self.DOCKER_FILE = self.config['build']['file']

        if 'containers' in self.config:
            self.CONTAINER_PREFIX = self.config['containers']['prefix']
            self.CONTAINER_SUFFIX_DB = self.config['containers']['suffixes']['db']
            self.CONTAINER_SUFFIX_CACHE = self.config['containers']['suffixes']['cache']
            self.CONTAINER_SUFFIX_APP = self.config['containers']['suffixes']['app']
            self.CONTAINER_SUFFIX_QUEUE = self.config['containers']['suffixes']['queue']
            self.CONTAINER_SUFFIX_WEBSERVER = self.config['containers']['suffixes']['webserver']
            self.CONTAINER_APP = f'{self.CONTAINER_PREFIX}{self.CONTAINER_SUFFIX_APP}'
            self.CONTAINER_QUEUE = f'{self.CONTAINER_PREFIX}{self.CONTAINER_SUFFIX_QUEUE}'
            self.CONTAINER_DB = f'{self.CONTAINER_PREFIX}{self.CONTAINER_SUFFIX_DB}'
            self.CONTAINER_CACHE = f'{self.CONTAINER_PREFIX}{self.CONTAINER_SUFFIX_CACHE}'
            self.CONTAINER_WEBSERVER = f'{self.CONTAINER_PREFIX}{self.CONTAINER_SUFFIX_WEBSERVER}'
            self.SWARM = self.config.get('swarm', False)
            self.SWARM_STACK = self.config.get(f'swarm_stack', self.CONTAINER_PREFIX)  # project name?
            self.compose_name = self.config['compose']['name']
            self.COMPOSE_PREFIX = 'docker-compose' if self.compose_name == '' else f'docker-compose.{self.compose_name}'
            self.compose_configs = [
                f'{self.configs_path}/docker/{self.COMPOSE_PREFIX}.yml',
                f'{self.configs_path}/docker/{self.COMPOSE_PREFIX}.proxy.yml'
                f'{self.configs_path}/docker/{self.COMPOSE_PREFIX}.{self.environment_id}.yml',
            ]

        self.DATABASE = self.config.get('cache', 'postgres')
        self.CACHE = self.config.get('cache', 'redis')
        self.WEBSERVER = self.config.get('webserver', 'nginx')
        self.database_config = f'{self.configs_path}/{self.DATABASE}/{self.environment_file_prefix}{self.environment_id}.conf'
        self.cache_config = f'{self.configs_path}/{self.CACHE}/{self.environment_file_prefix}{self.environment_id}.conf'
        self.webserver_config = f'{self.configs_path}/{self.WEBSERVER}/{self.environment_file_prefix}{self.environment_id}.conf'
        self.webserver_config_proxy = f'configs/{self.WEBSERVER}/proxy_directives.conf'
        self.htpasswd = f'secrets/.htpasswd'

    def check_environment_encryption(self):
        decrypted_env = self.decrypt_env(return_value=True)
        decrypted_env_from_file = self.load_environment(self.environment_file)

        if decrypted_env_from_file != decrypted_env:
            CLI.danger('Encrypted and decrypted environments do NOT match!')

            if decrypted_env_from_file is None:
                CLI.danger('Decrypted env from file is empty !')
            elif decrypted_env is None:
                CLI.danger('Decrypted env is empty !')
            else:
                set1 = set(decrypted_env_from_file.items())
                set2 = set(decrypted_env.items())
                CLI.danger(set1 ^ set2)
        else:
            CLI.success('Encrypted and decrypted environments DO match...')

    def read_key(self):
        if not os.path.exists(self.key_file):
            return None

        with open(self.key_file, "r") as f:
            return f.read()

    def generate_key(self):
        CLI.info(f'Deterministic encryption: ', end='')
        CLI.warning(self.encrypt_deterministically)

        key = Crypto.generate_key(self.encrypt_deterministically)
        CLI.bold('Generated cryptography key: ', end='')
        CLI.pink(key)
        CLI.danger(f'Save it to {self.key_file} and keep safe !!!')

    def encrypt_env(self, return_value=False):
        CLI.info(f'Encrypting environment file {self.environment_file}...')

        if not self.KEY:
            CLI.error('Missing mantis key!')

        decrypted_env = self.load_environment(self.environment_file)

        if not decrypted_env:
            return None

        encrypted_env = {}

        for var, value in decrypted_env.items():
            encrypted_value = Crypto.encrypt(value, self.KEY, self.encrypt_deterministically)

            if not return_value:
                print(f'{var}={encrypted_value}')

            encrypted_env[var] = encrypted_value

        if return_value:
            return encrypted_env

        # save to file?
        CLI.info(f'Save to file?')

        save_to_file = input("(Y)es or (N)o: ")

        if save_to_file.lower() == 'y':
            with open(self.environment_file_encrypted, "w") as f:
                for index, (var, encrypted_value) in enumerate(encrypted_env.items()):
                    f.write(f'{var}={encrypted_value}')

                    if index < len(encrypted_env) - 1:
                        f.write('\n')

            CLI.success(f'Saved to file {self.environment_file_encrypted}')
        else:
            CLI.warning(f'Save it to {self.environment_file_encrypted} manually.')

    def decrypt_env(self, return_value=False):
        if not return_value:
            CLI.info(f'Decrypting environment file {self.environment_file_encrypted}...')

        if not self.KEY:
            CLI.error('Missing mantis key!')

        encrypted_env = self.load_environment(self.environment_file_encrypted)

        if not encrypted_env:
            return None

        decrypted_env = {}

        for var, value in encrypted_env.items():
            decrypted_value = Crypto.decrypt(value, self.KEY, self.encrypt_deterministically)

            if not return_value:
                print(f'{var}={decrypted_value}')

            decrypted_env[var] = decrypted_value

        if return_value:
            return decrypted_env

        # save to file?
        CLI.info(f'Save to file?')

        save_to_file = input("(Y)es or (N)o: ")

        if save_to_file.lower() == 'y':
            with open(self.environment_file, "w") as f:
                for index, (var, decrypted_value) in enumerate(decrypted_env.items()):
                    f.write(f'{var}={decrypted_value}')

                    if index < len(encrypted_env) - 1:
                        f.write('\n')

            CLI.success(f'Saved to file {self.environment_file}')
        else:
            CLI.warning(f'Save it to {self.environment_file} manually.')

    def load_config(self):
        with open(self.config_file) as config:
            return json.load(config)

    def load_environment(self, path):
        if not os.path.exists(path):
            return None

        with open(path) as fh:
            return dict(
                (line.split('=', maxsplit=1)[0], line.split('=', maxsplit=1)[1].rstrip("\n"))
                for line in fh.readlines() if not line.startswith('#')
            )

    def contexts(self):
        os.system('docker context ls')

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
        os.system(command)
        self.contexts()

    def get_container_name(self, service):
        suffix = self.config['containers']['suffixes'].get(service, f'_{service}')
        return f'{self.CONTAINER_PREFIX}{suffix}'

    def build(self, params=''):
        CLI.info(f'Building...')
        CLI.info(f'Params = {params}')
        CLI.info(f'Dockerfile = {self.configs_path}/docker/{self.DOCKER_FILE}')
        steps = 1

        CLI.step(1, steps, 'Building Docker image...')

        build_args = self.config['build']['args']
        build_args = ','.join(map('='.join, build_args.items()))
        build_kit = self.config['build']['kit']
        build_kit = 'DOCKER_BUILDKIT=1' if build_kit else ''

        if build_args != '':
            build_args = build_args.split(',')
            build_args = [f'--build-arg {arg}' for arg in build_args]
            build_args = ' '.join(build_args)

        CLI.info(f'Kit = {build_kit}')
        CLI.info(f'Args = {build_args}')

        os.system(f'time {build_kit} docker build . {build_args} -t {self.IMAGE_NAME} -f {self.configs_path}/docker/{self.DOCKER_FILE} {params}')

    def push(self):
        CLI.info(f'Pushing...')

        DOCKER_REPOSITORY = self.config['build']['repository']
        DOCKER_TAG = self.config['build']['tag']

        steps = 2
        CLI.step(1, steps, 'Tagging Docker image...')
        os.system(f'docker tag {self.IMAGE_NAME} {DOCKER_REPOSITORY}:{DOCKER_TAG}')
        print(f'Successfully tagged {DOCKER_REPOSITORY}:{DOCKER_TAG}')

        CLI.step(2, steps, 'Pushing Docker image...')
        os.system(f'docker push {DOCKER_REPOSITORY}:{DOCKER_TAG}')

    def pull(self):
        CLI.info('Pulling docker image...')
        self.docker_compose('pull')

    def upload(self, context='services'):
        CLI.info('Uploading...')
        steps = 1

        if context == 'services':
            CLI.step(1, steps, 'Uploading configs for context "services" [webserver, database, cache, htpasswd]')
        elif context == 'compose':
            CLI.step(1, steps, 'Uploading configs for context "compose" [docker compose configs and environment]')
        elif context == 'mantis':
            CLI.step(1, steps, 'Uploading configs for mantis [mantis.json]')
        else:
            CLI.error(f'Unknown context "{context}". Available: services, compose, mantis')

        if self.environment_id == 'dev':
            print('Skipping for dev...')
        elif self.mode == 'host':
            CLI.warning('Not uploading due to host mode! Be sure your configs on host are up to date!')
        else:
            if context == 'services':
                os.system(f'rsync -arvz -e \'ssh -p {self.port}\' -rvzh --progress {self.database_config} {self.user}@{self.host}:/home/{self.user}/public_html/web/configs/{self.DATABASE}/')
                os.system(f'rsync -arvz -e \'ssh -p {self.port}\' -rvzh --progress {self.cache_config} {self.user}@{self.host}:/home/{self.user}/public_html/web/configs/{self.CACHE}/')
                os.system(f'rsync -arvz -e \'ssh -p {self.port}\' -rvzh --progress {self.webserver_config} {self.user}@{self.host}:/home/{self.user}/public_html/web/configs/{self.WEBSERVER}/')
                os.system(f'rsync -arvz -e \'ssh -p {self.port}\' -rvzh --progress {self.webserver_config_proxy} {self.user}@{self.host}:/etc/nginx/conf.d/proxy/')
                os.system(f'rsync -arvz -e \'ssh -p {self.port}\' -rvzh --progress {self.htpasswd} {self.user}@{self.host}:/etc/nginx/conf.d/')

            elif context == 'mantis':
                os.system(f'rsync -arvz -e \'ssh -p {self.port}\' -rvzh --progress {self.config_file} {self.user}@{self.host}:/home/{self.user}/public_html/web/configs/')

            elif context == 'compose':
                os.system(f'rsync -arvz -e \'ssh -p {self.port}\' -rvzh --progress {self.environment_file} {self.user}@{self.host}:/home/{self.user}/public_html/web/configs/environments/')

                for config in self.compose_configs:
                    os.system(f'rsync -arvz -e \'ssh -p {self.port}\' -rvzh --progress {config} {self.user}@{self.host}:/home/{self.user}/public_html/web/configs/docker/')

    def restart(self):
        CLI.info('Restarting...')
        steps = 3

        if self.SWARM:
            CLI.step(1, steps, 'Stopping and removing Docker app service...')

            for service in self.get_services():
                if service == self.CONTAINER_APP:
                    os.system(f'docker service rm {service}')

            CLI.step(2, steps, 'Recreating Docker swarm stack...')
            os.system(f'docker stack deploy -c configs/docker/{self.COMPOSE_PREFIX}.yml -c configs/docker/{self.COMPOSE_PREFIX}.{self.environment_id}.yml {self.PROJECT_NAME}')

            CLI.step(3, steps, 'Prune Docker images and volumes')  # todo prune on every node
            self.docker(f'system prune --volumes --force')
        else:
            CLI.step(1, steps, 'Stopping and removing Docker containers...')

            for service in self.config['containers']['deploy']['zero_downtime'] + self.config['containers']['deploy']['restart']:
                container = self.get_container_name(service)
                self.docker(f'container stop {container}', return_output=True)
                self.docker(f'container rm {container}')

            CLI.step(2, steps, 'Recreating Docker containers...')
            self.docker_compose(f'--project-name={self.PROJECT_NAME} up -d')

            CLI.step(3, steps, 'Prune Docker images and volumes')
            self.docker(f'system prune --volumes --force')

    def deploy(self):
        CLI.info('Deploying...')
        self.clean()
        self.upload()
        self.pull()
        self.reload()

    def reload(self):  # todo deploy swarm
        CLI.info('Reloading containers...')
        zero_downtime_services = self.config['containers']['deploy']['zero_downtime']
        restart_services = self.config['containers']['deploy']['restart']

        steps = 4

        step = 1
        CLI.step(step, steps, f'Zero downtime services: {zero_downtime_services}')

        for service in zero_downtime_services:
            container = self.get_container_name(service)
            self.docker_compose(f'--project-name={self.PROJECT_NAME} run -d --service-ports --name={container}_new {service}')
            CLI.info(f'Renaming old container [{container}_old]...')

            if container in self.get_containers():
                self.docker(f'container rename {container} {container}_old')
            else:
                CLI.info(f'{container}_old was not running')

            CLI.info(f'Renaming new container [{container}]...')
            self.docker(f'container rename {container}_new {container}')

        step += 1
        CLI.step(step, steps, 'Reloading webserver...')
        self.docker(f'exec -it {self.CONTAINER_WEBSERVER} {self.WEBSERVER} -s reload')

        step += 1
        CLI.step(step, steps, f'Stopping old zero downtime services: {zero_downtime_services}')

        for service in zero_downtime_services:
            container = self.get_container_name(service)

            if container in self.get_containers():
                CLI.info(f'Stopping old container [{container}_old]...')
                self.docker(f'container stop {container}_old')

                CLI.info(f'Removing old container [{container}_old]...')
                self.docker(f'container rm {container}_old')
            else:
                CLI.info(f'{container}_old was not running')

        step += 1
        CLI.step(step, steps, f'Restart services: {restart_services}')

        for service in restart_services:
            container = self.get_container_name(service)

            CLI.underline(f'Recreating {service} container ({container})...')

            if container in self.get_containers():
                CLI.info(f'Stopping container [{container}]...')
                self.docker(f'container stop {container}')

                CLI.info(f'Removing container [{container}]...')
                self.docker(f'container rm {container}')

                CLI.info(f'Creating new container [{container}]...')
                self.docker_compose(f'--project-name={self.PROJECT_NAME} run -d --service-ports --name={container} {service}')
            else:
                CLI.info(f'{container} was not running')

    def stop(self, params=None):
        if self.SWARM:  # todo can stop service ?
            CLI.info('Removing services...')
            os.system(f'docker stack rm {self.PROJECT_NAME}')

        else:
            CLI.info('Stopping containers...')

            containers = self.get_containers() if not params else params.split(' ')

            steps = len(containers)

            for index, container in enumerate(containers):
                CLI.step(index + 1, steps, f'Stopping {container}')
                self.docker(f'container stop {container}')

    def start(self, params=''):
        if self.SWARM:
            CLI.info('Starting services...')
            os.system(f'docker stack deploy -c configs/docker/{self.COMPOSE_PREFIX}.yml -c configs/docker/{self.COMPOSE_PREFIX}.{self.environment_id}.yml {self.PROJECT_NAME}')

        else:
            CLI.info('Starting containers...')

            containers = self.get_containers() if not params else params.split(' ')

            steps = len(containers)

            for index, container in enumerate(containers):
                CLI.step(index + 1, steps, f'Starting {container}')
                self.docker(f'container start {container}')

    def run(self, params):
        CLI.info('Run...')
        steps = 1

        CLI.step(1, steps, f'Running {params}...')
        self.docker_compose(f'--project-name={self.PROJECT_NAME} run {params}')

    def up(self, params):
        CLI.info('Up...')
        steps = 1

        CLI.step(1, steps, f'Upping {params}...')
        self.docker_compose(f'--project-name={self.PROJECT_NAME} up {params}')

    def remove(self, params=''):
        if self.SWARM:  # todo remove containers as well ?
            CLI.info('Removing services...')
            os.system(f'docker stack rm {self.PROJECT_NAME}')

        else:
            CLI.info('Removing containers...')

            containers = self.get_containers() if params == '' else params.split(' ')

            steps = len(containers)

            for index, container in enumerate(containers):
                CLI.step(index + 1, steps, f'Removing {container}')
                self.docker(f'container rm {container}')

    def clean(self):  # todo clean on all nodes
        CLI.info('Cleaning...')
        steps = 1

        CLI.step(1, steps, 'Prune Docker images and volumes')
        self.docker(f'system prune --volumes --force')

    def reload_webserver(self):
        CLI.info('Reloading webserver...')
        self.docker(f'exec -it {self.CONTAINER_WEBSERVER} {self.WEBSERVER} -s reload')

    def restart_proxy(self):
        CLI.info('Restarting proxy...')
        steps = 1

        CLI.step(1, steps, 'Reloading proxy container...')
        os.system(f'{self.docker_connection} docker-compose -f configs/docker/docker-compose.proxy.yml --project-name=reverse up -d')

    def status(self):
        if self.SWARM:  # todo remove containers as well ?
            CLI.info('Getting status...')
            os.system(f'docker stack services {self.PROJECT_NAME}')

        else:
            CLI.info('Getting status...')
            steps = 2

            CLI.step(1, steps, 'List of Docker images')
            self.docker(f'image ls')

            CLI.step(2, steps, 'Docker containers')
            self.docker(f'container ls -a --size')

    def networks(self):
        # todo for swarm
        CLI.info('Getting networks...')
        steps = 1

        CLI.step(1, steps, 'List of Docker networks')

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
        if self.SWARM:
            CLI.info('Reading logs...')

            services = params.split(' ') if params else self.get_services()
            lines = '-f' if params else '--tail 10'
            steps = len(services)

            for index, service in enumerate(services):
                CLI.step(index + 1, steps, f'{service} logs')
                os.system(f'docker service logs {service} {lines}')

        else:
            CLI.info('Reading logs...')

            containers = params.split(' ') if params else self.get_containers()
            lines = '-f' if params else '--tail 10'
            steps = len(containers)

            for index, container in enumerate(containers):
                CLI.step(index + 1, steps, f'{container} logs')
                self.docker(f'logs {container} {lines}')

    def shell(self):
        CLI.info('Connecting to Django shell...')
        self.docker(f'exec -i {self.CONTAINER_APP} python manage.py shell')

    def ssh(self, params):
        CLI.info('Logging to container...')
        self.docker(f'exec -it {params} /bin/sh')

    def manage(self, params):
        CLI.info('Django manage...')
        self.docker(f'exec -ti {self.CONTAINER_APP} python manage.py {params}')

    def psql(self):
        CLI.info('Starting psql...')
        env = self.load_environment(self.environment_file)
        self.docker(f'exec -it {self.CONTAINER_DB} psql -h {env["POSTGRES_HOST"]} -U {env["POSTGRES_USER"]} -d {env["POSTGRES_DBNAME"]} -W')
        # https://blog.sleeplessbeastie.eu/2014/03/23/how-to-non-interactively-provide-password-for-the-postgresql-interactive-terminal/
        # TODO: https://www.postgresql.org/docs/9.1/libpq-pgpass.html

    def exec(self, params):
        container, command = params.split(' ', maxsplit=1)
        CLI.info(f'Executing command "{command}" in container {container}...')
        self.docker(f'exec -it {container} {command}')

    def pg_dump(self):
        now = datetime.datetime.now()
        # filename = now.strftime("%Y%m%d%H%M%S")
        filename = now.strftime(f"{self.PROJECT_NAME}_%Y%m%d_%H%M.pg")
        CLI.info(f'Backuping database into file {filename}')
        env = self.load_environment(self.environment_file)
        self.docker(f'exec -it {self.CONTAINER_DB} bash -c \'pg_dump -Fc -h {env["POSTGRES_HOST"]} -U {env["POSTGRES_USER"]} {env["POSTGRES_DBNAME"]} -W > /backups/{filename}\'')
        # https://blog.sleeplessbeastie.eu/2014/03/23/how-to-non-interactively-provide-password-for-the-postgresql-interactive-terminal/
        # TODO: https://www.postgresql.org/docs/9.1/libpq-pgpass.html

    def pg_restore(self, params):
        CLI.info(f'Restoring database from file {params}')
        CLI.underline("Don't forget to drop database at first to prevent constraints collisions!")
        env = self.load_environment(self.environment_file)
        self.docker(f'exec -it {self.CONTAINER_DB} bash -c \'pg_restore -h {env["POSTGRES_HOST"]} -U {env["POSTGRES_USER"]} -d {env["POSTGRES_DBNAME"]} -W < /backups/{params}\'')
        # https://blog.sleeplessbeastie.eu/2014/03/23/how-to-non-interactively-provide-password-for-the-postgresql-interactive-terminal/
        # TODO: https://www.postgresql.org/docs/9.1/libpq-pgpass.html

    def send_test_email(self):
        CLI.info('Sending test email...')
        self.docker(f'exec -i {self.CONTAINER_APP} python manage.py sendtestemail --admins')

    def get_containers(self):
        containers = self.docker(f'container ls -a --format \'{{{{.Names}}}}\'', return_output=True)
        containers = containers.strip().split('\n')
        containers = list(filter(lambda x: x.startswith(self.CONTAINER_PREFIX), containers))
        return containers

    def get_services(self):
        services = os.popen(f'docker stack services {self.SWARM_STACK} --format \'{{{{.Name}}}}\'').read()
        services = services.strip().split('\n')
        services = list(filter(lambda x: x.startswith(self.CONTAINER_PREFIX), services))
        return services

    def get_containers_starts_with(self, start_with):
        return [i for i in self.get_containers() if i.startswith(start_with)]

    def docker(self, command, return_output=False):
        if return_output:
            return os.popen(f'{self.docker_connection} docker {command}').read()

        os.system(f'{self.docker_connection} docker {command}')

    def docker_compose(self, command):
        os.system(f'{self.docker_connection} docker-compose -f {self.configs_path}/docker/{self.COMPOSE_PREFIX}.yml -f {self.configs_path}/docker/{self.COMPOSE_PREFIX}.{self.environment_id}.yml {command}')
