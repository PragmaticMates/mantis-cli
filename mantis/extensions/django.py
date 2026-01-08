from mantis.helpers import CLI


class Django():
    django_service = 'django'

    @property
    def django_container(self):
        container_name = self.get_container_name(self.django_service)
        container_name_with_suffix = f"{container_name}-1"

        if container_name_with_suffix in self.get_containers():
            return container_name_with_suffix

        if container_name in self.get_containers():
            return container_name

        CLI.error(f"Container {container_name} not found")

    def shell(self):
        """Runs and connects to Django shell"""
        CLI.info('Connecting to Django shell...')
        self.docker(f'exec -i {self.django_container} python manage.py shell')

    def manage(self, cmd: str, args: list = None):
        """Runs Django manage command"""
        CLI.info('Django manage...')
        args_str = ' '.join(args) if args else ''
        full_cmd = f'{cmd} {args_str}'.strip()
        self.docker(f'exec -ti {self.django_container} python manage.py {full_cmd}')

    def send_test_email(self):
        """Sends test email to admins"""
        CLI.info('Sending test email...')
        self.docker(f'exec -i {self.django_container} python manage.py sendtestemail --admins')
