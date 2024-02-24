import os

from mantis.helpers import CLI, Colors


class Environment(object):
    def __init__(self, environment_id, folder):
        self.id = environment_id
        self.folder = folder

        if self.id:
            self.setup()

    def setup(self):
        # environment files
        self.path = self._get_path(self.id)

        if not self.path:
            return

        if not os.path.exists(self.path):
            CLI.error(f"Environment path '{self.path}' does not exist")

        if not os.path.isdir(self.path):
            CLI.error(f"Environment path '{self.path}' is not directory")

        for dirpath, directories, files in os.walk(self.path):
            environment_filenames = list(filter(lambda f: f.endswith('.env'), files))
            encrypted_environment_filenames = list(filter(lambda f: f.endswith('.env.encrypted'), files))
            self.files = list(map(lambda x: os.path.join(dirpath, x), environment_filenames))
            self.encrypted_files = list(map(lambda x: os.path.join(dirpath, x), encrypted_environment_filenames))

    def _get_path(self, id):
        possible_folder_names = [f'.{id}', id]
        possible_folders = list(map(lambda x: os.path.normpath(os.path.join(self.folder, x)), possible_folder_names))

        for environment_path in possible_folders:
            if os.path.exists(environment_path):
                if not os.path.isdir(environment_path):
                    CLI.error(f"Environment path '{environment_path}' is not directory")

                CLI.info(f"Found environment path: '{environment_path}'")
                return environment_path

        CLI.danger(f"Environment path not found. Tried: {', '.join(possible_folders)}")

    def read(self, path):
        if not os.path.exists(path):
            CLI.error(f'Environment file {path} does not exist')
            return None

        with open(path) as f:
            return f.read().splitlines()

    def load(self, path=None):
        # if not path is specified, load variables from all environment files
        if not path:
            CLI.info(f'Environment file path not specified. Walking all environment files...')

            values = {}

            for env_file in self.files:
                env_values = self.load(path=env_file)
                values.update(env_values)

            return values

        # read environment file
        lines = self.read(path)

        # TODO: refactor
        return dict(
            (
                self.parse_line(line)[0],
                self.parse_line(line)[1]
            )
            for line in lines if self.is_valid_line(line)
        )

    @staticmethod
    def is_valid_line(line):
        return not line.startswith('#') and line.rstrip("\n") != ''

    @staticmethod
    def parse_line(line):
        if not Environment.is_valid_line(line):
            return None

        return line.split('=', maxsplit=1)

    @staticmethod
    def save(path, lines):
        with open(path, "w") as f:
            for line in lines:
                f.write(f'{line}\n')
