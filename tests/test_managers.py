"""Tests for managers module - environment validation and resolution."""
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from mantis.managers import (
    BaseManager,
    validate_environment_for_commands,
    resolve_environment,
    SECRETS_COMMANDS,
)


class TestValidateEnvironmentForCommands:
    """Tests for validate_environment_for_commands function."""

    def test_single_connection_mode_skips_validation(self):
        """Test that single connection mode skips validation."""
        config = {'connection': 'ssh://user@host:22'}

        # Should not raise any error
        validate_environment_for_commands(
            'any-env', config, '/path/to/mantis.json', ['status', 'deploy']
        )

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.is_dir')
    @patch('pathlib.Path.iterdir')
    def test_secrets_command_valid_folder_env(
        self, mock_iterdir, mock_is_dir, mock_exists
    ):
        """Test secrets command with valid folder-based environment."""
        config = {
            'environment': {'folder': '<MANTIS>/../environments'},
            'connections': {}
        }

        mock_exists.return_value = True
        mock_is_dir.return_value = True

        mock_local = MagicMock()
        mock_local.name = 'local'
        mock_local.is_dir.return_value = True

        mock_test = MagicMock()
        mock_test.name = 'test'
        mock_test.is_dir.return_value = True

        mock_iterdir.return_value = [mock_local, mock_test]

        # Should not raise any error
        validate_environment_for_commands(
            'local', config, '/path/to/mantis.json', ['show-env']
        )

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.is_dir')
    @patch('pathlib.Path.iterdir')
    @patch('mantis.managers.CLI.error')
    def test_secrets_command_invalid_folder_env(
        self, mock_error, mock_iterdir, mock_is_dir, mock_exists
    ):
        """Test secrets command with invalid folder-based environment."""
        config = {
            'environment': {'folder': '<MANTIS>/../environments'},
            'connections': {'stage': 'ssh://user@host:22'}
        }

        mock_exists.return_value = True
        mock_is_dir.return_value = True

        mock_test = MagicMock()
        mock_test.name = 'test'
        mock_test.is_dir.return_value = True

        mock_iterdir.return_value = [mock_test]

        validate_environment_for_commands(
            'stage', config, '/path/to/mantis.json', ['show-env']
        )

        # Should call CLI.error because 'stage' is not in folder_envs
        mock_error.assert_called_once()
        call_args = mock_error.call_args[0][0]
        assert 'stage' in call_args
        assert 'show-env' in call_args

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.is_dir')
    def test_other_command_valid_connection_env(self, mock_is_dir, mock_exists):
        """Test non-secrets command with valid connection environment."""
        config = {
            'environment': {'folder': '/nonexistent'},
            'connections': {'stage': 'ssh://user@host:22'}
        }

        mock_exists.return_value = False

        # Should not raise any error
        validate_environment_for_commands(
            'stage', config, '/path/to/mantis.json', ['status']
        )

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.is_dir')
    def test_other_command_local_always_valid(self, mock_is_dir, mock_exists):
        """Test that 'local' is always valid for non-secrets commands."""
        config = {
            'environment': {'folder': '/nonexistent'},
            'connections': {'stage': 'ssh://user@host:22'}
        }

        mock_exists.return_value = False

        # Should not raise any error for 'local'
        validate_environment_for_commands(
            'local', config, '/path/to/mantis.json', ['status', 'deploy']
        )

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.is_dir')
    @patch('mantis.managers.CLI.error')
    def test_other_command_invalid_connection_env(
        self, mock_error, mock_is_dir, mock_exists
    ):
        """Test non-secrets command with invalid environment."""
        config = {
            'environment': {'folder': '/nonexistent'},
            'connections': {'stage': 'ssh://user@host:22'}
        }

        mock_exists.return_value = False

        validate_environment_for_commands(
            'production', config, '/path/to/mantis.json', ['status']
        )

        # Should call CLI.error because 'production' is not a valid connection
        mock_error.assert_called_once()
        call_args = mock_error.call_args[0][0]
        assert 'production' in call_args
        assert 'status' in call_args

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.is_dir')
    @patch('pathlib.Path.iterdir')
    @patch('mantis.managers.CLI.error')
    def test_mixed_commands_env_not_in_both(
        self, mock_error, mock_iterdir, mock_is_dir, mock_exists
    ):
        """Test mixed commands where environment doesn't satisfy all."""
        config = {
            'environment': {'folder': '<MANTIS>/../environments'},
            'connections': {'stage': 'ssh://user@host:22'}
        }

        mock_exists.return_value = True
        mock_is_dir.return_value = True

        # Only 'test' folder exists, not 'stage'
        mock_test = MagicMock()
        mock_test.name = 'test'
        mock_test.is_dir.return_value = True

        mock_iterdir.return_value = [mock_test]

        # 'stage' is valid for 'status' but not for 'show-env'
        validate_environment_for_commands(
            'stage', config, '/path/to/mantis.json', ['status', 'show-env']
        )

        # Should fail on 'show-env' command
        mock_error.assert_called_once()
        call_args = mock_error.call_args[0][0]
        assert 'stage' in call_args
        assert 'show-env' in call_args


