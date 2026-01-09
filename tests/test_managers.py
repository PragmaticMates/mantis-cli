"""Tests for managers module - environment validation and resolution."""
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from mantis.managers import (
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
