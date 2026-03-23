"""In-memory circular log buffers for scraping jobs.

Shared between scheduler and service to avoid circular imports.
"""

from __future__ import annotations

import logging
from collections import deque
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

_MAX_LOG_ENTRIES = 200

_job_logs: dict[str, deque[dict]] = {
    "scraping_tick": deque(maxlen=_MAX_LOG_ENTRIES),
    "calendar_sync": deque(maxlen=_MAX_LOG_ENTRIES),
    "deadline_check": deque(maxlen=_MAX_LOG_ENTRIES),
    "deadline_reminder": deque(maxlen=_MAX_LOG_ENTRIES),
    "manual_scrape": deque(maxlen=_MAX_LOG_ENTRIES),
    "live_monitor": deque(maxlen=_MAX_LOG_ENTRIES),
    "nightly_rescrape": deque(maxlen=_MAX_LOG_ENTRIES),
}


def scraping_log(job_id: str, message: str, level: str = "info") -> None:
    """Append a log entry to the per-job buffer and emit via stdlib logger."""
    if job_id not in _job_logs:
        _job_logs[job_id] = deque(maxlen=_MAX_LOG_ENTRIES)
    entry = {
        "ts": datetime.now(UTC).isoformat(),
        "level": level,
        "msg": message,
    }
    _job_logs[job_id].append(entry)
    getattr(logger, level, logger.info)("scraping.%s: %s", job_id, message)


def get_job_logs(job_id: str) -> list[dict]:
    """Return a snapshot of the log buffer for a job."""
    return list(_job_logs.get(job_id, []))