class TestResolveEnvironment:
    """Tests for resolve_environment function."""

    def test_none_environment_returns_none(self):
        """Test that None environment returns None."""
        config = {'connections': {'stage': 'ssh://user@host:22'}}

        result = resolve_environment(None, config, '/path/to/mantis.json')
        assert result is None

    def test_single_connection_mode_returns_as_is(self):
        """Test that single connection mode returns environment as-is."""
        config = {'connection': 'ssh://user@host:22'}

        result = resolve_environment('any-env', config, '/path/to/mantis.json')
        assert result == 'any-env'

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.is_dir')
    def test_local_always_returns_for_non_secrets(self, mock_is_dir, mock_exists):
        """Test that 'local' is always returned for non-secrets commands."""
        config = {
            'environment': {'folder': '/nonexistent'},
            'connections': {'stage': 'ssh://user@host:22'}
        }

        mock_exists.return_value = False

        result = resolve_environment('local', config, '/path/to/mantis.json', 'status')
        assert result == 'local'

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.is_dir')
    def test_exact_match_returns_env(self, mock_is_dir, mock_exists):
        """Test that exact match returns the environment."""
        config = {
            'environment': {'folder': '/nonexistent'},
            'connections': {'stage': 'ssh://user@host:22', 'production': 'ssh://user@prod:22'}
        }

        mock_exists.return_value = False

        result = resolve_environment('stage', config, '/path/to/mantis.json', 'status')
        assert result == 'stage'

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.is_dir')
    @patch('mantis.managers.CLI.info')
    def test_prefix_match_resolves(self, mock_info, mock_is_dir, mock_exists):
        """Test that prefix match resolves to full environment name."""
        config = {
            'environment': {'folder': '/nonexistent'},
            'connections': {'production': 'ssh://user@prod:22'}
        }

        mock_exists.return_value = False

        result = resolve_environment('prod', config, '/path/to/mantis.json', 'status')
        assert result == 'production'
        mock_info.assert_called()

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.is_dir')
    @patch('mantis.managers.CLI.error')
    def test_ambiguous_prefix_raises_error(self, mock_error, mock_is_dir, mock_exists):
        """Test that ambiguous prefix raises error."""
        config = {
            'environment': {'folder': '/nonexistent'},
            'connections': {
                'production-eu': 'ssh://user@eu:22',
                'production-us': 'ssh://user@us:22'
            }
        }

        mock_exists.return_value = False

        resolve_environment('production', config, '/path/to/mantis.json', 'status')

        mock_error.assert_called_once()
        call_args = mock_error.call_args[0][0]
        assert 'Ambiguous' in call_args
        assert 'production' in call_args

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.is_dir')
    @patch('mantis.managers.CLI.error')
    def test_no_match_raises_error(self, mock_error, mock_is_dir, mock_exists):
        """Test that no match raises error."""
        config = {
            'environment': {'folder': '/nonexistent'},
            'connections': {'stage': 'ssh://user@host:22'}
        }

        mock_exists.return_value = False

        resolve_environment('nonexistent', config, '/path/to/mantis.json', 'status')

        mock_error.assert_called_once()
        call_args = mock_error.call_args[0][0]
        assert 'not found' in call_args
        assert 'nonexistent' in call_args

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.is_dir')
    @patch('pathlib.Path.iterdir')
    def test_secrets_command_uses_folder_envs(
        self, mock_iterdir, mock_is_dir, mock_exists
    ):
        """Test that secrets commands use folder-based environments."""
        config = {
            'environment': {'folder': '<MANTIS>/../environments'},
            'connections': {'stage': 'ssh://user@host:22'}
        }

        mock_exists.return_value = True
        mock_is_dir.return_value = True

        mock_test = MagicMock()
        mock_test.name = 'test'
        mock_test.is_dir.return_value = True

        mock_iterdir.return_value = [mock_test]

        result = resolve_environment('test', config, '/path/to/mantis.json', 'show-env')
        assert result == 'test'


