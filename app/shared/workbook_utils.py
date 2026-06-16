import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

INVALID_BACKUP_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]+')


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def has_meaningful_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def normalize_header(value: Any) -> str:
    text = clean_text(value).casefold()
    text = "".join(
        character
        for character in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(character)
    )
    translation = str.maketrans(
        {
            "\u00e7": "c",
            "\u011f": "g",
            "\u0131": "i",
            "\u00f6": "o",
            "\u015f": "s",
            "\u00fc": "u",
        }
    )
    normalized = text.translate(translation)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def backup_filename(source_path: Path, fallback_stem: str) -> str:
    safe_stem = INVALID_BACKUP_FILENAME_CHARS.sub("_", source_path.stem).strip()
    if not safe_stem:
        safe_stem = fallback_stem
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return f"{safe_stem}_{timestamp}{source_path.suffix or '.xlsx'}"


def prune_backups(
    backup_dir: Path,
    source_path: Path,
    keep_count: int,
    fallback_stem: str,
) -> None:
    safe_stem = INVALID_BACKUP_FILENAME_CHARS.sub("_", source_path.stem).strip()
    if not safe_stem:
        safe_stem = fallback_stem
    pattern = f"{safe_stem}_*{source_path.suffix or '.xlsx'}"
    backups = sorted(backup_dir.glob(pattern), reverse=True)
    for old_backup in backups[keep_count:]:
        old_backup.unlink(missing_ok=True)
