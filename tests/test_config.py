"""Tests for config module - config analysis and environment matching."""
import pytest
from dataclasses import field
from unittest.mock import patch, MagicMock
from pathlib import Path

from mantis.config import (
    ConfigAnalysis,
    analyze_config,
    env_matches_for_command,
    env_matches_all_commands,
    get_valid_envs_for_commands,
    format_env_list,
    get_config_dir,
    SECRETS_COMMANDS,
    DEFAULT_ENV_FOLDER,
)


class TestConfigAnalysis:
    """Tests for ConfigAnalysis dataclass."""

    def test_default_values(self):
        """Test default values are set correctly."""
        analysis = ConfigAnalysis(path='/path/to/config.json', index=0)

        assert analysis.path == '/path/to/config.json'
        assert analysis.index == 0
        assert analysis.is_single_connection is False
        assert analysis.folder_envs == []
        assert analysis.connection_envs == []
        assert analysis.has_match is False

    def test_connection_envs_with_local_adds_local_first(self):
        """Test that 'local' is added at the beginning of connection envs."""
        analysis = ConfigAnalysis(
            path='/path/to/config.json',
            index=0,
            connection_envs=['stage', 'production']
        )

        assert analysis.connection_envs_with_local == ['local', 'stage', 'production']

    def test_connection_envs_with_local_no_duplicate(self):
        """Test that 'local' is not duplicated if already present."""
        analysis = ConfigAnalysis(
            path='/path/to/config.json',
            index=0,
            connection_envs=['local', 'stage', 'production']
        )

        # 'local' should appear only once at the beginning
        result = analysis.connection_envs_with_local
        assert result.count('local') == 1
        assert result[0] == 'local'

    def test_connection_envs_with_local_empty_list(self):
        """Test connection_envs_with_local with empty connection_envs."""
        analysis = ConfigAnalysis(path='/path/to/config.json', index=0)

        assert analysis.connection_envs_with_local == ['local']


class TestEnvMatchesForCommand:
    """Tests for env_matches_for_command function."""

    def test_secrets_command_matches_folder_env(self):
        """Test that secrets commands match folder-based environments."""
        analysis = ConfigAnalysis(
            path='/path/to/config.json',
            index=0,
            folder_envs=['local', 'test', 'production']
        )

        assert env_matches_for_command('local', 'show-env', analysis) is True
        assert env_matches_for_command('test', 'encrypt-env', analysis) is True
        assert env_matches_for_command('production', 'decrypt-env', analysis) is True

    def test_secrets_command_no_match_non_folder_env(self):
        """Test that secrets commands don't match non-folder environments."""
        analysis = ConfigAnalysis(
            path='/path/to/config.json',
            index=0,
            folder_envs=['test'],
            connection_envs=['stage', 'production']
        )

        assert env_matches_for_command('stage', 'show-env', analysis) is False
        assert env_matches_for_command('production', 'encrypt-env', analysis) is False

    def test_secrets_command_prefix_match(self):
        """Test that secrets commands match by prefix."""
        analysis = ConfigAnalysis(
            path='/path/to/config.json',
            index=0,
            folder_envs=['production-eu', 'production-us']
        )

        assert env_matches_for_command('prod', 'show-env', analysis) is True

    def test_other_command_matches_connection_env(self):
        """Test that non-secrets commands match connection-based environments."""
        analysis = ConfigAnalysis(
            path='/path/to/config.json',
            index=0,
            connection_envs=['stage', 'production']
        )

        assert env_matches_for_command('stage', 'status', analysis) is True
        assert env_matches_for_command('production', 'deploy', analysis) is True

    def test_other_command_always_matches_local(self):
        """Test that non-secrets commands always match 'local'."""
        analysis = ConfigAnalysis(
            path='/path/to/config.json',
            index=0,
            connection_envs=['stage']
        )

        assert env_matches_for_command('local', 'status', analysis) is True
        assert env_matches_for_command('local-dev', 'deploy', analysis) is True

    def test_other_command_prefix_match(self):
        """Test that non-secrets commands match by prefix."""
        analysis = ConfigAnalysis(
            path='/path/to/config.json',
            index=0,
            connection_envs=['production-eu', 'production-us']
        )

        assert env_matches_for_command('prod', 'status', analysis) is True


