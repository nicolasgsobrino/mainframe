from __future__ import annotations

import pytest

from models.account import Account
from models.card import Card, CardXref
from models.customer import Customer
from models.transaction import DailyTransaction
from models.user import SecUser
from services.seed import seed_all


@pytest.mark.django_db
def test_seed_loads_core_ascii_records():
    results = {result.name: result.count for result in seed_all()}

    assert results["account"] == 50
    assert results["customer"] == 50
    assert results["card"] == 50
    assert results["card_xref"] == 50
    assert results["daily_transaction"] == 300
    assert results["sec_user"] == 2
    assert Account.objects.count() == 50
    assert Customer.objects.count() == 50
    assert Card.objects.count() == 50
    assert CardXref.objects.count() == 50
    assert DailyTransaction.objects.count() == 300
    assert SecUser.objects.filter(usr_id="ADMIN001", usr_type="A").exists()
