"""Configuration commands: show-config, check-config."""
import json

from mantis.app import command, state


@command(name="show-config", panel="Configuration", no_env=True)
def show_config():
    """Shows the JSON mantis config"""
    print(json.dumps(state._manager.config, indent=2))


@command(name="check-config", panel="Configuration", no_env=True)
def check_config():
    """Validates config file"""
    state.check_config()
