"""Configuration variables."""

# Supported extensions
PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".tiff", ".dng"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv"}

# Log formats
short_fmt = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <5}</level> - <level>{message}</level>"
debug_fmt = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}"
    "</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)
