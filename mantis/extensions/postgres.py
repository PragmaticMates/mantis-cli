import datetime

from mantis.helpers import CLI
from mantis.commands import command


class Postgres():
    postgres_service = 'postgres'

    @property
    def postgres_container(self):
        return self.get_container_name(self.postgres_service)

    def psql(self):
        """
        Starts psql console
        """
        CLI.info('Starting psql...')
        env = self.env.load()
        self.docker(f'exec -it {self.postgres_container} psql -h {env["POSTGRES_HOST"]} -U {env["POSTGRES_USER"]} -d {env["POSTGRES_DBNAME"]} -W')
        # https://blog.sleeplessbeastie.eu/2014/03/23/how-to-non-interactively-provide-password-for-the-postgresql-interactive-terminal/
        # TODO: https://www.postgresql.org/docs/9.1/libpq-pgpass.html

    def pg_dump(self, data_only=False, table=None):
        """
        Backups PostgreSQL database [data and structure]
        """
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
        env = self.env.load()
        filename = now.strftime(f"{env['POSTGRES_DBNAME']}_%Y%m%d_%H%M{data_only_suffix}.{extension}")
        CLI.info(f'Backuping database into file {filename}')
        self.docker(f'exec -it {self.postgres_container} bash -c \'pg_dump {compressed_params} {data_only_param} -h {env["POSTGRES_HOST"]} -U {env["POSTGRES_USER"]} {table_params} {env["POSTGRES_DBNAME"]} -W > /backups/{filename}\'')
        # https://blog.sleeplessbeastie.eu/2014/03/23/how-to-non-interactively-provide-password-for-the-postgresql-interactive-terminal/
        # TODO: https://www.postgresql.org/docs/9.1/libpq-pgpass.html

    def pg_dump_data(self, table=None):
        """
        Backups PostgreSQL database [data only]
        """
        self.pg_dump(data_only=True, table=table)

    def pg_restore(self, filename, table=None):
        """
        Restores database from backup [data and structure]
        """
        if table:
            CLI.info(f'Restoring table {table} from file {filename}')
            table_params = f'--table {table}'
        else:
            CLI.info(f'Restoring database from file {filename}')
            table_params = ''

        CLI.underline("Don't forget to drop database at first to prevent constraints collisions!")
        env = self.env.load()
        self.docker(f'exec -it {self.postgres_container} bash -c \'pg_restore -h {env["POSTGRES_HOST"]} -U {env["POSTGRES_USER"]} -d {env["POSTGRES_DBNAME"]} {table_params} -W < /backups/{filename}\'')
        # print(f'exec -it {self.postgres_container} bash -c \'pg_restore -h {env["POSTGRES_HOST"]} -U {env["POSTGRES_USER"]} -d {env["POSTGRES_DBNAME"]} {table_params} -W < /backups/{filename}\'')
        # https://blog.sleeplessbeastie.eu/2014/03/23/how-to-non-interactively-provide-password-for-the-postgresql-interactive-terminal/
        # TODO: https://www.postgresql.org/docs/9.1/libpq-pgpass.html

    def pg_restore_data(self, params):
        """
        Restores database from backup [data only]
        """
        filename, table = params.split(',')
        self.pg_restore(filename=filename, table=table)


# Register extension commands
@command()
def psql(manager):
    """Starts psql console"""
    manager.psql()


@command(name='pg-dump')
def pg_dump_cmd(manager, *args):
    """Backups PostgreSQL database"""
    data_only = '--data-only' in args or '-d' in args
    table = None
    for i, arg in enumerate(args):
        if arg in ('--table', '-t') and i + 1 < len(args):
            table = args[i + 1]
        elif arg.startswith('--table='):
            table = arg.split('=')[1]
    manager.pg_dump(data_only=data_only, table=table)


@command(name='pg-dump-data')
def pg_dump_data_cmd(manager, *args):
    """Backups PostgreSQL database [data only]"""
    table = None
    for i, arg in enumerate(args):
        if arg in ('--table', '-t') and i + 1 < len(args):
            table = args[i + 1]
        elif arg.startswith('--table='):
            table = arg.split('=')[1]
        elif not arg.startswith('-'):
            table = arg
    manager.pg_dump_data(table=table)


@command(name='pg-restore')
def pg_restore_cmd(manager, *args):
    """Restores database from backup"""
    if not args:
        CLI.error("pg-restore requires a filename argument")
    filename = None
    table = None
    positional_args = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ('--table', '-t') and i + 1 < len(args):
            table = args[i + 1]
            i += 2
        elif arg.startswith('--table='):
            table = arg.split('=')[1]
            i += 1
        elif not arg.startswith('-'):
            positional_args.append(arg)
            i += 1
        else:
            i += 1
    if positional_args:
        filename = positional_args[0]
    if not filename:
        CLI.error("pg-restore requires a filename argument")
    manager.pg_restore(filename=filename, table=table)


@command(name='pg-restore-data')
def pg_restore_data_cmd(manager, filename: str, table: str):
    """Restores database from backup [data only]"""
    if not filename or not table:
        CLI.error("pg-restore-data requires filename and table arguments")
    manager.pg_restore(filename=filename, table=table)
