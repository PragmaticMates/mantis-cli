from mantis.helpers import CLI


class Django():
    django_service = 'django'

    @property
    def django_container(self):
        container_name = f"{self.CONTAINER_PREFIX}{self.get_container_suffix(self.django_service)}"
        container_name_with_suffix = f"{container_name}-1"

        if container_name_with_suffix in self.get_containers():
            return container_name_with_suffix
        
        if container_name in self.get_containers():
            return container_name
        
        CLI.error(f"Container {container_name} not found")

    def shell(self):
        """
        Runs and connects to Django shell
        """
        CLI.info('Connecting to Django shell...')
        self.docker(f'exec -i {self.django_container} python manage.py shell')

    def manage(self, params):
        """
        Runs Django manage command
        """
        CLI.info('Django manage...')
        self.docker(f'exec -ti {self.django_container} python manage.py {params}')

    def send_test_email(self):
        """
        Sends test email to admins using Django 'sendtestemail' command
        """
        CLI.info('Sending test email...')
        self.docker(f'exec -i {self.django_container} python manage.py sendtestemail --admins')
