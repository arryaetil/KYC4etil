"""Wekelijkse achtergrondplanning voor jaarverslag-monitoring."""
import logging
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .pipeline.monitoring import run_monitoring_watchlist_background

_log = logging.getLogger("scheduler")
_scheduler = AsyncIOScheduler(timezone="Europe/Amsterdam")


def _scheduler_enabled() -> bool:
    return os.getenv("MONITORING_SCHEDULER_ENABLED", "true").lower() not in {
        "0", "false", "no",
    }


def start_scheduler() -> None:
    """Start de wekelijkse jaarverslag-monitoring-taak, idempotent."""
    if not _scheduler_enabled():
        _log.warning("Wekelijkse jaarverslagmonitoring staat gepauzeerd")
        return
    if _scheduler.running:
        return
    try:
        _scheduler.add_job(
            run_monitoring_watchlist_background,
            trigger="cron",
            day_of_week="mon",
            hour=6,
            minute=0,
            id="wekelijkse_jaarverslag_monitoring",
            replace_existing=True,
        )
        _scheduler.start()
    except Exception:
        _log.exception("Kon de jaarverslag-monitoring-scheduler niet starten")
