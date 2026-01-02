from mantis.helpers import CLI
from mantis.commands import command


class Nginx():
    nginx_service = 'nginx'

    @property
    def nginx_container(self):
        return self.get_container_name(self.nginx_service)

    def reload_webserver(self):
        """
        Reloads nginx webserver
        """
        CLI.info('Reloading nginx...')
        self.docker(f'exec {self.nginx_container} nginx -s reload')


# Register extension commands
@command(name='reload-webserver')
def reload_webserver(manager):
    """Reloads nginx webserver"""
    manager.reload_webserver()
