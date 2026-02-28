"""Comprehensive tests for CardDemo Python edition.

Tests all 18 business operations translated from COBOL.
"""
import sys
from datetime import date, datetime
from decimal import Decimal

from models import Account, Customer, CreditCard, CardXref, Transaction, User, DisclosureGroup
from services import (
    CardDemoService, AuthenticationError, ValidationError,
    NotFoundError, InsufficientFundsError,
)


def setup() -> CardDemoService:
    svc = CardDemoService()
    svc.load_sample_data()
    return svc


passed = 0
failed = 0
results = []


def test(name: str, fn):
    global passed, failed
    try:
        fn()
        passed += 1
        results.append(("PASS", name))
    except Exception as e:
        failed += 1
        results.append(("FAIL", f"{name}: {e}"))


# ─── SIGN-ON (COSGN00C) ───────────────────────────────

def test_sign_on_admin():
    svc = setup()
    user = svc.sign_on("ADMIN001", "PASSWORD")
    assert user.user_type == "A"
    assert user.first_name == "MARGARET"

def test_sign_on_user():
    svc = setup()
    user = svc.sign_on("USER0001", "PASSWORD")
    assert user.user_type == "U"

def test_sign_on_wrong_password():
    svc = setup()
    try:
        svc.sign_on("ADMIN001", "WRONG")
        assert False, "Should have raised"
    except AuthenticationError:
        pass

def test_sign_on_user_not_found():
    svc = setup()
    try:
        svc.sign_on("NOBODY", "PASSWORD")
        assert False
    except AuthenticationError:
        pass

def test_sign_on_empty_id():
    svc = setup()
    try:
        svc.sign_on("", "PASSWORD")
        assert False
    except ValidationError:
        pass

def test_sign_on_case_insensitive():
    svc = setup()
    user = svc.sign_on("admin001", "password")
    assert user.id == "ADMIN001"


# ─── ACCOUNT VIEW (COACTVWC) ──────────────────────────

def test_account_view():
    svc = setup()
    acct = svc.get_account(11)
    assert acct.curr_bal == Decimal("7500.50")
    assert acct.active_status == "Y"

def test_account_not_found():
    svc = setup()
    try:
        svc.get_account(99999)
        assert False
    except NotFoundError:
        pass

def test_customer_for_account():
    svc = setup()
    cust = svc.get_customer_for_account(11)
    assert cust is not None
    assert cust.first_name == "MARGARET"


# ─── ACCOUNT UPDATE (COACTUPC) ────────────────────────

def test_account_update_status():
    svc = setup()
    acct = svc.update_account(11, active_status="N")
    assert acct.active_status == "N"

def test_account_update_balance():
    svc = setup()
    acct = svc.update_account(11, curr_bal=Decimal("5000.00"))
    assert acct.curr_bal == Decimal("5000.00")

def test_account_update_bad_status():
    svc = setup()
    try:
        svc.update_account(11, active_status="X")
        assert False
    except ValidationError:
        pass

def test_customer_update_fico():
    svc = setup()
    cust = svc.update_customer(1001, fico_score=750)
    assert cust.fico_score == 750

def test_customer_update_bad_fico():
    svc = setup()
    try:
        svc.update_customer(1001, fico_score=100)
        assert False
    except ValidationError:
        pass


# ─── CARD LIST / VIEW (COCRDLIC / COCRDSLC) ──────────

def test_card_list_all():
    svc = setup()
    cards, total = svc.list_cards()
    assert total == 5
    assert len(cards) == 5

def test_card_list_by_account():
    svc = setup()
    cards, total = svc.list_cards(acct_id=11)
    assert total == 1
    assert cards[0].embossed_name == "MARGARET GOLD"

def test_card_view():
    svc = setup()
    card = svc.get_card("4111111111111111")
    assert card.acct_id == 11


# ─── CARD UPDATE (COCRDUPC) ──────────────────────────

