from mantis.helpers import CLI


class Django():
    django_service = 'django'

    @property
    def django_container(self):
        return f"{self.CONTAINER_PREFIX}{self.get_container_suffix(self.django_service)}"

    def shell(self):
        CLI.info('Connecting to Django shell...')
        self.docker(f'exec -i {self.django_container} python manage.py shell')

    def manage(self, params):
        CLI.info('Django manage...')
        self.docker(f'exec -ti {self.django_container} python manage.py {params}')

    def send_test_email(self):
        CLI.info('Sending test email...')
        self.docker(f'exec -i {self.django_container} python manage.py sendtestemail --admins')


class Postgres():
    postgres_service = 'postgres'

    @property
    def postgres_container(self):
        return f"{self.CONTAINER_PREFIX}{self.get_container_suffix(self.postgres_service)}"

    def psql(self):
        CLI.info('Starting psql...')
        env = self.load_environment()
        self.docker(f'exec -it {self.postgres_container} psql -h {env["POSTGRES_HOST"]} -U {env["POSTGRES_USER"]} -d {env["POSTGRES_DBNAME"]} -W')
        # https://blog.sleeplessbeastie.eu/2014/03/23/how-to-non-interactively-provide-password-for-the-postgresql-interactive-terminal/
        # TODO: https://www.postgresql.org/docs/9.1/libpq-pgpass.html

    def pg_dump(self, data_only=False, table=None):
        if data_only:
            compressed = True
            data_only_param = '--data-only'
            data_only_suffix = f'_{table}' if table else '_data'
        else:
            compressed = True
            data_only_param = ''
            data_only_suffix = ''

        extension = 'pg' if compressed else 'sql'
        compressed_params = '-Fc' if compressed else ''
        table_params = f'--table={table}' if table else ''

        now = datetime.datetime.now()
        # filename = now.strftime("%Y%m%d%H%M%S")
        filename = now.strftime(f"{self.PROJECT_NAME}_%Y%m%d_%H%M{data_only_suffix}.{extension}")
        CLI.info(f'Backuping database into file {filename}')
        env = self.load_environment()
        self.docker(f'exec -it {self.postgres_container} bash -c \'pg_dump {compressed_params} {data_only_param} -h {env["POSTGRES_HOST"]} -U {env["POSTGRES_USER"]} {table_params} {env["POSTGRES_DBNAME"]} -W > /backups/{filename}\'')
        # https://blog.sleeplessbeastie.eu/2014/03/23/how-to-non-interactively-provide-password-for-the-postgresql-interactive-terminal/
        # TODO: https://www.postgresql.org/docs/9.1/libpq-pgpass.html

    def pg_dump_data(self, table=None):
        self.pg_dump(data_only=True, table=table)

    def pg_restore(self, filename, table=None):
        if table:
            CLI.info(f'Restoring table {table} from file {filename}')
            table_params = f'--table {table}'
        else:
            CLI.info(f'Restoring database from file {filename}')
            table_params = ''

        CLI.underline("Don't forget to drop database at first to prevent constraints collisions!")
        env = self.load_environment()
        self.docker(f'exec -it {self.postgres_container} bash -c \'pg_restore -h {env["POSTGRES_HOST"]} -U {env["POSTGRES_USER"]} -d {env["POSTGRES_DBNAME"]} {table_params} -W < /backups/{filename}\'')
        # print(f'exec -it {self.postgres_container} bash -c \'pg_restore -h {env["POSTGRES_HOST"]} -U {env["POSTGRES_USER"]} -d {env["POSTGRES_DBNAME"]} {table_params} -W < /backups/{filename}\'')
        # https://blog.sleeplessbeastie.eu/2014/03/23/how-to-non-interactively-provide-password-for-the-postgresql-interactive-terminal/
        # TODO: https://www.postgresql.org/docs/9.1/libpq-pgpass.html

    def pg_restore_data(self, params):
        filename, table = params.split(',')
        self.pg_restore(filename=filename, table=table)


class Nginx():
    nginx_service = 'nginx'

    @property
    def nginx_container(self):
        return f"{self.CONTAINER_PREFIX}{self.get_container_suffix(self.nginx_service)}"

    def reload_webserver(self):
        CLI.info('Reloading nginx...')
        self.docker(f'exec {self.nginx_container} nginx -s reload')
