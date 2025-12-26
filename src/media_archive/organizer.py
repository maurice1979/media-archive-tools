"""Organize photos and videos."""

import datetime
import re
import shutil
from pathlib import Path
from typing import Tuple

import ffmpeg
from PIL import ExifTags, Image

from media_archive.config import PHOTO_EXTS, VIDEO_EXTS
from media_archive.utils import load_events

# Regex to extract YYYYMMDD
DATE_RE = re.compile(r"(\d{4})(\d{2})(\d{2})")

EXIF_TAGS = {v: k for k, v in ExifTags.TAGS.items()}


def get_year_month_day(dt: datetime.datetime) -> Tuple[str, str, str]:
    """Extract year, year-month, and day as strings from a datetime object.

    Parameters
    ----------
    dt : datetime.datetime
        Datetime object to extract components from.

    Returns
    -------
    Tuple[str, str, str]
        Year, year-month, and day as strings.

    """
    return str(dt.year), f"{dt.year}{dt.month:02d}", f"{dt.day:02d}"


def get_date_from_filename(path: Path) -> datetime.datetime | None:
    """Extract datetime from filename using regex.

    Parameters
    ----------
    path : Path
        Path to the file.

    Returns
    -------
    datetime.datetime
        If datetime could be extracted else None.

    """
    match = DATE_RE.search(path.name)
    if match:
        year, month, day = match.groups()
        return datetime.datetime(int(year), int(month), int(day))
    return None


def get_date_from_image_exif(path: Path, log=None) -> datetime.datetime | None:
    """Extract datetime from image EXIF metadata.

    Parameters
    ----------
    path : Path
        Path to the image file.
    log : Logger, optional
        Logger object.

    Returns
    -------
    datetime.datetime
        If datetime could be extracted else None.

    """
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            if exif:
                for tag in ("DateTimeOriginal", "DateTimeDigitized", "DateTime"):
                    tag_id = EXIF_TAGS.get(tag)
                    if tag_id is not None and tag_id in exif:
                        return datetime.datetime.strptime(exif[tag_id], "%Y:%m:%d %H:%M:%S")
    except Exception:
        if log:
            log.info(f"EXIF : {path}")
    return None


def get_date_from_video(path: Path, log=None) -> datetime.datetime | None:
    """Extract datetime from video metadata using ffmpeg.

    Parameters
    ----------
    path : Path
        Path to the video file.
    log : Logger, optional
        Logger object.

    Returns
    -------
    datetime.datetime
        If datetime could be extracted else None.

    """
    try:
        probe = ffmpeg.probe(str(path))
        tags = probe.get("format", {}).get("tags", {})
        ct = tags.get("creation_time")
        if ct:
            return datetime.datetime.fromisoformat(ct.replace("Z", ""))
    except Exception:
        if log:
            log.info(f"VIDEO : {path}")
    return None


def get_date_from_file(path: Path, log=None) -> datetime.datetime | None:
    """Extract datetime from file's modification time.

    Parameters
    ----------
    path : Path
        Path to the file.
    log : Logger, optional
        Logger object.

    Returns
    -------
    datetime.datetime
        If datetime could be extracted else None.

    """
    try:
        return datetime.datetime.fromtimestamp(path.stat().st_mtime)
    except Exception:
        if log:
            log.info(f"Fallback : {path}")
        return None


def extract_date(path: Path, log=None) -> datetime.datetime | None:
    """Extract datetime from file using filename, EXIF, video metadata, or file date.

    Parameters
    ----------
    path : Path
        Path to the file.
    log : Logger, optional
        Logger object.

    Returns
    -------
    datetime.datetime
        If datetime could be extracted else None.

    """
    # 1️⃣ Extract date from Filename
    dt = get_date_from_filename(path)
    if dt:
        return dt

    # 2️⃣ Extract date from Photo EXIF
    if path.suffix.lower() in PHOTO_EXTS:
        dt = get_date_from_image_exif(path, log=log)
        if dt:
            return dt

    # 3️⃣ Extract date from Video metadata
    elif path.suffix.lower() in VIDEO_EXTS:
        dt = get_date_from_video(path, log=log)
        if dt:
            return dt

    # 4️⃣ Filesystem fallback - Extract date from creation date
    dt = get_date_from_file(path, log=log)
    if dt:
        return dt

    return None


def group_by_events(target_folder: Path, events_file: Path, dry_run: bool = True, log=None) -> None:
    """Organize files in the target folder into event-based subfolders based on date ranges from an events file.

    Parameters
    ----------
    target_folder : Path
        Root folder containing year/month subfolders with media files.
    events_file : Path
        Path to the YAML file containing event definitions (with 'start', 'end', and 'name').
    dry_run : bool, optional
        If True, only print the actions that would be taken, do not move files (default is True).
    log : Logger, optional
        Logger object.

    Returns
    -------
    None

    """
    events = load_events(events_file)

    for year_dir in target_folder.iterdir():
        if not year_dir.is_dir() or not year_dir.name.isdigit():
            continue

        for month_dir in year_dir.iterdir():
            if not month_dir.is_dir() or not month_dir.name.isdigit():
                continue

            for path in month_dir.iterdir():
                if not path.is_file():
                    continue

                date = extract_date(path, log=log)
                if not date:
                    continue

                for event in events:
                    if event["start"] <= date.date() <= event["end"]:
                        event_root = (
                            target_folder / str(event["start"].year) / event["start"].strftime("%Y%m") / event["name"]
                        )
                        event_root.mkdir(parents=True, exist_ok=True)

                        dest = event_root / path.name

                        if dry_run:
                            if log:
                                log.info(f"🧪 Would move {path} → {dest}")
                        else:
                            shutil.move(path, dest)
                            if log:
                                log.info(f"Moved {path} → {dest}")

                        break  # one event per file


def process_file(path: Path, target_folder: Path, log=None) -> bool:
    """Organize file by moving/copying it to the appropriate folder based on its date and type.

    Parameters
    ----------
    path : Path
        Path to the file to process.
    target_folder : Path
        Root folder in which the media file will be moved.
    log : Logger, optional
        Logger object.

    Returns
    -------
    bool
        True if file was moved/copied, False otherwise.

    """
    file_date = extract_date(path, log=log)
    if not file_date:
        if log:
            log.debug(f"⚠️  Skipping (no date): {path.name}")
        return False

    year, year_month, _ = get_year_month_day(file_date)
    if not year or not year_month:
        return False

    # Get file extension
    ext = path.suffix.lower()

    # Photo
    if ext in PHOTO_EXTS:
        dest_dir = target_folder / year / year_month
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / path.name

        shutil.move(path, dest_path)
        if log:
            log.info(f"📷 Moved photo → {dest_path}")
        return True

    # Video
    elif ext in VIDEO_EXTS:
        dest_dir = target_folder / year / year_month / "video"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / path.name

        shutil.copy2(path, dest_path)
        if log:
            log.info(f"🎥 Copied video → {dest_path}")
        return True

    else:
        if log:
            log.info(f"⚠️  Skipping (unknown type): {path.name}")
        return False
