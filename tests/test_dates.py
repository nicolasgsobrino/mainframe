from __future__ import annotations

from datetime import date

from services.common import dates


def test_system_date_uses_django_localdate(monkeypatch):
    monkeypatch.setattr(dates.timezone, "localdate", lambda: date(2024, 1, 2))

    assert dates.system_date() == "2024-01-02"
