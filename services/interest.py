from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from models.account import Account
from models.discgrp import DisclosureGroup
from models.trancat import TransactionCategoryBalance

from .common.cobol_numerics import money


@dataclass(frozen=True)
class InterestResult:
    accounts: int
    total_interest: Decimal


def calculate_interest_for_account(account: Account) -> Decimal:
    total = Decimal("0.00")
    balances = TransactionCategoryBalance.objects.filter(acct_id=account.acct_id)
    for balance in balances:
        group = DisclosureGroup.objects.filter(
            acct_group_id=account.acct_group_id,
            tran_type_cd=balance.type_cd,
            tran_cat_cd=balance.cat_cd,
        ).first()
        if not group:
            continue
        total += money(balance.tran_cat_bal * group.int_rate / Decimal("100") / Decimal("12"))
    return money(total)


def apply_interest() -> InterestResult:
    total = Decimal("0.00")
    count = 0
    with transaction.atomic():
        for account in Account.objects.select_for_update().order_by("acct_id"):
            interest = calculate_interest_for_account(account)
            if interest:
                account.acct_curr_bal += interest
                account.acct_curr_cyc_debit += interest
                account.save(update_fields=["acct_curr_bal", "acct_curr_cyc_debit"])
                total += interest
                count += 1
    return InterestResult(accounts=count, total_interest=money(total))