class TestEnvMatchesAllCommands:
    """Tests for env_matches_all_commands function."""

    def test_empty_commands_returns_true(self):
        """Test that empty command list returns True."""
        analysis = ConfigAnalysis(path='/path/to/config.json', index=0)

        assert env_matches_all_commands('any-env', [], analysis) is True

    def test_single_command_match(self):
        """Test matching with a single command."""
        analysis = ConfigAnalysis(
            path='/path/to/config.json',
            index=0,
            folder_envs=['test'],
            connection_envs=['stage']
        )

        assert env_matches_all_commands('test', ['show-env'], analysis) is True
        assert env_matches_all_commands('stage', ['status'], analysis) is True

    def test_multiple_commands_all_match(self):
        """Test that environment must match ALL commands."""
        analysis = ConfigAnalysis(
            path='/path/to/config.json',
            index=0,
            folder_envs=['local', 'test'],
            connection_envs=['local', 'stage']
        )

        # 'local' exists in both folder_envs and connection_envs
        assert env_matches_all_commands('local', ['show-env', 'status'], analysis) is True

    def test_multiple_commands_partial_match_fails(self):
        """Test that partial match fails for multiple commands."""
        analysis = ConfigAnalysis(
            path='/path/to/config.json',
            index=0,
            folder_envs=['test'],
            connection_envs=['stage']
        )

        # 'test' is in folder_envs but not in connection_envs (no 'local' prefix)
        assert env_matches_all_commands('test', ['show-env', 'status'], analysis) is False
        # 'stage' is in connection_envs but not in folder_envs
        assert env_matches_all_commands('stage', ['show-env', 'status'], analysis) is False


class TestGetValidEnvsForCommands:
    """Tests for get_valid_envs_for_commands function."""

    def test_empty_commands_returns_empty_set(self):
        """Test that empty command list returns empty set."""
        analysis = ConfigAnalysis(
            path='/path/to/config.json',
            index=0,
            folder_envs=['test'],
            connection_envs=['stage']
        )

        assert get_valid_envs_for_commands([], analysis) == set()

    def test_secrets_command_only_returns_folder_envs(self):
        """Test that secrets commands only return folder environments."""
        analysis = ConfigAnalysis(
            path='/path/to/config.json',
            index=0,
            folder_envs=['local', 'test'],
            connection_envs=['stage', 'production']
        )

        result = get_valid_envs_for_commands(['show-env'], analysis)
        assert result == {'local', 'test'}

    def test_other_command_only_returns_connections_with_local(self):
        """Test that non-secrets commands return connections + local."""
        analysis = ConfigAnalysis(
            path='/path/to/config.json',
            index=0,
            folder_envs=['test'],
            connection_envs=['stage', 'production']
        )

        result = get_valid_envs_for_commands(['status'], analysis)
        assert result == {'local', 'stage', 'production'}

    def test_mixed_commands_returns_intersection(self):
        """Test that mixed commands return intersection of valid envs."""
        analysis = ConfigAnalysis(
            path='/path/to/config.json',
            index=0,
            folder_envs=['local', 'test'],
            connection_envs=['stage', 'production']
        )

        # Only 'local' is in both folder_envs and connection_envs_with_local
        result = get_valid_envs_for_commands(['show-env', 'status'], analysis)
        assert result == {'local'}

    def test_mixed_commands_no_overlap(self):
        """Test mixed commands with no overlapping environments."""
        analysis = ConfigAnalysis(
            path='/path/to/config.json',
            index=0,
            folder_envs=['test'],  # no 'local'
            connection_envs=['stage']  # no 'test'
        )

        # No environment satisfies both commands
        result = get_valid_envs_for_commands(['show-env', 'status'], analysis)
        assert result == set()


class TestFormatEnvList:
    """Tests for format_env_list function."""

    def test_empty_list(self):
        """Test formatting empty environment list."""
        result = format_env_list([], None)
        assert result == '[dim]none[/dim]'

    def test_no_match_all_yellow(self):
        """Test formatting with no matching environment."""
        result = format_env_list(['stage', 'production'], None)
        assert '[yellow]stage[/yellow]' in result
        assert '[yellow]production[/yellow]' in result
        assert '[green]' not in result

    def test_exact_match_green(self):
        """Test that exact match is highlighted in green."""
        result = format_env_list(['stage', 'production'], 'stage')
        assert '[green]stage[/green]' in result
        assert '[yellow]production[/yellow]' in result

    def test_prefix_match_green(self):
        """Test that prefix match is highlighted in green."""
        result = format_env_list(['production-eu', 'production-us', 'stage'], 'prod')
        assert '[green]production-eu[/green]' in result
        assert '[green]production-us[/green]' in result
        assert '[yellow]stage[/yellow]' in result


