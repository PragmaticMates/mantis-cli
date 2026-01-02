from mantis.helpers import CLI
from mantis.commands import command


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


# Register extension commands
@command()
def shell(manager):
    """Runs and connects to Django shell"""
    manager.shell()


@command()
def manage(manager, *args):
    """Runs Django manage command"""
    if not args:
        CLI.error("manage requires a command argument (e.g., 'mantis production manage migrate')")
    params = ' '.join(args)
    manager.manage(params)


@command(name='send-test-email')
def send_test_email(manager):
    """Sends test email to admins using Django 'sendtestemail' command"""
    manager.send_test_email()