class TestLocalCommands:
    """build and push run against the local docker daemon, so they need no connection."""

    @staticmethod
    def _config():
        return {
            'environment': {'folder': '<MANTIS>/../environments'},
            'connections': {'stage': 'ssh://user@host:22'}
        }

    @staticmethod
    def _folder_envs(mock_iterdir, mock_is_dir, mock_exists, names):
        mock_exists.return_value = True
        mock_is_dir.return_value = True

        entries = []
        for name in names:
            entry = MagicMock()
            entry.name = name
            entry.is_dir.return_value = True
            entries.append(entry)

        mock_iterdir.return_value = entries

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.is_dir')
    @patch('pathlib.Path.iterdir')
    def test_resolves_folder_only_environment(self, mock_iterdir, mock_is_dir, mock_exists):
        """An environment with files but no connection is enough to build an image."""
        self._folder_envs(mock_iterdir, mock_is_dir, mock_exists, ['test', 'stage'])

        assert resolve_environment('test', self._config(), '/path/to/mantis.json', 'build') == 'test'

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.is_dir')
    @patch('pathlib.Path.iterdir')
    def test_resolves_connection_environment(self, mock_iterdir, mock_is_dir, mock_exists):
        """Connections keep working for build, even without an environment folder."""
        self._folder_envs(mock_iterdir, mock_is_dir, mock_exists, ['test'])

        assert resolve_environment('stage', self._config(), '/path/to/mantis.json', 'push') == 'stage'

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.is_dir')
    @patch('pathlib.Path.iterdir')
    def test_validation_accepts_folder_only_environment(self, mock_iterdir, mock_is_dir, mock_exists):
        """Building an environment without a connection is not an error."""
        self._folder_envs(mock_iterdir, mock_is_dir, mock_exists, ['test'])

        # Should not raise any error
        validate_environment_for_commands(
            'test', self._config(), '/path/to/mantis.json', ['build', 'push']
        )

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.is_dir')
    @patch('pathlib.Path.iterdir')
    @patch('mantis.managers.CLI.error')
    def test_deploying_that_environment_still_fails(
        self, mock_error, mock_iterdir, mock_is_dir, mock_exists
    ):
        """A connection is still required for commands which talk to a server."""
        self._folder_envs(mock_iterdir, mock_is_dir, mock_exists, ['test'])

        validate_environment_for_commands(
            'test', self._config(), '/path/to/mantis.json', ['deploy']
        )

        mock_error.assert_called_once()
        assert 'deploy' in mock_error.call_args[0][0]

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.is_dir')
    @patch('pathlib.Path.iterdir')
    @patch('mantis.managers.CLI.error')
    def test_unknown_environment_still_fails(
        self, mock_error, mock_iterdir, mock_is_dir, mock_exists
    ):
        """An environment which is neither a folder nor a connection is rejected."""
        self._folder_envs(mock_iterdir, mock_is_dir, mock_exists, ['test'])

        validate_environment_for_commands(
            'preview', self._config(), '/path/to/mantis.json', ['build']
        )

        mock_error.assert_called_once()
        assert 'preview' in mock_error.call_args[0][0]


class TestSecretsCommandsConstant:
    """Tests for SECRETS_COMMANDS constant in managers module."""

    def test_contains_expected_commands(self):
        """Test that SECRETS_COMMANDS contains all expected commands."""
        expected = {'show-env', 'encrypt-env', 'decrypt-env', 'check-env'}
        assert SECRETS_COMMANDS == expected

    def test_matches_config_module(self):
        """Test that managers SECRETS_COMMANDS matches config module."""
        from mantis.config import SECRETS_COMMANDS as CONFIG_SECRETS_COMMANDS
        assert SECRETS_COMMANDS == CONFIG_SECRETS_COMMANDS


