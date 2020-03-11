import os


class CLI(object):
    @staticmethod
    def info(text):
        print(f'{Colors.BLUE}{text}{Colors.ENDC}')

    @staticmethod
    def error(text):
        exit(f'{Colors.RED}{text}{Colors.ENDC}')

    @staticmethod
    def step(index, total, text):
        print(f'{Colors.YELLOW}[{index}/{total}] {text}{Colors.ENDC}')


class Colors:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    PINK = '\033[95m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class Mantis(object):
    environment_id = None
    docker_ssh = ''

    def __init__(self, config=None, environment_id=None):
        self.environment_id = environment_id
        self.init_config(config)

    def init_config(self, config):
        if config is not None:
            variables = config
            prefix = ''
        else:
            variables = os.environ
            prefix = 'MANTIS_'

        self.user = variables[f'{prefix}USER']

        if self.environment_id is not None:
            # Get environment settings
            if self.environment_id == 'dev':
                self.host = 'localhost'
            else:
                self.host = variables[f'{prefix}HOST_{self.environment_id.upper()}']
                self.docker_ssh = f'-H "ssh://{self.user}@{self.host}"'

            print(f'Deploying to {Colors.BOLD}{self.environment_id}{Colors.ENDC}: {Colors.RED}{self.host}{Colors.ENDC}')

        self.PROJECT_NAME = variables[f'{prefix}PROJECT_NAME']
        self.IMAGE_NAME = variables[f'{prefix}IMAGE_NAME']
        self.DOCKER_REPOSITORY = variables[f'{prefix}DOCKER_REPOSITORY']
        self.DOCKER_TAG = variables[f'{prefix}DOCKER_TAG']
        self.CONTAINER_PREFIX = variables[f'{prefix}CONTAINER_PREFIX']
        self.CONTAINER_SUFFIX_DB = variables[f'{prefix}CONTAINER_SUFFIX_DB']
        self.CONTAINER_SUFFIX_CACHE = variables[f'{prefix}CONTAINER_SUFFIX_CACHE']
        self.CONTAINER_SUFFIX_APP = variables[f'{prefix}CONTAINER_SUFFIX_APP']
        self.CONTAINER_SUFFIX_NGINX = variables[f'{prefix}CONTAINER_SUFFIX_NGINX']  # TODO: rename to webserver?
        self.CONTAINER_APP = f'{self.CONTAINER_PREFIX}{self.CONTAINER_SUFFIX_APP}'
        self.CONTAINER_DB = f'{self.CONTAINER_PREFIX}{self.CONTAINER_SUFFIX_DB}'
        self.CONTAINER_CACHE = f'{self.CONTAINER_PREFIX}{self.CONTAINER_SUFFIX_CACHE}'
        self.CONTAINER_NGINX = f'{self.CONTAINER_PREFIX}{self.CONTAINER_SUFFIX_NGINX}'

    def build(self, no_cache='', params={}):
        CLI.info(f'Building...')
        steps = 3

        CLI.step(1, steps, 'Building Docker image...')
        FONTAWESOME_NPM_AUTH_TOKEN = os.environ.get('FONTAWESOME_NPM_AUTH_TOKEN')  # TODO: move to arguments
        # now = datetime.datetime.now()
        # CACHE_DATE = now.strftime("%Y%m%d%H%M%S")
        # os.system(f'docker build . --build-arg FONTAWESOME_NPM_AUTH_TOKEN={FONTAWESOME_NPM_AUTH_TOKEN} --build-arg CACHE_DATE={CACHE_DATE} -t {IMAGE_NAME} -f configs/docker/Dockerfile {no_cache}')
        os.system(f'docker build . --build-arg FONTAWESOME_NPM_AUTH_TOKEN={FONTAWESOME_NPM_AUTH_TOKEN} -t {self.IMAGE_NAME} -f configs/docker/Dockerfile {no_cache}')

        CLI.step(2, steps, 'Tagging Docker image...')
        os.system(f'docker tag {self.IMAGE_NAME} {self.DOCKER_REPOSITORY}:{self.DOCKER_TAG}')
        print(f'Successfully tagged {self.DOCKER_REPOSITORY}:{self.DOCKER_TAG}')

        CLI.step(3, steps, 'Pushing Docker image...')
        os.system(f'docker push {self.DOCKER_REPOSITORY}:{self.DOCKER_TAG}')

    def upload(self):
        CLI.info('Uploading...')
        steps = 2

        CLI.step(1, steps, 'Uploading nginx server configs...')

        if self.environment_id == 'dev':
            print('Skippipng...')
        else:
            os.system(f'rsync -rvzh --progress configs/nginx/{self.environment_id}.conf {self.user}@{self.host}:/home/{self.user}/public_html/{self.IMAGE_NAME}/configs/nginx/')

        CLI.step(2, steps, 'Pulling docker image...')
        os.system(f'docker-compose {self.docker_ssh} -f configs/docker/docker-compose.yml -f configs/docker/docker-compose.{self.environment_id}.yml pull')

    def restart(self):
        CLI.info('Restarting...')
        steps = 4

        CLI.step(1, steps, 'Stopping and removing Docker app container...')

        for container in self.get_containers():
            if container == self.CONTAINER_APP:
                os.popen(f'docker {self.docker_ssh} container stop {container}').read()
                os.system(f'docker {self.docker_ssh} container rm {container}')

        CLI.step(2, steps, 'Recreating Docker containers...')
        os.system(f'docker-compose {self.docker_ssh} -f configs/docker/docker-compose.yml -f configs/docker/docker-compose.{self.environment_id}.yml --project-name={self.PROJECT_NAME} up -d')

        CLI.step(3, steps, 'Prune Docker images and volumes')
        os.system(f'docker {self.docker_ssh} system prune --volumes --force')

        CLI.step(4, steps, 'Collecting static files')
        os.system(f'docker {self.docker_ssh} exec -i {self.CONTAINER_APP} python manage.py collectstatic --noinput')

    def deploy(self):
        CLI.info('Deploying...')
        steps = 7

        CLI.step(1, steps, 'Creating new app container...')
        # timestamp = 'now'
        os.system(f'docker-compose {self.docker_ssh} -f configs/docker/docker-compose.yml -f configs/docker/docker-compose.{self.environment_id}.yml --project-name={self.PROJECT_NAME} run -d --service-ports --name={self.CONTAINER_APP}_new app')

        CLI.step(2, steps, 'Renaming old app container...')
        os.system(f'docker {self.docker_ssh} container rename {self.CONTAINER_APP} {self.CONTAINER_APP}_old')

        CLI.step(3, steps, 'Renaming new app container...')
        os.system(f'docker {self.docker_ssh} container rename {self.CONTAINER_APP}_new {self.CONTAINER_APP}')

        CLI.step(4, steps, 'Collecting static files')
        os.system(f'docker {self.docker_ssh} exec -i {self.CONTAINER_APP} python manage.py collectstatic --noinput')

        CLI.step(5, steps, 'Reloading webserver...')
        # sed -i '' "2s/.*/    server e-max-web_app:8000;/" configs/nginx/stage.conf
        os.system(f'docker {self.docker_ssh} exec -it {self.CONTAINER_NGINX} nginx -s reload')

        CLI.step(6, steps, 'Stopping old app container...')
        os.system(f'docker {self.docker_ssh} container stop {self.CONTAINER_APP}_old')

        CLI.step(7, steps, 'Removing old app container...')
        os.system(f'docker {self.docker_ssh} container rm {self.CONTAINER_APP}_old')

    def stop(self):
        CLI.info('Stopping containers...')

        containers = self.get_containers()

        steps = len(containers)

        for index, container in enumerate(containers):
            CLI.step(index + 1, steps, f'Stopping {container}')
            os.system(f'docker {self.docker_ssh} container stop {container}')

    def start(self):
        CLI.info('Starting containers...')

        containers = self.get_containers()

        steps = len(containers)

        for index, container in enumerate(containers):
            CLI.step(index + 1, steps, f'Starting {container}')
            os.system(f'docker {self.docker_ssh} container start {container}')

    def remove(self):
        CLI.info('Removing containers...')

        containers = self.get_containers()

        steps = len(containers)

        for index, container in enumerate(containers):
            CLI.step(index + 1, steps, f'Removing {container}')
            os.system(f'docker {self.docker_ssh} container rm {container}')

    def clean(self):
        CLI.info('Cleaning...')
        steps = 1

        CLI.step(1, steps, 'Prune Docker images and volumes')
        os.system(f'docker {self.docker_ssh} system prune --volumes --force')

    def reload_webserver(self):
        CLI.info('Reloading webserver...')
        os.system(f'docker {self.docker_ssh} exec -it {self.CONTAINER_NGINX} nginx -s reload')

    def restart_proxy(self):
        CLI.info('Restarting proxy...')
        steps = 1

        CLI.step(1, steps, 'Reloading proxy container...')
        os.system(f'docker-compose {self.docker_ssh} -f configs/docker/docker-compose.{self.environment_id}.proxy.yml --project-name=reverse up -d')

    def status(self):
        CLI.info('Getting status...')
        steps = 2

        CLI.step(1, steps, 'List of Docker images')
        os.system(f'docker {self.docker_ssh} image ls')

        CLI.step(2, steps, 'Docker containers')
        os.system(f'docker {self.docker_ssh} container ls -a --size')

    def networks(self):
        CLI.info('Getting networks...')
        steps = 1

        CLI.step(1, steps, 'List of Docker networks')

        networks = os.popen(f'docker {self.docker_ssh} network ls').read()
        networks = networks.strip().split('\n')

        for index, network in enumerate(networks):
            network_data = list(filter(lambda x: x != '', network.split(' ')))
            network_name = network_data[1]

            if index == 0:
                print(f'{network}\tCONTAINERS')
            else:
                containers = os.popen(f'docker {self.docker_ssh} network inspect -f \'{{{{ range $key, $value := .Containers }}}}{{{{ .Name }}}} {{{{ end }}}}\' {network_name}').read()
                containers = ', '.join(containers.split())
                print(f'{network}\t{containers}'.strip())

    def logs(self):
        CLI.info('Reading logs...')

        containers = self.get_containers()

        steps = len(containers)

        for index, container in enumerate(containers):
            CLI.step(index + 1, steps, f'{container} logs')
            os.system(f'docker {self.docker_ssh} logs {container} --tail 10')

    def shell(self):
        CLI.info('Connecting to Django shell...')
        os.system(f'docker {self.docker_ssh} exec -i {self.CONTAINER_APP} python manage.py shell')

    def ssh(self, params):
        CLI.info('Logging to container...')
        os.system(f'docker {self.docker_ssh} exec -it {params} /bin/sh')

    def manage(self, params):
        CLI.info('Django manage...')
        os.system(f'docker {self.docker_ssh} exec -i {self.CONTAINER_APP} python manage.py {params}')

    def psql(self):
        CLI.info('Starting psql...')
        # postgresql_user = os.environ['POSTGRES_USER']
        # postgresql_database = os.environ['POSTGRES_DB']

        # print(f'POSTGRES_USER = {postgresql_user}')
        # print(f'POSTGRES_DB = {postgresql_database}')

        # print('Loading environment')
        # os.system(f'set -a; source configs/environments/{self.environment_id}.env; set +a;')
        # https://stackoverflow.com/questions/19331497/set-environment-variables-from-file-of-key-value-pairs/19331521

        os.system(f'set -a; source configs/environments/{self.environment_id}.env; set +a;'  # loaded environment
                  f'docker {self.docker_ssh} exec -it {self.CONTAINER_DB} psql -U $POSTGRES_USER -d $POSTGRES_DB')

    def send_test_email(self):
        CLI.info('Sending test email...')
        os.system(f'docker {self.docker_ssh} exec -i {self.CONTAINER_APP} python manage.py sendtestemail --admins')

    def get_containers(self):
        containers = os.popen(f'docker {self.docker_ssh} container ls -a --format \'{{{{.Names}}}}\'').read()
        containers = containers.strip().split('\n')
        containers = list(filter(lambda x: x.startswith(self.CONTAINER_PREFIX), containers))
        return containers
