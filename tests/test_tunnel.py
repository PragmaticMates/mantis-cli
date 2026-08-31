"""Tests for the SSH tunnel forwarding the remote docker socket."""
import subprocess
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from mantis.managers import BaseManager


def _manager(
    connection='ssh://deploy@example.com:2222',
    tunnel=None,
    mode='remote',
    use_tunnel=True,
    dry_run=False,
    environment_id='production',
):
    """A manager wired for connection resolution only, without running __init__."""
    manager = BaseManager.__new__(BaseManager)
    manager.config = {
        'project_path': '~/app',
        'tunnel': {'enabled': False} if tunnel is None else tunnel,
    }
    manager.connection = connection
    manager.mode = mode
    manager.dry_run = dry_run
    manager.single_connection_mode = False
    manager.environment = SimpleNamespace(id=environment_id)

    manager.use_tunnel = use_tunnel
    manager._tunnel_lock = threading.Lock()
    manager._tunnel_socket = None
    manager._tunnel_control_socket = None
    manager._tunnel_dir = None
    manager._tunnel_failed = False

    return manager


@pytest.fixture
def ssh(tmp_path):
    """Mocks the ssh subprocess and pins the tunnel directory into tmp_path."""
    tunnel_dir = tmp_path / 'mantis-test'
    tunnel_dir.mkdir()

    result = SimpleNamespace(returncode=0, output='', stdout='')

    def fake_run(command, **kwargs):
        # the master writes to a file, not to a pipe (see start_tunnel)
        output = kwargs.get('stdout')

        if hasattr(output, 'write'):
            output.write(result.output)

        return MagicMock(returncode=result.returncode, stdout=result.stdout, stderr='')

    with patch('mantis.managers.subprocess.run', side_effect=fake_run) as run, \
            patch('mantis.managers.tempfile.mkdtemp', return_value=str(tunnel_dir)), \
            patch('mantis.managers.atexit.register') as register:
        yield SimpleNamespace(run=run, register=register, dir=tunnel_dir, result=result)


class TestTunnelDisabled:
    """Without the tunnel, every docker command keeps its own ssh:// connection."""

    def test_disabled_by_config(self, ssh):
        manager = _manager(tunnel={'enabled': False})

        assert manager.docker_connection == 'DOCKER_HOST="ssh://deploy@example.com:2222"'
        ssh.run.assert_not_called()

    def test_disabled_by_no_tunnel_flag(self, ssh):
        manager = _manager(tunnel={'enabled': True}, use_tunnel=False)

        assert manager.docker_connection == 'DOCKER_HOST="ssh://deploy@example.com:2222"'
        ssh.run.assert_not_called()

    @pytest.mark.parametrize('mode', ['ssh', 'host'])
    def test_only_remote_mode_is_tunnelled(self, ssh, mode):
        manager = _manager(tunnel={'enabled': True}, mode=mode)

        assert manager.ensure_tunnel() is None
        ssh.run.assert_not_called()

    def test_local_environment_is_untouched(self, ssh):
        manager = _manager(tunnel={'enabled': True}, environment_id='local')

        assert manager.docker_connection == ''
        ssh.run.assert_not_called()

    def test_context_connection_is_untouched(self, ssh):
        manager = _manager(connection='context://production', tunnel={'enabled': True})

        assert manager.docker_connection == 'DOCKER_CONTEXT=production'
        ssh.run.assert_not_called()


