from datetime import datetime, timedelta, timezone
from src.tick import is_turn_due


def test_turn_due_when_never_run():
    now = datetime.now(timezone.utc)
    assert is_turn_due(None, interval_minutes=480, tolerance_minutes=10, now_dt=now) is True
    assert is_turn_due("", interval_minutes=1, tolerance_minutes=0, now_dt=now) is True


def test_turn_due_tolerance_window():
    now = datetime(2026, 10, 24, 12, 0, 0, tzinfo=timezone.utc)
    # 480 min interval with 10 min tolerance -> due at 470 min (7h 50m)
    interval = 480
    tolerance = 10

    # 469 minutes elapsed -> Not due
    last_run_469 = (now - timedelta(minutes=469)).isoformat()
    assert is_turn_due(last_run_469, interval, tolerance, now) is False

    # 470 minutes elapsed -> Exactly due
    last_run_470 = (now - timedelta(minutes=470)).isoformat()
    assert is_turn_due(last_run_470, interval, tolerance, now) is True

    # 485 minutes elapsed -> Due
    last_run_485 = (now - timedelta(minutes=485)).isoformat()
    assert is_turn_due(last_run_485, interval, tolerance, now) is True


def test_turn_due_test_mode_short_interval():
    now = datetime(2026, 10, 24, 12, 0, 0, tzinfo=timezone.utc)
    interval = 1  # 60 seconds
    tolerance = 0  # 0 tolerance

    last_run_30s = (now - timedelta(seconds=30)).isoformat()
    assert is_turn_due(last_run_30s, interval, tolerance, now) is False

    last_run_60s = (now - timedelta(seconds=60)).isoformat()
    assert is_turn_due(last_run_60s, interval, tolerance, now) is True
