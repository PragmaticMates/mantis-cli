"""Tests for command_line module - argument parsing and command chaining."""
import pytest
import sys
from unittest.mock import patch, MagicMock

from mantis.command_line import (
    split_args,
    parse_global_options,
    COMMAND_SEPARATOR,
)


class TestSplitArgs:
    """Tests for split_args function."""

    def test_chained_commands_simple(self):
        """Test basic command chaining with + separator."""
        args = ['-e', 'stage', 'build', '+', 'push', '+', 'deploy']
        global_opts, cmd_groups = split_args(args)

        assert global_opts == ['-e', 'stage']
        assert cmd_groups == [['build'], ['push'], ['deploy']]

    def test_chained_commands_with_args(self):
        """Test command chaining where first command has arguments."""
        args = ['-e', 'stage', 'build', 'web', 'api', '+', 'push', '+', 'deploy']
        global_opts, cmd_groups = split_args(args)

        assert global_opts == ['-e', 'stage']
        assert cmd_groups == [['build', 'web', 'api'], ['push'], ['deploy']]

    def test_single_command(self):
        """Test single command without chaining."""
        args = ['-e', 'prod', 'status']
        global_opts, cmd_groups = split_args(args)

        assert global_opts == ['-e', 'prod']
        assert cmd_groups == [['status']]

    def test_single_command_with_args(self):
        """Test single command with arguments."""
        args = ['-e', 'prod', 'build', 'web', 'api']
        global_opts, cmd_groups = split_args(args)

        assert global_opts == ['-e', 'prod']
        assert cmd_groups == [['build', 'web', 'api']]

    def test_command_with_options(self):
        """Test command with its own options."""
        args = ['-e', 'prod', 'deploy', '--dirty']
        global_opts, cmd_groups = split_args(args)

        assert global_opts == ['-e', 'prod']
        assert cmd_groups == [['deploy', '--dirty']]

    def test_chained_commands_with_options(self):
        """Test chained commands where commands have options."""
        args = ['-e', 'prod', 'build', '--no-cache', '+', 'deploy', '--dirty']
        global_opts, cmd_groups = split_args(args)

        assert global_opts == ['-e', 'prod']
        assert cmd_groups == [['build', '--no-cache'], ['deploy', '--dirty']]

    def test_help_flag(self):
        """Test command with --help flag."""
        args = ['build', '--help']
        global_opts, cmd_groups = split_args(args)

        assert global_opts == []
        assert cmd_groups == [['build', '--help']]

    def test_global_help_flag(self):
        """Test global --help flag."""
        args = ['--help']
        global_opts, cmd_groups = split_args(args)

        assert global_opts == ['--help']
        assert cmd_groups == []

    def test_version_flag(self):
        """Test --version flag."""
        args = ['--version']
        global_opts, cmd_groups = split_args(args)

        assert global_opts == ['--version']
        assert cmd_groups == []

    def test_dry_run_flag(self):
        """Test -n/--dry-run flag."""
        args = ['-n', '-e', 'prod', 'deploy']
        global_opts, cmd_groups = split_args(args)

        assert global_opts == ['-n', '-e', 'prod']
        assert cmd_groups == [['deploy']]

    def test_mode_option(self):
        """Test --mode option."""
        args = ['-e', 'prod', '-m', 'ssh', 'status']
        global_opts, cmd_groups = split_args(args)

        assert global_opts == ['-e', 'prod', '-m', 'ssh']
        assert cmd_groups == [['status']]

    def test_long_options(self):
        """Test long option names."""
        args = ['--env', 'prod', '--mode', 'host', '--dry-run', 'status']
        global_opts, cmd_groups = split_args(args)

        assert global_opts == ['--env', 'prod', '--mode', 'host', '--dry-run']
        assert cmd_groups == [['status']]

    def test_empty_args(self):
        """Test empty arguments."""
        global_opts, cmd_groups = split_args([])

        assert global_opts == []
        assert cmd_groups == []

    def test_only_global_opts(self):
        """Test only global options, no command."""
        args = ['-e', 'prod']
        global_opts, cmd_groups = split_args(args)

        assert global_opts == ['-e', 'prod']
        assert cmd_groups == []

    def test_multiple_separators(self):
        """Test handling of multiple consecutive separators."""
        args = ['build', '+', '+', 'push']
        global_opts, cmd_groups = split_args(args)

        assert global_opts == []
        assert cmd_groups == [['build'], ['push']]

    def test_separator_at_end(self):
        """Test separator at the end."""
        args = ['-e', 'prod', 'build', '+']
        global_opts, cmd_groups = split_args(args)

        assert global_opts == ['-e', 'prod']
        assert cmd_groups == [['build']]

    def test_shortcut_commands(self):
        """Test shortcut command names."""
        args = ['-e', 'prod', 'b', '+', 'p', '+', 'd']
        global_opts, cmd_groups = split_args(args)

        assert global_opts == ['-e', 'prod']
        assert cmd_groups == [['b'], ['p'], ['d']]


class TestParseGlobalOptions:
    """Tests for parse_global_options function (used only for multi-command chaining)."""

    def test_environment_short(self):
        """Test -e option."""
        opts = parse_global_options(['-e', 'production'])

        assert opts['env'] == 'production'
        assert opts['mode'] == 'remote'
        assert opts['dry_run'] is False

    def test_environment_long(self):
        """Test --env option."""
        opts = parse_global_options(['--env', 'staging'])

        assert opts['env'] == 'staging'

    def test_mode_short(self):
        """Test -m option."""
        opts = parse_global_options(['-m', 'ssh'])

        assert opts['mode'] == 'ssh'

    def test_mode_long(self):
        """Test --mode option."""
        opts = parse_global_options(['--mode', 'host'])

        assert opts['mode'] == 'host'

    def test_dry_run_short(self):
        """Test -n option."""
        opts = parse_global_options(['-n'])

        assert opts['dry_run'] is True

    def test_dry_run_long(self):
        """Test --dry-run option."""
        opts = parse_global_options(['--dry-run'])

        assert opts['dry_run'] is True

    def test_all_options(self):
        """Test all options combined."""
        opts = parse_global_options(['-e', 'prod', '-m', 'ssh', '-n'])

        assert opts['env'] == 'prod'
        assert opts['mode'] == 'ssh'
        assert opts['dry_run'] is True

    def test_defaults(self):
        """Test default values."""
        opts = parse_global_options([])

        assert opts['env'] is None
        assert opts['mode'] == 'remote'
        assert opts['dry_run'] is False

    def test_unknown_options_ignored(self):
        """Test that unknown options are ignored."""
        opts = parse_global_options(['--unknown', '-x', '-e', 'prod'])

        assert opts['env'] == 'prod'


class TestCommandSeparator:
    """Tests for command separator constant."""

    def test_separator_is_plus(self):
        """Verify the separator is '+'."""
        assert COMMAND_SEPARATOR == '+'
