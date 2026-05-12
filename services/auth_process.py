from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from models.account import Account
from models.auth import AuthFraud, PendingAuthDetail, PendingAuthSummary
from models.card import Card, CardXref


@dataclass(frozen=True)
class AuthRequest:
    auth_date: str
    auth_time: str
    card_num: str
    auth_type: str
    card_expiry_date: str
    message_type: str
    message_source: str
    processing_code: str
    transaction_amt: Decimal
    merchant_catagory_code: str
    acqr_country_code: str
    pos_entry_mode: int
    merchant_id: str
    merchant_name: str
    merchant_city: str
    merchant_state: str
    merchant_zip: str
    transaction_id: str


def parse_auth_request(payload: bytes | str) -> AuthRequest:
    raw = payload.decode("latin-1") if isinstance(payload, bytes) else payload
    return AuthRequest(
        auth_date=raw[0:6],
        auth_time=raw[6:12],
        card_num=raw[12:28],
        auth_type=raw[28:32],
        card_expiry_date=raw[32:36],
        message_type=raw[36:42],
        message_source=raw[42:48],
        processing_code=raw[48:54],
        transaction_amt=Decimal(raw[54:68].strip() or "0"),
        merchant_catagory_code=raw[68:72],
        acqr_country_code=raw[72:75],
        pos_entry_mode=int(raw[75:77].strip() or "0"),
        merchant_id=raw[77:92].rstrip(),
        merchant_name=raw[92:114].rstrip(),
        merchant_city=raw[114:127].rstrip(),
        merchant_state=raw[127:129],
        merchant_zip=raw[129:138].rstrip(),
        transaction_id=raw[138:153].rstrip(),
    )


def process_authorization(request: AuthRequest) -> str:
    xref = CardXref.objects.filter(xref_card_num=request.card_num).first()
    card = Card.objects.filter(card_num=request.card_num).first()
    approved = xref is not None and card is not None and card.card_active_status == "Y"
    resp_code = "00" if approved else "05"
    reason = "    " if approved else "CARD"
    approved_amt = request.transaction_amt if approved else Decimal("0.00")

    with transaction.atomic():
        if xref and card:
            account = Account.objects.get(acct_id=xref.xref_acct_id)
            summary, _ = PendingAuthSummary.objects.get_or_create(
                card_num=request.card_num,
                defaults={
                    "acct_id": xref.xref_acct_id,
                    "cust_id": xref.xref_cust_id,
                    "auth_status": "P",
                    "account_status": account.acct_active_status,
                    "credit_limit": account.acct_credit_limit,
                    "cash_limit": account.acct_cash_credit_limit,
                    "credit_balance": account.acct_curr_bal,
                    "cash_balance": Decimal("0.00"),
                },
            )
            if approved:
                summary.approved_auth_cnt += 1
                summary.approved_auth_amt += approved_amt
            else:
                summary.declined_auth_cnt += 1
                summary.declined_auth_amt += request.transaction_amt
            summary.save()

        PendingAuthDetail.objects.update_or_create(
            auth_date=request.auth_date,
            auth_time=request.auth_time,
            defaults={
                "auth_orig_date": request.auth_date,
                "auth_orig_time": request.auth_time,
                "card_num": request.card_num,
                "auth_type": request.auth_type,
                "card_expiry_date": request.card_expiry_date,
                "message_type": request.message_type,
                "message_source": request.message_source,
                "auth_id_code": "PYAUTH",
                "auth_resp_code": resp_code,
                "auth_resp_reason": reason,
                "processing_code": request.processing_code,
                "transaction_amt": request.transaction_amt,
                "approved_amt": approved_amt,
                "merchant_catagory_code": request.merchant_catagory_code,
                "acqr_country_code": request.acqr_country_code,
                "pos_entry_mode": request.pos_entry_mode,
                "merchant_id": request.merchant_id,
                "merchant_name": request.merchant_name,
                "merchant_city": request.merchant_city,
                "merchant_state": request.merchant_state,
                "merchant_zip": request.merchant_zip,
                "transaction_id": request.transaction_id,
                "match_status": "P" if approved else "D",
            },
        )

    return f"{request.card_num:<16}{request.transaction_id:<15}{'PYAUTH':<6}{resp_code:<2}{reason:<4}{approved_amt:+013.2f}"


def mark_fraud(detail: PendingAuthDetail) -> AuthFraud:
    detail.match_status = "E"
    detail.auth_fraud = "F"
    detail.fraud_rpt_date = timezone.localdate().strftime("%Y%m%d")
    detail.save(update_fields=["match_status", "auth_fraud", "fraud_rpt_date"])
    xref = CardXref.objects.filter(xref_card_num=detail.card_num).first()
    return AuthFraud.objects.create(
        card_num=detail.card_num,
        auth_ts=timezone.now(),
        auth_type=detail.auth_type,
        card_expiry_date=detail.card_expiry_date,
        message_type=detail.message_type,
        message_source=detail.message_source,
        auth_id_code=detail.auth_id_code,
        auth_resp_code=detail.auth_resp_code,
        auth_resp_reason=detail.auth_resp_reason,
        processing_code=detail.processing_code,
        transaction_amt=detail.transaction_amt,
        approved_amt=detail.approved_amt,
        merchant_catagory_code=detail.merchant_catagory_code,
        acqr_country_code=detail.acqr_country_code,
        pos_entry_mode=detail.pos_entry_mode,
        merchant_id=detail.merchant_id,
        merchant_name=detail.merchant_name,
        merchant_city=detail.merchant_city,
        merchant_state=detail.merchant_state,
        merchant_zip=detail.merchant_zip,
        transaction_id=detail.transaction_id,
        match_status=detail.match_status,
        auth_fraud=detail.auth_fraud,
        acct_id=xref.xref_acct_id if xref else None,
        cust_id=xref.xref_cust_id if xref else None,
    )
