"""Domain-specific event logging for ConfigHub.

Records notable pipeline events, warnings and errors — topology loads,
file imports, GNN model runs, GCL/XML validation results, exports — as
structured entries so they can be reviewed on the Logs page.
"""

import uuid
from datetime import datetime, timezone

from src.layers.logService import log_store


class LogLevel:
    DEBUG = "DEBUG"
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"


LEVELS = [LogLevel.DEBUG, LogLevel.INFO, LogLevel.SUCCESS, LogLevel.WARNING, LogLevel.ERROR]


class LogCategory:
    SYSTEM = "system"
    TOPOLOGY = "topology"
    WORKLOAD = "workload"
    MODEL = "model"
    VALIDATION = "validation"
    EXPORT = "export"
    FILE = "file"


CATEGORIES = [
    LogCategory.SYSTEM, LogCategory.TOPOLOGY, LogCategory.WORKLOAD,
    LogCategory.MODEL, LogCategory.VALIDATION, LogCategory.EXPORT, LogCategory.FILE,
]


class EventLogger:
    """Records and retrieves structured application log entries."""

    def log(self, level: str, category: str, event: str, message: str, **details) -> dict:
        entry = {
            "id": uuid.uuid4().hex[:10],
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "level": level,
            "category": category,
            "event": event,
            "message": message,
            "details": details or {},
        }
        log_store.append_entry(entry)
        return entry

    def debug(self, category: str, event: str, message: str, **details) -> dict:
        return self.log(LogLevel.DEBUG, category, event, message, **details)

    def info(self, category: str, event: str, message: str, **details) -> dict:
        return self.log(LogLevel.INFO, category, event, message, **details)

    def success(self, category: str, event: str, message: str, **details) -> dict:
        return self.log(LogLevel.SUCCESS, category, event, message, **details)

    def warning(self, category: str, event: str, message: str, **details) -> dict:
        return self.log(LogLevel.WARNING, category, event, message, **details)

    def error(self, category: str, event: str, message: str, exc: Exception | None = None, **details) -> dict:
        """Log an error. Pass the caught exception via `exc` to record its type/message."""
        if exc is not None:
            details.setdefault("exception_type", type(exc).__name__)
            details.setdefault("exception_message", str(exc))
        return self.log(LogLevel.ERROR, category, event, message, **details)

    def get_logs(
        self,
        limit: int = 200,
        level: str | None = None,
        category: str | None = None,
        search: str | None = None,
    ) -> list[dict]:
        """Return matching entries, most recent first."""
        entries = log_store.read_entries()
        if level:
            entries = [e for e in entries if e.get("level") == level]
        if category:
            entries = [e for e in entries if e.get("category") == category]
        if search:
            needle = search.lower()
            entries = [
                e for e in entries
                if needle in e.get("message", "").lower() or needle in e.get("event", "").lower()
            ]
        entries = list(reversed(entries))
        return entries[:limit] if limit else entries

    def counts_by_level(self) -> dict:
        counts = {lvl: 0 for lvl in LEVELS}
        for e in log_store.read_entries():
            lvl = e.get("level")
            if lvl in counts:
                counts[lvl] += 1
        return counts

    def clear(self) -> None:
        log_store.clear_entries()


logger = EventLogger()
