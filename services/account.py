from __future__ import annotations

from decimal import Decimal

from models.account import Account
from models.card import CardXref
from models.customer import Customer


def get_account_view(acct_id: str | int | Decimal) -> dict | None:
    try:
        account = Account.objects.get(acct_id=acct_id)
    except Account.DoesNotExist:
        return None

    xref = CardXref.objects.filter(xref_acct_id=account.acct_id).order_by("xref_card_num").first()
    customer = None
    if xref:
        customer = Customer.objects.filter(cust_id=xref.xref_cust_id).first()

    return {"account": account, "card_xref": xref, "customer": customer}
