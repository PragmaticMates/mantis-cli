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
