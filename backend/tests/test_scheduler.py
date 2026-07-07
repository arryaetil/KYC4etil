"""Tests voor de wekelijkse jaarverslag-monitoring-scheduler."""
from app.scheduler import _scheduler, start_scheduler


def test_start_scheduler_registreert_wekelijkse_taak():
    start_scheduler()

    job = _scheduler.get_job("wekelijkse_jaarverslag_monitoring")
    assert job is not None


def test_start_scheduler_is_veilig_dubbel_aan_te_roepen():
    start_scheduler()
    start_scheduler()

    assert _scheduler.running is True