class TestTunnelEnabled:
    """With the tunnel, all docker commands share a single ssh connection."""

    def test_docker_host_points_at_the_forwarded_socket(self, ssh):
        manager = _manager(tunnel={'enabled': True})

        assert manager.docker_connection == f'DOCKER_HOST="unix://{ssh.dir}/docker.sock"'

    def test_ssh_master_command(self, ssh):
        manager = _manager(tunnel={'enabled': True})
        manager.ensure_tunnel()

        command = ssh.run.call_args[0][0]

        assert command[0] == 'ssh'
        # backgrounded master with a control socket we can close deterministically
        assert '-f' in command and '-N' in command and '-M' in command
        # a refused channel is only reported at verbose level, and only in the log file
        assert '-v' in command
        assert command[command.index('-S') + 1] == f'{ssh.dir}/ssh.ctl'
        # a refused forward must fail loudly instead of yielding a dead socket
        assert 'ExitOnForwardFailure=yes' in command
        assert command[command.index('-L') + 1] == f'{ssh.dir}/docker.sock:/var/run/docker.sock'
        assert command[command.index('-p') + 1] == '2222'
        assert command[-1] == 'deploy@example.com'

    def test_remote_socket_is_configurable(self, ssh):
        manager = _manager(tunnel={'enabled': True, 'remote_socket': '/run/docker.sock'})
        manager.ensure_tunnel()

        command = ssh.run.call_args[0][0]

        assert command[command.index('-L') + 1] == f'{ssh.dir}/docker.sock:/run/docker.sock'

    def test_extra_ssh_options_are_appended(self, ssh):
        manager = _manager(tunnel={'enabled': True, 'ssh_options': ['-o', 'StrictHostKeyChecking=no']})
        manager.ensure_tunnel()

        command = ssh.run.call_args[0][0]

        assert 'StrictHostKeyChecking=no' in command
        # options stay in front of the destination
        assert command.index('StrictHostKeyChecking=no') < command.index('deploy@example.com')

    def test_master_output_is_not_piped(self, ssh):
        """A pipe would never reach EOF, because ssh -f keeps it open in the background."""
        manager = _manager(tunnel={'enabled': True})
        manager.ensure_tunnel()

        kwargs = ssh.run.call_args[1]

        assert 'capture_output' not in kwargs
        assert kwargs['stdout'] is not subprocess.PIPE
        assert hasattr(kwargs['stdout'], 'write')
        assert kwargs['stderr'] is kwargs['stdout']

    def test_connection_is_opened_only_once(self, ssh):
        manager = _manager(tunnel={'enabled': True})

        first = manager.docker_connection
        second = manager.docker_connection

        assert first == second
        assert ssh.run.call_count == 1

    def test_stop_tunnel_closes_master_and_cleans_up(self, ssh):
        manager = _manager(tunnel={'enabled': True})
        manager.ensure_tunnel()

        manager.stop_tunnel()

        command = ssh.run.call_args[0][0]
        assert command == ['ssh', '-S', f'{ssh.dir}/ssh.ctl', '-O', 'exit', 'deploy@example.com']
        assert not ssh.dir.exists()

    def test_stop_tunnel_is_idempotent(self, ssh):
        manager = _manager(tunnel={'enabled': True})
        manager.ensure_tunnel()

        manager.stop_tunnel()
        calls_after_first = ssh.run.call_count
        manager.stop_tunnel()

        assert ssh.run.call_count == calls_after_first


class TestTunnelAutoDetection:
    """An unset "enabled" means: use the tunnel wherever it happens to work."""

    def test_used_when_the_daemon_answers(self, ssh):
        ssh.result.stdout = '24.0.6\n'
        manager = _manager(tunnel={})

        assert manager.docker_connection == f'DOCKER_HOST="unix://{ssh.dir}/docker.sock"'

    def test_missing_tunnel_config_is_also_detected(self, ssh):
        ssh.result.stdout = '24.0.6\n'
        manager = _manager()
        manager.config.pop('tunnel')

        assert manager.docker_connection == f'DOCKER_HOST="unix://{ssh.dir}/docker.sock"'

    def test_falls_back_when_nothing_answers(self, ssh):
        """The forward succeeds even when the remote socket is unreachable."""
        ssh.result.stdout = ''
        manager = _manager(tunnel={})

        with patch('mantis.managers.CLI.warning') as warning:
            assert manager.docker_connection == 'DOCKER_HOST="ssh://deploy@example.com:2222"'

        assert 'did not answer' in warning.call_args[0][0]

    def test_fallback_says_why(self, ssh):
        ssh.result.stdout = ''
        ssh.result.output = 'channel 2: open failed: unknown channel type: unsupported channel type\n'
        manager = _manager(tunnel={})

        with patch('mantis.managers.CLI.warning') as warning:
            manager.docker_connection

        assert 'direct-streamlocal' in warning.call_args[0][0]
        assert 'ControlMaster' in warning.call_args[0][0]

    def test_failed_detection_closes_the_tunnel(self, ssh):
        ssh.result.stdout = ''
        manager = _manager(tunnel={})

        with patch('mantis.managers.CLI.warning'):
            manager.ensure_tunnel()

        assert ssh.run.call_args[0][0][:2] == ['ssh', '-S']
        assert not ssh.dir.exists()

    def test_detection_runs_only_once(self, ssh):
        ssh.result.stdout = ''
        manager = _manager(tunnel={})

        with patch('mantis.managers.CLI.warning'):
            manager.docker_connection
            manager.docker_connection

        # master + probe + close, not a second round
        assert ssh.run.call_count == 3

    def test_says_it_is_checking(self, ssh):
        ssh.result.stdout = '24.0.6\n'
        manager = _manager(tunnel={})

        with patch('mantis.managers.CLI.info') as info, patch('mantis.managers.CLI.success') as success:
            manager.ensure_tunnel()

        assert 'checking' in info.call_args_list[0][0][0]
        assert '24.0.6' in success.call_args[0][0]

    def test_explicitly_enabled_skips_detection(self, ssh):
        """A server known to work must not pay for a probe on every run."""
        manager = _manager(tunnel={'enabled': True})

        with patch('mantis.managers.CLI.info') as info:
            manager.ensure_tunnel()

        commands = [call[0][0] for call in ssh.run.call_args_list]

        assert len(commands) == 1
        assert commands[0][0] == 'ssh'
        assert not any('checking' in call[0][0] for call in info.call_args_list)

    def test_explicitly_disabled_skips_detection(self, ssh):
        manager = _manager(tunnel={'enabled': False})

        assert manager.docker_connection == 'DOCKER_HOST="ssh://deploy@example.com:2222"'
        ssh.run.assert_not_called()


