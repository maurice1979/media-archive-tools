"""Organize photos and videos."""

import argparse
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Tuple

import ffmpeg
from config import DEST_ROOT, PHOTO_EXTS, VIDEO_EXTS
from loguru import logger
from PIL import ExifTags, Image

# Regex to extract YYYYMMDD
DATE_RE = re.compile(r"(\d{4})(\d{2})(\d{2})")

EXIF_TAGS = {v: k for k, v in ExifTags.TAGS.items()}


def get_date_from_filename(path: Path) -> Tuple[str | None, str | None]:
    """Extract year and year-month from filename using regex.

    Parameters
    ----------
    path : Path
        Path to the file.

    Returns
    -------
    Tuple[str | None, str | None]
        Year and year-month if found, else None.

    """
    match = DATE_RE.search(path.name)
    if match:
        year, month, _ = match.groups()
        return str(year), f"{year}{month}"
    return None, None


def get_date_from_image_exif(path: Path) -> Tuple[str | None, str | None]:
    """Extract year and year-month from image EXIF metadata.

    Parameters
    ----------
    path : Path
        Path to the image file.

    Returns
    -------
    Tuple[str | None, str | None]
        Year and year-month if found, else None.

    """
    try:
        with Image.open(path) as img:
            exif = img._getexif()
            if exif:
                for tag in ("DateTimeOriginal", "DateTimeDigitized", "DateTime"):
                    tag_id = EXIF_TAGS.get(tag)
                    if tag_id in exif:
                        dt = datetime.strptime(exif[tag_id], "%Y:%m:%d %H:%M:%S")
                        return str(dt.year), f"{dt.year}{dt.month:02d}"
    except Exception:
        logger.info(f"EXIF : {path}")
    return None, None


def get_date_from_video(path: Path) -> Tuple[str | None, str | None]:
    """Extract year and year-month from video metadata using ffmpeg.

    Parameters
    ----------
    path : Path
        Path to the video file.

    Returns
    -------
    Tuple[str | None, str | None]
        Year and year-month if found, else None.

    """
    try:
        probe = ffmpeg.probe(str(path))
        tags = probe.get("format", {}).get("tags", {})
        ct = tags.get("creation_time")
        if ct:
            dt = datetime.fromisoformat(ct.replace("Z", ""))
            return str(dt.year), f"{dt.year}{dt.month:02d}"
    except Exception:
        logger.info(f"VIDEO : {path}")
    return None, None


def get_date_from_file(path: Path) -> Tuple[str | None, str | None]:
    """Extract year and year-month from file's modification time.

    Parameters
    ----------
    path : Path
        Path to the file.

    Returns
    -------
    Tuple[str | None, str | None]
        Year and year-month if found, else None.

    """
    try:
        dt = datetime.fromtimestamp(path.stat().st_mtime)
        return str(dt.year), f"{dt.year}{dt.month:02d}"
    except Exception:
        logger.info(f"Fallback : {path}")
        return None, None


def extract_date(path: Path) -> Tuple[str | None, str | None]:
    """Extract year and year-month from file using filename, EXIF, video metadata, or file date.

    Parameters
    ----------
    path : Path
        Path to the file.

    Returns
    -------
    Tuple[str | None, str | None]
        Year and year-month if found, else None.

    """
    # 1️⃣ Extract date from Filename
    year, month = get_date_from_filename(path)
    if year and month:
        return year, month

    # 2️⃣ Extract date from Photo EXIF
    if path.suffix.lower() in PHOTO_EXTS:
        year, month = get_date_from_image_exif(path)
        if year and month:
            return year, month

    # 3️⃣ Extract date from Video metadata
    elif path.suffix.lower() in VIDEO_EXTS:
        year, month = get_date_from_video(path)
        if year and month:
            return year, month

    # 4️⃣ Filesystem fallback - Extract date from creation date
    year, month = get_date_from_file(path)
    if year and month:
        return year, month

    return None, None


def process_file(path: Path) -> bool:
    """Organize file by moving/copying it to the appropriate folder based on its date and type.

    Parameters
    ----------
    path : Path
        Path to the file to process.

    Returns
    -------
    bool
        True if file was moved/copied, False otherwise.

    """
    date_info = extract_date(path)
    if not date_info:
        logger.info(f"⚠️  Skipping (no date): {path.name}")
        return False

    year, year_month = date_info
    ext = path.suffix.lower()

    # Photo
    if ext in PHOTO_EXTS:
        dest_dir = DEST_ROOT / year / year_month
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / path.name

        shutil.move(path, dest_path)
        logger.info(f"📷 Moved photo → {dest_path}")
        return True

    # Video
    elif ext in VIDEO_EXTS:
        dest_dir = DEST_ROOT / year / year_month / "video"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / path.name

        shutil.copy2(path, dest_path)
        logger.info(f"🎥 Copied video → {dest_path}")
        return True

    else:
        logger.info(f"⚠️  Skipping (unknown type): {path.name}")
        return False


if __name__ == "__main__":
    # Set-up argument parser
    parser = argparse.ArgumentParser(description="Organize pictures and videos")
    parser.add_argument(
        "--source-folder",
        "-sf",
        type=str,
        default="/Volumes/photo/movil_maurice",
        help="Folder with pictures and videos to be organized",
    )
    parser.add_argument(
        "--target-folder",
        "-tf",
        type=str,
        default="/Volumes/photo",
        help="Folder to save organized pictures and videos",
    )
    args = parser.parse_args()

    source_folder: Path = Path(args.source_folder)
    target_folder: Path = Path(args.target_folder)

    counter: int = 0
    counter_skipped: int = 0
    for item in source_folder.iterdir():
        if item.is_file():
            file_moved: bool = process_file(item)
            if file_moved:
                counter += 1
            else:
                counter_skipped += 1
            if counter % 50 == 0:
                logger.info(f"---- So far Processed {counter} files")
    if counter > 0:
        logger.info(f"Finished moving {counter} images and videos! (skipped {counter_skipped} files)")
    else:
        logger.info("No files were organized")
