#!/usr/bin/env python
"""
Mantis CLI - Docker deployment tool

Usage:
    mantis [OPTIONS] COMMAND [ARGS]... [COMMAND [ARGS]...]

Examples:
    mantis -e production status
    mantis -e production deploy --dirty
    mantis -e production build push deploy
    mantis status                          (single connection mode)
    mantis manage migrate
"""
from mantis.app import app

# Import commands to register them with the app
from mantis import commands  # noqa: F401


def run():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    run()