def test_card_update_name():
    svc = setup()
    card = svc.update_card("4111111111111111", embossed_name="M. GOLD")
    assert card.embossed_name == "M. GOLD"

def test_card_update_status():
    svc = setup()
    card = svc.update_card("4111111111111111", active_status="N")
    assert card.active_status == "N"

def test_card_update_bad_status():
    svc = setup()
    try:
        svc.update_card("4111111111111111", active_status="X")
        assert False
    except ValidationError:
        pass

def test_card_not_found():
    svc = setup()
    try:
        svc.update_card("0000000000000000", embossed_name="X")
        assert False
    except NotFoundError:
        pass


# ─── TRANSACTION LIST / VIEW (COTRN00C / COTRN01C) ──

def test_transaction_list():
    svc = setup()
    txns, total = svc.list_transactions()
    assert total == 20
    assert len(txns) == 10  # per_page=10

def test_transaction_list_page2():
    svc = setup()
    txns, total = svc.list_transactions(page=2)
    assert len(txns) == 10

def test_transaction_view():
    svc = setup()
    txn = svc.get_transaction("0000000000000001")
    assert txn.source == "ONLINE"


# ─── TRANSACTION ADD (COTRN02C) ──────────────────────

def test_transaction_add():
    svc = setup()
    txn = svc.add_transaction(
        acct_id=11, amt=Decimal("250.00"), desc="Test purchase",
        merchant_name="TestMerchant", merchant_city="NYC",
    )
    assert txn.amt == Decimal("250.00")
    assert txn.card_num == "4111111111111111"
    assert len(txn.id) == 16

def test_transaction_add_zero():
    svc = setup()
    try:
        svc.add_transaction(acct_id=11, amt=Decimal("0"))
        assert False
    except ValidationError:
        pass

def test_transaction_add_bad_account():
    svc = setup()
    try:
        svc.add_transaction(acct_id=99999, amt=Decimal("100"))
        assert False
    except NotFoundError:
        pass


# ─── BILL PAYMENT (COBIL00C) ────────────────────────

def test_bill_payment():
    svc = setup()
    original = svc.accounts[11].curr_bal
    paid, txn = svc.pay_bill(11)
    assert paid == original
    assert svc.accounts[11].curr_bal == Decimal("0")
    assert txn.type_cd == "02"

def test_bill_payment_zero_balance():
    svc = setup()
    svc.accounts[11].curr_bal = Decimal("0")
    try:
        svc.pay_bill(11)
        assert False
    except InsufficientFundsError:
        pass

def test_bill_payment_creates_transaction():
    svc = setup()
    before = len(svc.transactions)
    svc.pay_bill(11)
    assert len(svc.transactions) == before + 1


# ─── USER CRUD (COUSR00C-03C) ───────────────────────

def test_user_list():
    svc = setup()
    users = svc.list_users()
    assert len(users) == 3

def test_user_add():
    svc = setup()
    user = svc.add_user("USER0099", "JOHN", "DOE", "PASS1234", "U")
    assert user.id == "USER0099"
    assert len(svc.users) == 4

def test_user_add_duplicate():
    svc = setup()
    try:
        svc.add_user("ADMIN001", "X", "Y", "Z", "A")
        assert False
    except ValidationError:
        pass

def test_user_add_empty_id():
    svc = setup()
    try:
        svc.add_user("", "X", "Y", "Z", "U")
        assert False
    except ValidationError:
        pass

def test_user_add_bad_type():
    svc = setup()
    try:
        svc.add_user("TEST001", "X", "Y", "Z", "X")
        assert False
    except ValidationError:
        pass

def test_user_update():
    svc = setup()
    user = svc.update_user("USER0001", first_name="UPDATED")
    assert user.first_name == "UPDATED"

def test_user_delete():
    svc = setup()
    svc.delete_user("USER0002")
    assert "USER0002" not in svc.users

