from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from django.contrib.auth.hashers import make_password
from django.db import transaction

from models.account import Account
from models.card import Card, CardXref
from models.customer import Customer
from models.discgrp import DisclosureGroup
from models.trancat import TransactionCategory, TransactionCategoryBalance
from models.transaction import DailyReject, DailyTransaction, Transaction
from models.trantype import TransactionType
from models.user import SecUser

from .common.ebcdic_loader import (
    ACCOUNT_LAYOUT,
    ASCII_DIR,
    CARD_LAYOUT,
    CARD_XREF_LAYOUT,
    CUSTOMER_LAYOUT,
    DAILY_TRANSACTION_LAYOUT,
    DISCLOSURE_GROUP_LAYOUT,
    TRAN_CAT_BALANCE_LAYOUT,
    TRAN_CATEGORY_LAYOUT,
    TRAN_TYPE_LAYOUT,
    read_fixed_width,
)


@dataclass(frozen=True)
class SeedResult:
    name: str
    count: int


def _replace(model, rows: list[dict]) -> int:
    model.objects.all().delete()
    model.objects.bulk_create([model(**row) for row in rows])
    return len(rows)


def seed_all(data_dir: Path = ASCII_DIR, only: str | None = None) -> list[SeedResult]:
    jobs = {
        "account": (Account, data_dir / "acctdata.txt", ACCOUNT_LAYOUT),
        "customer": (Customer, data_dir / "custdata.txt", CUSTOMER_LAYOUT),
        "card": (Card, data_dir / "carddata.txt", CARD_LAYOUT),
        "card_xref": (CardXref, data_dir / "cardxref.txt", CARD_XREF_LAYOUT),
        "transaction_type": (TransactionType, data_dir / "trantype.txt", TRAN_TYPE_LAYOUT),
        "transaction_category": (
            TransactionCategory,
            data_dir / "trancatg.txt",
            TRAN_CATEGORY_LAYOUT,
        ),
        "disclosure_group": (DisclosureGroup, data_dir / "discgrp.txt", DISCLOSURE_GROUP_LAYOUT),
        "tran_cat_balance": (
            TransactionCategoryBalance,
            data_dir / "tcatbal.txt",
            TRAN_CAT_BALANCE_LAYOUT,
        ),
        "daily_transaction": (
            DailyTransaction,
            data_dir / "dailytran.txt",
            DAILY_TRANSACTION_LAYOUT,
        ),
    }

    results: list[SeedResult] = []
    with transaction.atomic():
        if only is None:
            DailyReject.objects.all().delete()
            Transaction.objects.all().delete()
        for name, (model, path, layout) in jobs.items():
            if only and only != name:
                continue
            rows = read_fixed_width(path, layout)
            results.append(SeedResult(name, _replace(model, rows)))
        if only in (None, "sec_user"):
            SecUser.objects.all().delete()
            SecUser.objects.bulk_create(
                [
                    SecUser(
                        usr_id="ADMIN001",
                        usr_fname="Admin",
                        usr_lname="User",
                        usr_pwd=make_password("PASSWORD"),
                        usr_type="A",
                    ),
                    SecUser(
                        usr_id="USER0001",
                        usr_fname="Demo",
                        usr_lname="User",
                        usr_pwd=make_password("PASSWORD"),
                        usr_type="U",
                    ),
                ]
            )
            results.append(SeedResult("sec_user", 2))
    return results
