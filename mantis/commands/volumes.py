"""Volume commands: backup-volume, restore-volume."""
import typer

from mantis.app import command, state


@command(name="backup-volume", panel="Volumes")
def backup_volume(
    volume: str = typer.Argument(..., help="Volume name"),
):
    """Backups volume to a file"""
    state.backup_volume(volume)


@command(name="restore-volume", panel="Volumes")
def restore_volume(
    volume: str = typer.Argument(..., help="Volume name"),
    file: str = typer.Argument(..., help="Backup file"),
):
    """Restores volume from a file"""
    state.restore_volume(volume, file)
