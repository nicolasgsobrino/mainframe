from __future__ import annotations

from datetime import datetime

from django.utils import timezone


def db2_timestamp() -> str:
    now = timezone.localtime()
    return now.strftime("%Y-%m-%d-%H.%M.%S.%f")


def system_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")
