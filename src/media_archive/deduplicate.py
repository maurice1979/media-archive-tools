"""Deduplicate photos."""
# TODO: Deduplicate videos too

import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

from media_archive.config import PHOTO_EXTS


def file_hash(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Compute SHA-256 hash of a file (streamed).

    Parameters
    ----------
    path : Path
        Path to the file to hash.
    chunk_size : int, optional
        Size of chunks to read at a time (default is 1MB).

    Returns
    -------
    str
        SHA-256 hash of the file as a hex string.

    """
    # Compute SHA-256 hash of a file (streamed)."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_files(path: Path, type: str = "photo") -> List[Path]:
    """Return list of files of type photo/video.

    Parameters
    ----------
    path : Path
        Directory to search for files.
    type : str, optional
        Type of media to collect ('photo' or 'video').

    Returns
    -------
    List[Path]
        List of file paths matching the type.

    """
    # Return list of files of type photo/video."""
    extensions = set()
    if type == "photo":
        extensions = PHOTO_EXTS
    elif type == "video":
        raise NotImplementedError("Video is not supported yet")

    files = []
    for p in path.rglob("*"):
        if p.is_file() and p.suffix.lower() in extensions:
            files.append(p)

    return files


def find_duplicates(files: List[Path], log: None) -> Dict[str, List[Path]]:
    """Find duplicate files by grouping by size and then by hash.

    Parameters
    ----------
    files : List[Path]
        List of file paths to check for duplicates.
    log : log, optional
        log to use for logging errors.

    Returns
    -------
    Dict[str, List[Path]]
        Dictionary mapping hash to list of duplicate file paths.

    """
    # 1️⃣ Group by size
    size_groups = defaultdict(list)
    for f in files:
        size_groups[f.stat().st_size].append(f)

    # 2️⃣ Hash only same-size files
    hash_groups = defaultdict(list)
    for size, group in size_groups.items():
        if len(group) < 2:
            continue
        for f in group:
            try:
                h = file_hash(f)
                hash_groups[h].append(f)
            except Exception as e:
                if log:
                    log.error(f"⚠️ Error hashing {f}: {e}")

    # 3️⃣ Keep only real duplicates
    duplicates = {h: files for h, files in hash_groups.items() if len(files) > 1}

    return duplicates


def delete_duplicates(duplicates: Dict[str, List[Path]], log, is_dry_run: bool = False) -> None:
    """Delete duplicate files, keeping one copy per group.

    Parameters
    ----------
    duplicates : Dict[str, List[Path]]
        Dictionary mapping hash to list of duplicate file paths.
    is_dry_run : bool, optional
        If True, only log actions without deleting files.
    log : Logger, optional
        Logger to use for logging actions.

    Returns
    -------
    None

    """
    total_deleted = 0

    for h, files in duplicates.items():
        files_sorted = sorted(files)
        keep = files_sorted[0]
        remove = files_sorted[1:]

        log.info(f"\n🟢 Keeping: {keep}")
        for f in remove:
            if is_dry_run:
                log.info(f"🧪 Would delete: {f}")
            else:
                try:
                    f.unlink()
                    log.info(f"❌ Deleted: {f}")
                    total_deleted += 1
                except Exception as e:
                    log.error(f"⚠️ Failed to delete {f}: {e}")

    log.info(f"✅ Total duplicates removed: {total_deleted}")
