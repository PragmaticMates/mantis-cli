# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Mantis is a CLI tool that wraps docker and docker-compose commands for managing web application deployments. It provides environment encryption, zero-downtime deployments, and service-specific extensions for Django, PostgreSQL, and Nginx.

## Development Commands

```bash
# Install for development
pip install -e .

# Build distribution
python3 setup.py sdist

# Upload to PyPI
twine upload dist/<latest-tarball>

# Build and upload in one step
make sdist-and-upload
```

## Architecture

### Entry Point
- `mantis/command_line.py`: CLI entry point via `run()`, parses arguments and dispatches commands
- Usage: `mantis [--mode=remote|ssh|host] [environment] --command[:params]`

### Core Components

**Manager System** (`mantis/managers.py`):
- `AbstractManager`: Base class with internal methods (not exposed to CLI)
- `BaseManager`: All CLI-callable commands defined as methods here
- Commands are method names with underscores replaced by dashes (e.g., `zero_downtime` -> `--zero-downtime`)

**Dynamic Extension Loading** (`mantis/logic.py`):
- `get_manager()`: Creates a dynamic class that inherits from BaseManager plus any configured extensions
- Extensions add methods that become available as CLI commands
- Extensions are defined in `mantis.json` config under `"extensions"`

**Extensions** (`mantis/extensions/`):
- `Django`: `--shell`, `--manage:params`, `--send-test-email`
- `Postgres`: `--psql`, `--pg-dump`, `--pg-restore`
- `Nginx`: `--reload-webserver` (called automatically during deploy)

**Environment Encryption** (`mantis/crypto.py`, `mantis/environment.py`):
- Supports deterministic (AES-SIV) and non-deterministic (Fernet) encryption
- Encrypts each environment variable separately for VCS diff tracking
- Key stored in `mantis.key` file or `$MANTIS_KEY` environment variable

### Configuration

Config file: `mantis.json` (located via `$MANTIS_CONFIG` or auto-discovered)
- Template: `mantis/mantis.tpl` defines all valid config keys
- `<MANTIS>` variable in paths resolves to config file's parent directory
- Connections format: `ssh://user@host:port` or `context://<docker-context-name>`

### Key Patterns

- Commands with optional params use method signatures with defaults
- Command shortcuts: `-b` (build), `-d` (deploy), `-s` (status), `-l` (logs), etc.
- Zero-downtime deployment uses docker-compose scaling and healthchecks
- Container names use `-` separator; image names use `_` separator
