"""Nginx extension commands: reload-webserver."""
from mantis.app import command, state


@command(name="reload-webserver", panel="Nginx")
def reload_webserver():
    """Reloads nginx webserver"""
    state.reload_webserver()
