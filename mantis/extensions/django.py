import time
from typing import Optional

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

    def manage(self, cmd: str, args: list = None, if_healthy: bool = False, healthy_timeout: Optional[int] = None):
        """Runs Django manage command"""
        container = self.django_container

        if healthy_timeout is not None:
            if not self.has_healthcheck(container):
                CLI.error(f"Container '{container}' has no healthcheck defined. Command not executed")
                return

            CLI.info(f"Waiting up to {healthy_timeout}s for container '{container}' to become healthy...")
            start_time = time.time()
            poll_interval = 1

            while time.time() - start_time < healthy_timeout:
                health_result = self.check_health(container)
                elapsed = int(time.time() - start_time)
                remaining = healthy_timeout - elapsed
                if health_result:
                    is_healthy, status = health_result
                    if is_healthy:
                        CLI.success(f"Container '{container}' is healthy after {elapsed}s")
                        break
                    CLI.info(f"Container status: {status} ({elapsed}s elapsed, {remaining}s remaining)")
                time.sleep(poll_interval)
            else:
                elapsed = int(time.time() - start_time)
                CLI.warning(f"Container '{container}' did not become healthy within {elapsed}s, skipping command")
                return

        elif if_healthy:
            health_result = self.check_health(container)
            if health_result is None:
                CLI.error(f"Container '{container}' has no healthcheck defined. Command not executed")
                return
            is_healthy, status = health_result
            if not is_healthy:
                CLI.warning(f"Container '{container}' is not healthy (status: {status}), skipping command")
                return

        CLI.info('Django manage...')
        args_str = ' '.join(args) if args else ''
        full_cmd = f'{cmd} {args_str}'.strip()
        self.docker(f'exec -ti {container} python manage.py {full_cmd}')

    def send_test_email(self):
        """Sends test email to admins"""
        CLI.info('Sending test email...')
        self.docker(f'exec -i {self.django_container} python manage.py sendtestemail --admins')

    def reset_migrations(self):
        """Clears migration history and fakes all migrations"""
        CLI.info('Resetting migrations...')
        container = self.django_container
        self.docker(f'exec -i {container} python manage.py shell -c "from django.db import connection; cursor = connection.cursor(); cursor.execute(\'DELETE FROM django_migrations\')"')
        CLI.info('Faking migrations...')
        self.docker(f'exec -i {container} python manage.py migrate --fake')
