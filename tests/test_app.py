"""Tests for the command decorator - passing unknown options on to the wrapped tool."""
import typer

import mantis.command_line  # noqa: F401  - importing registers every command and shortcut
from mantis.app import CONTEXT_SETTINGS, _DEFERRED_SHORTCUTS, app, command, register_shortcuts

# Commands whose arguments are a command line for docker, compose or Django
FORWARDING_COMMANDS = ['up', 'down', 'run', 'exec', 'exec-it', 'manage']

# Commands whose arguments are container or service names, where an unknown option is a typo
NAME_TAKING_COMMANDS = ['stop', 'start', 'kill', 'remove', 'build', 'pull', 'push']


def commands():
    return typer.main.get_command(app).commands


class TestPassthrough:
    """Tests for which commands accept unknown options."""

    def test_forwarding_commands_accept_unknown_options(self):
        """Without this, `manage check --deploy` fails with "No such option: --deploy"."""
        registered = commands()

        for name in FORWARDING_COMMANDS:
            assert registered[name].context_settings.get('ignore_unknown_options') is True, name

    def test_name_taking_commands_still_reject_unknown_options(self):
        """`build --no-cache` should fail rather than look for a service called --no-cache."""
        registered = commands()

        for name in NAME_TAKING_COMMANDS:
            assert registered[name].context_settings.get('ignore_unknown_options') is not True, name

    def test_forwarding_commands_keep_the_help_width(self):
        """Settings on a command replace the app-level ones, so they have to carry them."""
        registered = commands()
        expected = CONTEXT_SETTINGS['max_content_width']

        for name in FORWARDING_COMMANDS:
            assert registered[name].context_settings.get('max_content_width') == expected, name

    def test_shortcuts_carry_the_passthrough_flag(self):
        """Shortcut registration is deferred, so the flag has to travel with the entry."""
        for entry in _DEFERRED_SHORTCUTS:
            assert len(entry) == 4, entry
            assert isinstance(entry[3], bool), entry

    def test_shortcut_of_a_forwarding_command_also_passes_through(self):
        """A shortcut is registered as a command of its own and needs the same settings.

        No forwarding command has a shortcut today, so this registers one to check the
        mechanism rather than the current set of commands - otherwise the guarantee would
        only break the day someone adds a shortcut to `up`.
        """
        saved = list(_DEFERRED_SHORTCUTS)
        saved_commands = list(app.registered_commands)

        try:
            _DEFERRED_SHORTCUTS.clear()

            @command(name='passthrough-probe', shortcut='ptp', passthrough=True)
            def probe():
                """Probe"""

            register_shortcuts()

            assert commands()['ptp'].context_settings.get('ignore_unknown_options') is True
        finally:
            _DEFERRED_SHORTCUTS.clear()
            _DEFERRED_SHORTCUTS.extend(saved)
            app.registered_commands = saved_commands
