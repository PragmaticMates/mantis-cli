"""PostgreSQL extension commands: psql, pg-dump, pg-dump-data, pg-restore, pg-restore-data."""
from typing import Optional

import typer

from mantis.app import command, state


@command(panel="PostgreSQL")
def psql():
    """Starts psql console"""
    state.psql()


@command(name="pg-dump", panel="PostgreSQL")
def pg_dump(
    data_only: bool = typer.Option(False, "--data-only", "-d", help="Dump data only"),
    table: Optional[str] = typer.Option(None, "--table", "-t", help="Specific table"),
):
    """Backups PostgreSQL database"""
    state.pg_dump(data_only=data_only, table=table)


@command(name="pg-dump-data", panel="PostgreSQL")
def pg_dump_data(
    table: Optional[str] = typer.Option(None, "--table", "-t", help="Specific table"),
):
    """Backups PostgreSQL database (data only)"""
    state.pg_dump_data(table=table)


@command(name="pg-restore", panel="PostgreSQL")
def pg_restore(
    filename: str = typer.Argument(..., help="Backup filename"),
    table: Optional[str] = typer.Option(None, "--table", "-t", help="Specific table"),
):
    """Restores database from backup"""
    state.pg_restore(filename=filename, table=table)


@command(name="pg-restore-data", panel="PostgreSQL")
def pg_restore_data(
    filename: str = typer.Argument(..., help="Backup filename"),
    table: str = typer.Argument(..., help="Table name"),
):
    """Restores database data from backup"""
    state.pg_restore(filename=filename, table=table)
