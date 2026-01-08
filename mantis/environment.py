import os
from pathlib import Path

from mantis.helpers import CLI


class Environment(object):
    def __init__(self, environment_id, folder, single_mode=False):
        self.id = environment_id
        self.folder = folder
        self.single_mode = single_mode

        if self.single_mode:
            self.setup_single_mode()
        elif self.id:
            self.setup()

    def setup(self):
        # environment files
        self.path = self._get_path(self.id)

        if not self.path:
            return

        env_path = Path(self.path)

        if not env_path.exists():
            CLI.error(f"Environment path '{self.path}' does not exist")

        if not env_path.is_dir():
            CLI.error(f"Environment path '{self.path}' is not directory")

        for dirpath, directories, files in os.walk(self.path):
            environment_filenames = [f for f in files if f.endswith('.env')]
            encrypted_environment_filenames = [f for f in files if f.endswith('.env.encrypted')]
            self.files = [os.path.join(dirpath, f) for f in environment_filenames]
            self.encrypted_files = [os.path.join(dirpath, f) for f in encrypted_environment_filenames]

    def setup_single_mode(self):
        """
        Setup for single connection mode: look for env files directly in the folder
        instead of environment subfolders
        """
        self.path = self.folder
        env_path = Path(self.path)

        if not env_path.exists():
            CLI.warning(f"Environment path '{self.path}' does not exist")
            self.files = []
            self.encrypted_files = []
            return

        if not env_path.is_dir():
            CLI.error(f"Environment path '{self.path}' is not directory")

        CLI.info(f"Found environment path (single mode): '{self.path}'")

        # Look for env files directly in the folder (not in subdirectories)
        files = [f.name for f in env_path.iterdir() if f.is_file()]
        environment_filenames = [f for f in files if f.endswith('.env') and not f.endswith('.encrypted')]
        encrypted_environment_filenames = [f for f in files if f.endswith('.env.encrypted')]
        self.files = [str(env_path / f) for f in environment_filenames]
        self.encrypted_files = [str(env_path / f) for f in encrypted_environment_filenames]

    def _get_path(self, id):
        possible_folder_names = [f'.{id}', id]
        possible_folders = [str(Path(self.folder) / name) for name in possible_folder_names]

        for environment_path in possible_folders:
            env_path = Path(environment_path)
            if env_path.exists():
                if not env_path.is_dir():
                    CLI.error(f"Environment path '{environment_path}' is not directory")

                CLI.info(f"Found environment path: '{environment_path}'")
                return environment_path

        CLI.danger(f"Environment path not found. Tried: {', '.join(possible_folders)}")

    def read(self, path):
        if not Path(path).exists():
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
