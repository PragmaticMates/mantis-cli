from mantis.helpers import CLI


class Nginx():
    nginx_service = 'nginx'

    @property
    def nginx_container(self):
        return f"{self.CONTAINER_PREFIX}{self.get_container_suffix(self.nginx_service)}"

    def reload_webserver(self):
        """
        Reloads nginx webserver
        """
        CLI.info('Reloading nginx...')
        self.docker(f'exec {self.nginx_container} nginx -s reload')
