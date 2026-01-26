# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Mantis is a CLI tool that wraps docker and docker-compose commands for managing web application deployments. It provides environment encryption, zero-downtime deployments, and service-specific extensions for Django, PostgreSQL, and Nginx.

## Development Commands

```bash
# Install for development
pip install -e .

# Run tests
make test

# Build distribution
python3 setup.py sdist

# Upload to PyPI
twine upload dist/<latest-tarball>

# Build and upload in one step
make sdist-and-upload
```

## Architecture

### Entry Point
- `mantis/command_line.py`: CLI entry point via `run()`, supports command chaining with `+` separator
- Usage: `mantis [-e environment] [-m mode] [-n] COMMAND [ARGS] [+ COMMAND [ARGS] ...]`
- Examples:
  - `mantis -e production status`
  - `mantis -e production build + push + deploy`
  - `mantis status` (single connection mode)

### Core Components

**App Setup** (`mantis/app.py`):
- Typer application with command registration via `@command` decorator
- Manages state, shortcuts, and command panels

**Command Modules** (`mantis/commands/`):
- `core.py`: build, push, deploy, status, logs, exec, etc.
- `images.py`: image management commands
- `containers.py`: container management commands
- `compose.py`: docker-compose commands
- `services.py`: service management commands
- `secrets.py`: show-env, encrypt-env, decrypt-env, check-env, generate-key, read-key
- `configuration.py`: show-config, check-config
- `connection.py`: contexts, create-context, ssh
- `volumes.py`: volume management commands
- `django.py`: Django-specific commands (shell, manage, send-test-email)
- `postgres.py`: PostgreSQL commands (psql, pg-dump, pg-restore)
- `nginx.py`: Nginx commands (reload-webserver)

**Manager System** (`mantis/managers.py`):
- `AbstractManager`: Base class with internal methods (not exposed to CLI)
- `BaseManager`: Core deployment and management methods
- `get_manager()`: Creates a dynamic class that inherits from BaseManager plus any configured extensions
- Extensions are defined in `mantis.json` config under `"extensions"`

**Environment & Encryption** (`mantis/cryptography.py`, `mantis/environment.py`):
- Supports deterministic (AES-SIV) and non-deterministic (Fernet) encryption
- Encrypts each environment variable separately for VCS diff tracking
- Key stored in `mantis.key` file or `$MANTIS_KEY` environment variable
- Environment accessed via `manager.environment` property

### Configuration

Config file: `mantis.json` (located via `$MANTIS_CONFIG` or auto-discovered)
- Template: `mantis/mantis.tpl` defines all valid config keys
- `<MANTIS>` variable in paths resolves to config file's parent directory
- Connections format: `ssh://user@host:port` or `context://<docker-context-name>`

### Key Patterns

- Commands use Typer decorators with `@command(name="cmd-name", panel="Panel")`
- Command chaining: `mantis -e prod build + push + deploy`
- Command shortcuts: `-b` (build), `-d` (deploy), `-s` (status), `-l` (logs), etc.
- Zero-downtime deployment uses docker-compose scaling and healthchecks
- Container names use `-` separator; image names use `_` separator

### Testing

Tests are located in `tests/` directory using pytest:
- `tests/test_command_line.py`: Tests for argument parsing and command chaining