def test_user_delete_self_guard():
    svc = setup()
    try:
        svc.delete_user("ADMIN001", current_user_id="ADMIN001")
        assert False
    except ValidationError:
        pass

def test_user_delete_not_found():
    svc = setup()
    try:
        svc.delete_user("NOBODY")
        assert False
    except NotFoundError:
        pass


# ─── INTEREST CALCULATION (CBACT04C) ────────────────

def test_interest_calculation():
    svc = setup()
    results = svc.calculate_interest()
    assert len(results) > 0
    for r in results:
        assert r["interest"] > 0
        assert r["new_balance"] > 0

def test_interest_only_active():
    svc = setup()
    svc.accounts[11].active_status = "N"
    results = svc.calculate_interest()
    acct_ids = [r["account_id"] for r in results]
    assert 11 not in acct_ids

def test_interest_formula():
    svc = setup()
    acct = svc.accounts[11]
    bal_before = acct.curr_bal
    grp = svc.disclosure_groups[acct.group_id]
    expected_interest = (bal_before * grp.interest_rate / Decimal("1200")).quantize(Decimal("0.01"))
    results = svc.calculate_interest()
    r = next(r for r in results if r["account_id"] == 11)
    assert abs(Decimal(str(r["interest"])) - expected_interest) < Decimal("0.02")


# ─── TRANSACTION POSTING (CBTRN02C) ────────────────

def test_post_transaction():
    svc = setup()
    txn = Transaction(
        id="POST001", type_cd="01", cat_cd=1, source="BATCH",
        amt=Decimal("100"), card_num="4111111111111111",
        orig_ts=datetime.now(), proc_ts=datetime.now(),
    )
    bal_before = svc.accounts[11].curr_bal
    ok = svc.post_transaction(txn)
    assert ok
    assert svc.accounts[11].curr_bal == bal_before + Decimal("100")

def test_post_transaction_inactive_card():
    svc = setup()
    txn = Transaction(
        id="POST002", type_cd="01", cat_cd=1, source="BATCH",
        amt=Decimal("100"), card_num="3400000000000009",
        orig_ts=datetime.now(), proc_ts=datetime.now(),
    )
    ok = svc.post_transaction(txn)
    assert not ok

def test_post_transaction_over_limit():
    svc = setup()
    txn = Transaction(
        id="POST003", type_cd="01", cat_cd=1, source="BATCH",
        amt=Decimal("999999"), card_num="4111111111111111",
        orig_ts=datetime.now(), proc_ts=datetime.now(),
    )
    ok = svc.post_transaction(txn)
    assert not ok


# ─── STATEMENT GENERATION (CBSTM03A) ───────────────

def test_statement_generation():
    svc = setup()
    stmt = svc.generate_statement(11)
    assert stmt["account_id"] == 11
    assert stmt["customer_name"] != "N/A"
    assert stmt["total_transactions"] > 0


# ─── TRANSACTION REPORT (CBTRN03C) ─────────────────

def test_transaction_report():
    svc = setup()
    report = svc.generate_report(date(2026, 2, 1), date(2026, 2, 28))
    assert report["total_count"] > 0

def test_transaction_report_bad_dates():
    svc = setup()
    try:
        svc.generate_report(date(2026, 3, 1), date(2026, 2, 1))
        assert False
    except ValidationError:
        pass

def test_transaction_report_empty_range():
    svc = setup()
    report = svc.generate_report(date(2020, 1, 1), date(2020, 1, 31))
    assert report["total_count"] == 0


# ─── RUN ALL ────────────────────────────────────────

if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for t in tests:
        test(t.__name__, t)

    print(f"\n{'='*60}")
    print(f"  CardDemo Python Tests: {passed}/{passed+failed}")
    print(f"{'='*60}")
    for status, name in results:
        marker = "✓" if status == "PASS" else "✗"
        print(f"  {marker} {name}")
    print()

    if failed:
        print(f"  {failed} FAILED")
        sys.exit(1)
    else:
        print(f"  ALL {passed} PASSED")
