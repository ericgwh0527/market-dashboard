from datetime import datetime, timedelta, timezone

import pytest

from dashboard.ai_policy import CooldownPolicy

NOW = datetime(2026, 9, 28, 9, 40, tzinfo=timezone.utc)


def test_off_never_generates():
    assert CooldownPolicy("off").decide(None, NOW)[0] is False


def test_auto_generates_when_no_previous_or_old_previous():
    assert CooldownPolicy("auto").decide(None, NOW)[0] is True
    old = {"generated_at": (NOW - timedelta(hours=2)).isoformat()}
    assert CooldownPolicy("auto").decide(old, NOW)[0] is True


def test_force_still_respects_cooldown():
    recent = {"generated_at": (NOW - timedelta(minutes=10)).isoformat()}
    go, reason = CooldownPolicy("force").decide(recent, NOW)
    assert go is False and "51 min" in reason


def test_legacy_summary_without_timestamp_is_allowed():
    assert CooldownPolicy("auto").decide({"text": "x"}, NOW)[0] is True


def test_bad_mode_rejected():
    with pytest.raises(ValueError):
        CooldownPolicy("always")