class TestGetConfigDir:
    """Tests for get_config_dir function."""

    def test_returns_parent_directory(self):
        """Test that function returns parent directory of config file."""
        result = get_config_dir('/path/to/configs/mantis.json')
        assert result == '/path/to/configs'

    def test_current_directory(self):
        """Test with config file in current directory."""
        result = get_config_dir('mantis.json')
        assert result == '.'


class TestSecretsCommands:
    """Tests for SECRETS_COMMANDS constant."""

    def test_contains_expected_commands(self):
        """Test that SECRETS_COMMANDS contains all expected commands."""
        expected = {'show-env', 'encrypt-env', 'decrypt-env', 'check-env'}
        assert SECRETS_COMMANDS == expected

    def test_is_set(self):
        """Test that SECRETS_COMMANDS is a set for O(1) lookup."""
        assert isinstance(SECRETS_COMMANDS, set)


class TestDefaultEnvFolder:
    """Tests for DEFAULT_ENV_FOLDER constant."""

    def test_matches_schema_default(self):
        """Test that DEFAULT_ENV_FOLDER matches the schema default."""
        from mantis.schema import EnvironmentConfig
        schema_default = EnvironmentConfig.model_fields['folder'].default
        assert DEFAULT_ENV_FOLDER == schema_default

    def test_contains_mantis_placeholder(self):
        """Test that DEFAULT_ENV_FOLDER contains the <MANTIS> placeholder."""
        assert '<MANTIS>' in DEFAULT_ENV_FOLDER

    def test_expected_value(self):
        """Test the expected default value."""
        assert DEFAULT_ENV_FOLDER == '<MANTIS>/../environments'


class TestAnalyzeConfig:
    """Tests for analyze_config function."""

    @patch('mantis.config.load_config')
    def test_single_connection_mode(self, mock_load_config):
        """Test analyzing a single connection config."""
        mock_load_config.return_value = {
            'connection': 'ssh://user@host:22'
        }

        analysis = analyze_config('/path/to/mantis.json', 0)

        assert analysis.is_single_connection is True
        assert analysis.folder_envs == []
        assert analysis.connection_envs == []

    @patch('mantis.config.load_config')
    def test_multi_environment_mode_with_connections(self, mock_load_config):
        """Test analyzing a multi-environment config with connections."""
        mock_load_config.return_value = {
            'connections': {
                'stage': 'ssh://user@stage:22',
                'production': 'ssh://user@prod:22'
            },
            'environment': {
                'folder': '/nonexistent/path'
            }
        }

        analysis = analyze_config('/path/to/mantis.json', 1)

        assert analysis.is_single_connection is False
        assert analysis.connection_envs == ['stage', 'production']
        assert analysis.index == 1

    @patch('mantis.config.load_config')
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.is_dir')
    @patch('pathlib.Path.iterdir')
    def test_multi_environment_mode_with_folder_envs(
        self, mock_iterdir, mock_is_dir, mock_exists, mock_load_config
    ):
        """Test analyzing a config with folder-based environments."""
        mock_load_config.return_value = {
            'connections': {},
            'environment': {
                'folder': '<MANTIS>/../environments'
            }
        }
        mock_exists.return_value = True
        mock_is_dir.return_value = True

        # Mock directory entries
        mock_dir1 = MagicMock()
        mock_dir1.name = 'local'
        mock_dir1.is_dir.return_value = True

        mock_dir2 = MagicMock()
        mock_dir2.name = 'test'
        mock_dir2.is_dir.return_value = True

        mock_iterdir.return_value = [mock_dir1, mock_dir2]

        analysis = analyze_config('/path/to/mantis.json', 0)

        assert analysis.is_single_connection is False
        assert 'local' in analysis.folder_envs
        assert 'test' in analysis.folder_envs