class TestCheckTunnel:
    """check-tunnel tells apart the reasons a tunnel can be unusable."""

    def test_reports_available(self, ssh):
        ssh.result.stdout = '24.0.6\n'
        manager = _manager(tunnel={'enabled': True})

        with patch('mantis.managers.CLI.success') as success:
            assert manager.check_tunnel() is True

        assert '24.0.6' in success.call_args[0][0]

    def test_checks_even_when_disabled_in_config(self, ssh):
        """The point of the command is to answer "would it work", not "is it on"."""
        ssh.result.stdout = '24.0.6\n'
        manager = _manager(tunnel={'enabled': False})

        with patch('mantis.managers.CLI.success'), patch('mantis.managers.CLI.warning') as warning:
            assert manager.check_tunnel() is True

        assert 'disabled' in warning.call_args[0][0]

    def test_closes_the_tunnel_again(self, ssh):
        ssh.result.stdout = '24.0.6\n'
        manager = _manager(tunnel={'enabled': True})

        with patch('mantis.managers.CLI.success'):
            manager.check_tunnel()

        assert ssh.run.call_args[0][0][:2] == ['ssh', '-S']
        assert not ssh.dir.exists()

    def test_refused_forward_points_at_sshd_config(self, ssh):
        ssh.result.returncode = 255
        manager = _manager(tunnel={'enabled': True})

        with patch('mantis.managers.CLI.warning'), patch('mantis.managers.CLI.danger'), \
                patch('mantis.managers.CLI.info') as info:
            assert manager.check_tunnel() is False

        assert 'AllowStreamLocalForwarding' in info.call_args[0][0]

    def test_silent_daemon_points_at_socket_access(self, ssh):
        """The forward works, but nothing answers on the remote socket."""
        ssh.result.stdout = ''
        manager = _manager(tunnel={'enabled': True})

        with patch('mantis.managers.CLI.danger'), patch('mantis.managers.CLI.info') as info:
            assert manager.check_tunnel() is False

        assert 'docker' in info.call_args[0][0]
        assert 'deploy' in info.call_args[0][0]

    def test_debug_chatter_is_not_reported_to_the_user(self, ssh):
        """The master runs with -v, so its log cannot be shown as it is."""
        ssh.result.returncode = 255
        ssh.result.output = (
            'debug1: Connecting to example.com port 2222.\n'
            'ssh: connect to host example.com port 2222: Connection refused\n'
        )
        manager = _manager(tunnel={'enabled': True})

        with patch('mantis.managers.CLI.warning') as warning, patch('mantis.managers.CLI.danger'), \
                patch('mantis.managers.CLI.info'):
            manager.check_tunnel()

        message = warning.call_args[0][0]

        assert 'Connection refused' in message
        assert 'debug1' not in message

    def test_unsupported_channel_points_at_multiplexing(self, ssh):
        """Not every SSH server is OpenSSH: some reject the forward channel outright."""
        ssh.result.stdout = ''
        ssh.result.output = 'channel 2: open failed: unknown channel type: unsupported channel type\n'
        manager = _manager(tunnel={'enabled': True})

        with patch('mantis.managers.CLI.danger'), patch('mantis.managers.CLI.info') as info:
            assert manager.check_tunnel() is False

        message = info.call_args[0][0]

        # no remote_socket can fix this, so the advice must not be about the socket
        assert 'direct-streamlocal' in message
        assert 'ControlMaster' in message
        assert 'docker' not in message.split('ControlMaster')[0]

    def test_prohibited_forward_points_at_sshd_config(self, ssh):
        ssh.result.stdout = ''
        ssh.result.output = 'channel 2: open failed: administratively prohibited: open failed\n'
        manager = _manager(tunnel={'enabled': True})

        with patch('mantis.managers.CLI.danger'), patch('mantis.managers.CLI.info') as info:
            assert manager.check_tunnel() is False

        assert 'AllowStreamLocalForwarding' in info.call_args[0][0]

    def test_reason_is_read_before_the_tunnel_is_removed(self, ssh):
        """The log lives in the tunnel directory, which stop_tunnel deletes."""
        ssh.result.stdout = ''
        ssh.result.output = 'channel 2: open failed: unknown channel type: unsupported channel type\n'
        manager = _manager(tunnel={'enabled': True})

        with patch('mantis.managers.CLI.danger'), patch('mantis.managers.CLI.info') as info:
            manager.check_tunnel()

        assert not ssh.dir.exists()
        assert 'direct-streamlocal' in info.call_args[0][0]

    def test_non_ssh_connection_is_an_error(self, ssh):
        manager = _manager(connection='context://production', tunnel={'enabled': True})

        # CLI.error exits, so nothing is attempted afterwards
        with patch('mantis.managers.CLI.error', side_effect=SystemExit(1)) as error:
            with pytest.raises(SystemExit):
                manager.check_tunnel()

        assert 'ssh://' in error.call_args[0][0]
        ssh.run.assert_not_called()


