"""Config commands: check-config, contexts, create-context, ssh."""
from mantis.app import command, state


@command(name="check-config", no_env=True)
def check_config():
    """Validates config file"""
    state.check_config()


@command(panel="Connections", no_env=True)
def contexts():
    """Prints all docker contexts"""
    state.contexts()


@command(name="create-context", panel="Connections", no_env=True)
def create_context():
    """Creates docker context"""
    state.create_context()


@command(name="ssh", panel="Connections")
def ssh_cmd():
    """Connects to remote host via SSH"""
    state.ssh()
