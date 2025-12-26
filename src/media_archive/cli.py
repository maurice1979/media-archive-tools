"""Media Archive Tools CLI."""

import os
import sys
from importlib.metadata import version
from pathlib import Path

import click
from loguru import logger as log

from media_archive.deduplicate import collect_files, delete_duplicates, find_duplicates
from media_archive.organizer import group_by_events, process_file

LOG_FILE = Path(__file__).resolve().parents[1] / "logs/media_archive_tools.log"
LOG_FILE_RELATIVE = os.path.relpath(LOG_FILE.resolve(), start=Path.cwd())

ROOT_DIR = Path(__file__).resolve().parents[2]
events_file = ROOT_DIR / "events.yaml"


@click.group(
    help="Media Archive Tools",
    invoke_without_command=True,
)
@click.option(
    "--debug",
    is_flag=True,
    help="Globally enable logging debug mode",
)
@click.option(
    "--no-logfile",
    "logfile_enabled",
    is_flag=True,
    default=True,
    help=f"Disable file logging ({LOG_FILE_RELATIVE})",
)
@click.option(
    "--version",
    "show_version",
    is_flag=True,
    help="Show current version for media_archive_tools",
)
@click.pass_context
def mat(ctx: click.Context, debug: bool, show_version: bool, logfile_enabled: bool):
    """Media Archive Tool entrypoint."""
    if show_version:
        print(f"media_archive_tools version {version('media_archive_tools')}")
        ctx.exit(0)

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        ctx.exit(1)

    level = "DEBUG" if debug else "INFO"

    log.remove()
    log.add(sys.stderr, level=level)

    if logfile_enabled:
        log.add(LOG_FILE, rotation="10 MB", retention="7 days", level=level)

    log.info("Welcome to Media Archive Tools")


@mat.command("organize", help="Organize media files")
@click.option(
    "--source-folder",
    "-sf",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, readable=True, path_type=Path),
    required=True,
    help="Folder with pictures and videos to be organized",
)
@click.option(
    "--target-folder",
    "-tf",
    type=click.Path(exists=False, file_okay=False, dir_okay=True, writable=True, path_type=Path),
    required=True,
    help="Folder to save organized pictures and videos",
)
@click.option("--dry-run/--no-dry-run", default=True, help="If set, only print actions without moving files.")
@click.pass_context
def organize(ctx, source_folder: Path, target_folder: Path, dry_run: bool):
    """Organize media files from source to target folder."""
    counter: int = 0
    counter_skipped: int = 0
    log.info("Started organizing new media...")
    for item in source_folder.iterdir():
        if item.is_file():
            file_moved: bool = process_file(item, target_folder, log=log)
            if file_moved:
                counter += 1
            else:
                counter_skipped += 1
            if counter % 100 == 0:
                log.info(f"---- So far Processed {counter} files")

    # Use events.yaml from the root directory of the package
    group_by_events(target_folder, events_file, dry_run=dry_run, log=log)

    if counter > 0:
        log.info(f"Finished moving {counter} images and videos! (skipped {counter_skipped} files)")
    else:
        log.info("No files were organized")


# Events
@mat.command("events", help="Group media files by events")
@click.option(
    "--target-folder",
    "-tf",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, readable=True, path_type=Path),
    required=True,
    help="Root folder containing year/month subfolders with media files",
)
@click.option(
    "--events-file",
    "-ef",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True, path_type=Path),
    required=True,
    help="Path to the YAML file containing event definitions",
)
@click.option("--dry-run/--no-dry-run", default=True, help="If set, only print actions without moving files.")
@click.pass_context
def events(ctx, target_folder: Path, events_file: Path, dry_run: bool):
    """Group media files in the target folder by events from a YAML file."""
    group_by_events(target_folder, events_file, dry_run=dry_run, log=log)


# Deduplicate


@mat.command("deduplicate", help="Deduplicate repeated images")
@click.option(
    "--target-folder",
    "-tf",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, readable=True, path_type=Path),
    required=True,
    help="Folder in which duplicates have to be found",
)
@click.option("--dry-run", default=False, help="If set, only print actions without deleting files.")
def deduplicate(target_folder: Path, dry_run: bool):
    """Deduplicate repeated images in the target folder."""
    log.info("📂 Scanning files...")
    files = collect_files(path=target_folder)
    log.info(f"📸 Found {len(files)} media files in {target_folder}")

    log.info("🔍 Finding duplicates...")
    duplicates = find_duplicates(files, log=log)
    log.info(f"🧬 Found {len(duplicates)} duplicate groups")

    delete_duplicates(duplicates, is_dry_run=dry_run, log=log)
