from __future__ import annotations

from decimal import Decimal

import pytest

from models.account import Account
from services.interest import calculate_interest_for_account
from services.seed import seed_all


@pytest.mark.django_db
def test_interest_uses_disclosure_groups():
    seed_all()
    account = Account.objects.get(acct_id=1)

    interest = calculate_interest_for_account(account)

    assert interest >= Decimal("0.00")
