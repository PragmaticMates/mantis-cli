from mantis.helpers import CLI
from mantis.manager import Mantis


class Django(Mantis):
    def shell(self):
        CLI.info('Connecting to Django shell...')
        self.docker(f'exec -i {self.CONTAINER_APP} python manage.py shell')

    def manage(self, params):
        CLI.info('Django manage...')
        self.docker(f'exec -ti {self.CONTAINER_APP} python manage.py {params}')

    def send_test_email(self):
        CLI.info('Sending test email...')
        self.docker(f'exec -i {self.CONTAINER_APP} python manage.py sendtestemail --admins')