class TestResolveContainers:
    """Tests for resolving container names from container or service names."""

    def _manager(self, containers, services, project='itfitness', compose_services=None):
        manager = BaseManager.__new__(BaseManager)
        manager.get_containers = lambda *args, **kwargs: list(containers)
        manager.services = lambda *args, **kwargs: list(services)
        manager.get_project_by_service = lambda service: project
        manager.project_services = lambda: {project: list(services)}
        manager.compose_config = {'services': compose_services or {}}
        return manager

    def test_exact_container_name_has_priority(self):
        """A container named exactly like the argument wins over the service lookup."""
        manager = self._manager(['itfitness-app', 'app'], ['app'])

        assert manager.resolve_containers(['app']) == ['app']

    def test_service_name_resolves_to_container(self):
        """Service name is prefixed with the project name."""
        manager = self._manager(['itfitness-app', 'itfitness-db'], ['app', 'db'])

        assert manager.resolve_containers(['app']) == ['itfitness-app']

    def test_service_name_resolves_to_scaled_containers(self):
        """All containers of a scaled service are resolved."""
        manager = self._manager(['itfitness-app-1', 'itfitness-app-2'], ['app'])

        assert manager.resolve_containers(['app']) == ['itfitness-app-1', 'itfitness-app-2']

    def test_service_name_does_not_match_similar_services(self):
        """Service "app" must not pull in containers of service "app-worker"."""
        manager = self._manager(['itfitness-app', 'itfitness-app-worker'], ['app', 'app-worker'])

        assert manager.resolve_containers(['app']) == ['itfitness-app']

    def test_explicit_container_name_of_service_is_used(self):
        """Service defining its own container_name is resolved to that name."""
        manager = self._manager(
            ['legacy-app'],
            ['app'],
            compose_services={'app': {'container_name': 'legacy-app'}},
        )

        assert manager.resolve_containers(['app']) == ['legacy-app']

    def test_common_name_of_numbered_services_resolves(self):
        """"htmltopdf" matches containers of services "htmltopdf-1" and "htmltopdf-2"."""
        manager = self._manager(
            ['itfitness-htmltopdf-1', 'itfitness-htmltopdf-2', 'itfitness-app'],
            ['htmltopdf-1', 'htmltopdf-2', 'app'],
            compose_services={
                'htmltopdf-1': {'container_name': 'itfitness-htmltopdf-1'},
                'htmltopdf-2': {'container_name': 'itfitness-htmltopdf-2'},
            },
        )

        assert manager.resolve_containers(['htmltopdf']) == ['itfitness-htmltopdf-1', 'itfitness-htmltopdf-2']

    def test_numbered_service_still_resolves_to_its_own_container(self):
        """The numbered service name keeps resolving to a single container."""
        manager = self._manager(
            ['itfitness-htmltopdf-1', 'itfitness-htmltopdf-2'],
            ['htmltopdf-1', 'htmltopdf-2'],
            compose_services={
                'htmltopdf-1': {'container_name': 'itfitness-htmltopdf-1'},
                'htmltopdf-2': {'container_name': 'itfitness-htmltopdf-2'},
            },
        )

        assert manager.resolve_containers(['htmltopdf-2']) == ['itfitness-htmltopdf-2']

    def test_unknown_name_is_kept_as_given(self):
        """Names which are neither a container nor a service are passed to docker untouched."""
        manager = self._manager(['itfitness-app'], ['app'])

        assert manager.resolve_containers(['whatever']) == ['whatever']

    def test_multiple_names_are_deduplicated(self):
        """Service name and its container name resolve to a single container."""
        manager = self._manager(['itfitness-app', 'itfitness-db'], ['app', 'db'])

        assert manager.resolve_containers(['app', 'itfitness-app', 'db']) == ['itfitness-app', 'itfitness-db']

    @patch('mantis.managers.CLI.warning')
    def test_resolve_container_returns_single_name(self, mock_warning):
        """Commands operating on one container get one container name."""
        manager = self._manager(['itfitness-app', 'itfitness-db'], ['app', 'db'])

        assert manager.resolve_container('app') == 'itfitness-app'
        mock_warning.assert_not_called()

    @patch('mantis.managers.CLI.warning')
    def test_resolve_container_warns_on_multiple_matches(self, mock_warning):
        """A scaled service picks the first container and warns about the rest."""
        manager = self._manager(['itfitness-app-1', 'itfitness-app-2'], ['app'])

        assert manager.resolve_container('app') == 'itfitness-app-1'
        mock_warning.assert_called_once()

    def test_resolve_container_accepts_prefetched_containers(self):
        """Callers which already listed containers do not trigger another docker call."""
        manager = self._manager([], ['app'])
        manager.get_containers = lambda *args, **kwargs: pytest.fail('containers listed again')

        assert manager.resolve_container('app', ['itfitness-app']) == 'itfitness-app'


class TestQuietProgress:
    """Layer progress is repainted in place, which only works on a terminal."""

    @staticmethod
    def _manager():
        manager = BaseManager.__new__(BaseManager)
        manager.commands = []
        manager.docker_compose = lambda command, **kwargs: manager.commands.append(
            ' '.join(command.split())
        )
        return manager

    @patch('sys.stdout', new_callable=MagicMock)
    def test_push_and_pull_are_quiet_off_a_terminal(self, mock_stdout):
        """A log file or a CI pipe would otherwise get every progress event as its own line."""
        mock_stdout.isatty.return_value = False
        manager = self._manager()

        manager.push()
        manager.pull()

        assert manager.commands == ['push --quiet', 'pull --quiet']

    @patch('sys.stdout', new_callable=MagicMock)
    def test_push_and_pull_keep_progress_on_a_terminal(self, mock_stdout):
        """Interactively the progress is the point, so nothing changes."""
        mock_stdout.isatty.return_value = True
        manager = self._manager()

        manager.push(['app'])
        manager.pull(['app'])

        assert manager.commands == ['push app', 'pull app']
