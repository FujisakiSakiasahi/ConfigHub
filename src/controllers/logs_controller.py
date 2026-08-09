from src.layers.logService.event_logger import CATEGORIES, LEVELS, logger


class LogsController:
    """Bridge between the logs view and the log service layer."""

    def get_logs(
        self,
        limit: int = 200,
        level: str | None = None,
        category: str | None = None,
        search: str | None = None,
    ) -> list[dict]:
        return logger.get_logs(limit=limit, level=level, category=category, search=search)

    def counts_by_level(self) -> dict:
        return logger.counts_by_level()

    def levels(self) -> list[str]:
        return LEVELS

    def categories(self) -> list[str]:
        return CATEGORIES

    def clear_logs(self) -> None:
        logger.clear()