class TestTunnelDryRun:
    """A dry run prints the ssh command it would run, and connects to nothing."""

    def test_no_connection_is_opened(self, ssh):
        manager = _manager(tunnel={'enabled': True}, dry_run=True)

        with patch('mantis.managers.CLI.warning'):
            manager.ensure_tunnel()

        ssh.run.assert_not_called()
        ssh.register.assert_not_called()
        assert not ssh.dir.exists()

    def test_reported_docker_host_matches_a_real_run(self, ssh):
        manager = _manager(tunnel={'enabled': True}, dry_run=True)

        with patch('mantis.managers.CLI.warning') as warning:
            assert manager.docker_connection == f'DOCKER_HOST="unix://{ssh.dir}/docker.sock"'

        assert warning.call_args[0][0].startswith('[DRY-RUN] ssh -f -N -M')


class TestTunnelFallback:
    """A server refusing the forward must degrade, not break the deploy."""

    def test_falls_back_to_ssh_docker_host(self, ssh):
        ssh.result.returncode = 255
        ssh.result.output = 'forwarding refused'
        manager = _manager(tunnel={'enabled': True})

        with patch('mantis.managers.CLI.warning') as warning:
            assert manager.docker_connection == 'DOCKER_HOST="ssh://deploy@example.com:2222"'
            warning.assert_called_once()

        assert 'forwarding refused' in warning.call_args[0][0]

    def test_failure_is_not_retried_on_every_command(self, ssh):
        ssh.result.returncode = 255
        manager = _manager(tunnel={'enabled': True})

        with patch('mantis.managers.CLI.warning'):
            manager.docker_connection
            manager.docker_connection

        assert ssh.run.call_count == 1

    def test_temporary_directory_is_removed(self, ssh):
        ssh.result.returncode = 255
        manager = _manager(tunnel={'enabled': True})

        with patch('mantis.managers.CLI.warning'):
            manager.ensure_tunnel()

        assert not ssh.dir.exists()
