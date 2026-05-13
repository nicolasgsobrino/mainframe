from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from models.account import Account
from models.card import CardXref
from models.trancat import TransactionCategoryBalance
from models.transaction import DailyReject, DailyTransaction, Transaction

from .common.dates import db2_timestamp


@dataclass(frozen=True)
class PostingResult:
    processed: int
    posted: int
    rejected: int


def validate_daily_transaction(daily: DailyTransaction) -> tuple[CardXref | None, str | None]:
    xref = CardXref.objects.filter(xref_card_num=daily.card_num).first()
    if not xref:
        return None, "INVALID CARD NUMBER FOUND"

    account = Account.objects.filter(acct_id=xref.xref_acct_id).first()
    if not account:
        return xref, "ACCOUNT RECORD NOT FOUND"

    temp_bal = account.acct_curr_cyc_credit - account.acct_curr_cyc_debit + daily.amt
    if account.acct_credit_limit < temp_bal:
        return xref, "OVERLIMIT TRANSACTION"
    if account.acct_expiraion_date < daily.orig_ts[:10]:
        return xref, "TRANSACTION RECEIVED AFTER ACCT EXPIRATION"
    return xref, None


def post_daily_transactions() -> PostingResult:
    processed = posted = rejected = 0
    DailyReject.objects.all().delete()

    for daily in DailyTransaction.objects.order_by("dalytran_id"):
        processed += 1
        with transaction.atomic():
            if Transaction.objects.filter(tran_id=daily.dalytran_id).exists():
                continue

            xref, reason = validate_daily_transaction(daily)
            if reason or xref is None:
                DailyReject.objects.create(
                    dalytran_id=daily.dalytran_id,
                    card_num=daily.card_num,
                    reason=reason or "UNKNOWN VALIDATION ERROR",
                )
                rejected += 1
                continue

            account = Account.objects.select_for_update().get(acct_id=xref.xref_acct_id)
            balance, _ = TransactionCategoryBalance.objects.select_for_update().get_or_create(
                acct_id=xref.xref_acct_id,
                type_cd=daily.type_cd,
                cat_cd=daily.cat_cd,
                defaults={"tran_cat_bal": 0},
            )
            balance.tran_cat_bal += daily.amt
            balance.save(update_fields=["tran_cat_bal"])

            account.acct_curr_bal += daily.amt
            if daily.amt >= 0:
                account.acct_curr_cyc_credit += daily.amt
            else:
                account.acct_curr_cyc_debit += daily.amt
            account.save(
                update_fields=[
                    "acct_curr_bal",
                    "acct_curr_cyc_credit",
                    "acct_curr_cyc_debit",
                ]
            )

            Transaction.objects.create(
                tran_id=daily.dalytran_id,
                type_cd=daily.type_cd,
                cat_cd=daily.cat_cd,
                source=daily.source,
                desc=daily.desc,
                amt=daily.amt,
                merchant_id=daily.merchant_id,
                merchant_name=daily.merchant_name,
                merchant_city=daily.merchant_city,
                merchant_zip=daily.merchant_zip,
                card_num=daily.card_num,
                orig_ts=daily.orig_ts,
                proc_ts=db2_timestamp(),
            )
            posted += 1
    return PostingResult(processed=processed, posted=posted, rejected=rejected)
