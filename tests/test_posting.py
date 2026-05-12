from __future__ import annotations

import pytest

from models.transaction import DailyReject, DailyTransaction, Transaction
from services.posting import post_daily_transactions
from services.seed import seed_all


@pytest.mark.django_db
def test_posting_processes_daily_transactions():
    seed_all()

    result = post_daily_transactions()

    assert result.processed == DailyTransaction.objects.count()
    assert result.posted == Transaction.objects.count()
    assert result.rejected == DailyReject.objects.count()
    assert result.processed == result.posted + result.rejected
