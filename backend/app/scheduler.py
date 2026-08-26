"""Achtergrondplanning: wekelijkse monitoring en de dagelijkse back-up."""
import logging
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .backup import backupmap, maak_backup
from .pipeline.monitoring import run_monitoring_watchlist_background

_log = logging.getLogger("scheduler")
_scheduler = AsyncIOScheduler(timezone="Europe/Amsterdam")


def _scheduler_enabled() -> bool:
    return os.getenv("MONITORING_SCHEDULER_ENABLED", "true").lower() not in {
        "0", "false", "no",
    }


def _plan_backup() -> None:
    """Dagelijks een herstelpunt, los van de monitoring.

    Bewust niet aan `MONITORING_SCHEDULER_ENABLED` gekoppeld: die vlag staat uit
    omdat de monitoring met een knop wordt gestart, en dat is geen reden om ook
    geen back-up meer te maken. Zonder pad gebeurt er niets.
    """
    if backupmap() is None:
        _log.info("Geen BACKUP_PAD ingesteld; er worden geen herstelpunten gemaakt")
        return
    _scheduler.add_job(
        maak_backup,
        trigger="cron",
        hour=3,
        minute=30,
        id="dagelijkse_database_backup",
        replace_existing=True,
    )


def start_scheduler() -> None:
    """Start de geplande taken, idempotent."""
    if _scheduler.running:
        return
    _plan_backup()
    if not _scheduler_enabled():
        _log.warning("Wekelijkse jaarverslagmonitoring staat gepauzeerd")
        # De back-up hangt hier niet vanaf; starten wat er gepland is.
        if _scheduler.get_jobs():
            _scheduler.start()
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
