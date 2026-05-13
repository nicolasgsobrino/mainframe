from __future__ import annotations

import pytest
from django.db import IntegrityError

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


@pytest.mark.django_db
def test_posting_preserves_existing_ledger_rows():
    seed_all()
    first_result = post_daily_transactions()
    first_count = Transaction.objects.count()

    second_result = post_daily_transactions()

    assert first_result.posted == first_count
    assert second_result.processed == DailyTransaction.objects.count()
    assert second_result.posted == 0
    assert Transaction.objects.count() == first_count


@pytest.mark.django_db
def test_daily_reject_transaction_id_is_unique():
    DailyReject.objects.create(dalytran_id="DUPLICATE", card_num="1", reason="first")

    with pytest.raises(IntegrityError):
        DailyReject.objects.create(dalytran_id="DUPLICATE", card_num="1", reason="second")
