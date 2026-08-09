"""JSONL-backed storage for application log entries.

Generic append/read/clear operations only — no knowledge of what an entry's
fields mean. Domain-specific logging behaviour lives in event_logger.py.
"""

import json
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_LOG_DIR = _PROJECT_ROOT / "logs"
_LOG_FILE = _LOG_DIR / "app_log.jsonl"

MAX_ENTRIES = 5000


def append_entry(entry: dict) -> None:
    """Append one log entry, then trim the file down to the most recent MAX_ENTRIES."""
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    with _LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")

    lines = _LOG_FILE.read_text(encoding="utf-8").splitlines()
    if len(lines) > MAX_ENTRIES:
        _LOG_FILE.write_text("\n".join(lines[-MAX_ENTRIES:]) + "\n", encoding="utf-8")


def read_entries() -> list[dict]:
    """Return all stored entries, oldest first. Malformed lines are skipped."""
    if not _LOG_FILE.exists():
        return []
    entries = []
    with _LOG_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def clear_entries() -> None:
    if _LOG_FILE.exists():
        _LOG_FILE.write_text("", encoding="utf-8")
