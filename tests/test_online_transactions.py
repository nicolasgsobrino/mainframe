from __future__ import annotations

import pytest

from models.account import Account
from models.card import Card
from models.transaction import Transaction
from models.trantype import TransactionType
from models.user import SecUser
from services.seed import seed_all


def sign_in(client, user_id: str = "ADMIN001") -> None:
    client.post("/tx/CC00", {"user_id": user_id, "password": "PASSWORD", "pfkey": "ENTER"})


@pytest.mark.django_db
def test_card_list_view_and_update(client):
    seed_all()
    sign_in(client)
    card = Card.objects.order_by("card_num").first()

    response = client.get("/tx/CCLI")
    assert response.status_code == 200
    assert "Credit Card List" in response.content.decode()

    response = client.post("/tx/CCDL", {"card_num": card.card_num, "pfkey": "ENTER"})
    assert response.status_code == 200
    assert card.card_num in response.content.decode()

    response = client.post(
        "/tx/CCUP",
        {
            "card_num": card.card_num,
            "card_expiraion_date": card.card_expiraion_date,
            "card_active_status": "N",
            "pfkey": "ENTER",
        },
    )
    assert response.status_code == 200
    assert "Record updated" in response.content.decode()
    card.refresh_from_db()
    assert card.card_active_status == "N"


@pytest.mark.django_db
def test_account_update_and_bill_payment(client):
    seed_all()
    sign_in(client)
    account = Account.objects.get(acct_id=1)

    response = client.post(
        "/tx/CAUP",
        {
            "acct_id": "1",
            "acct_active_status": "Y",
            "acct_credit_limit": "9999.00",
            "pfkey": "ENTER",
        },
    )
    assert response.status_code == 200
    assert "Record updated" in response.content.decode()
    account.refresh_from_db()
    assert account.acct_credit_limit == 9999

    response = client.post(
        "/tx/CB00",
        {"acct_id": "1", "amount": "10.00", "pfkey": "ENTER"},
    )
    assert response.status_code == 200
    assert "Record updated" in response.content.decode()


@pytest.mark.django_db
def test_bill_payment_rejects_non_positive_amounts(client):
    seed_all()
    sign_in(client)
    account = Account.objects.get(acct_id=1)
    original_balance = account.acct_curr_bal
    original_debit = account.acct_curr_cyc_debit

    response = client.post(
        "/tx/CB00",
        {"acct_id": "1", "amount": "-10.00", "pfkey": "ENTER"},
    )

    assert response.status_code == 200
    assert "Payment amount must be greater than 0" in response.content.decode()
    account.refresh_from_db()
    assert account.acct_curr_bal == original_balance
    assert account.acct_curr_cyc_debit == original_debit


@pytest.mark.django_db
def test_transaction_add_list_and_view(client):
    seed_all()
    sign_in(client)
    card = Card.objects.order_by("card_num").first()

    response = client.post(
        "/tx/CT02",
        {
            "tran_id": "TSTTRAN000000001",
            "card_num": card.card_num,
            "type_cd": "01",
            "cat_cd": "0001",
            "amt": "12.34",
            "merchant_id": "1",
            "desc": "Test transaction",
            "pfkey": "ENTER",
        },
    )
    assert response.status_code == 200
    assert "Record created" in response.content.decode()
    assert Transaction.objects.filter(tran_id="TSTTRAN000000001").exists()

    response = client.get("/tx/CT00")
    assert response.status_code == 200
    assert "TSTTRAN000000001" in response.content.decode()

    response = client.post("/tx/CT01", {"tran_id": "TSTTRAN000000001", "pfkey": "ENTER"})
    assert response.status_code == 200
    assert "Test transaction" in response.content.decode()


@pytest.mark.django_db
def test_admin_user_and_transaction_type_maintenance(client):
    seed_all()
    sign_in(client)

    response = client.post(
        "/tx/CU01",
        {
            "usr_id": "TEST0001",
            "usr_fname": "Test",
            "usr_lname": "User",
            "usr_pwd": "PASSWORD",
            "usr_type": "U",
            "pfkey": "ENTER",
        },
    )
    assert response.status_code == 200
    assert "Record created" in response.content.decode()
    assert SecUser.objects.filter(usr_id="TEST0001").exists()

    response = client.post(
        "/tx/CU02",
        {
            "usr_id": "TEST0001",
            "usr_fname": "Changed",
            "usr_lname": "User",
            "usr_type": "A",
            "pfkey": "ENTER",
        },
    )
    assert response.status_code == 200
    assert "Record updated" in response.content.decode()

    response = client.post("/tx/CU03", {"usr_id": "TEST0001", "pfkey": "ENTER"})
    assert response.status_code == 200
    assert "Record deleted" in response.content.decode()

    response = client.post(
        "/tx/CTTU",
        {"tr_type": "99", "description": "Test Type", "pfkey": "ENTER"},
    )
    assert response.status_code == 200
    assert "Transaction type updated" in response.content.decode()
    assert TransactionType.objects.filter(tr_type="99").exists()


@pytest.mark.django_db
def test_reports_and_admin_required(client):
    seed_all()
    sign_in(client, "USER0001")

    response = client.get("/tx/CR00")
    assert response.status_code == 200
    assert "Transaction Reports" in response.content.decode()

    response = client.get("/tx/CU00")
    assert response.status_code == 200
    assert "Admin access required" in response.content.decode()
