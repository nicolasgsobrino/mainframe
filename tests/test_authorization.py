from __future__ import annotations

import pytest

from models.auth import PendingAuthDetail, PendingAuthSummary
from services.auth_process import parse_auth_request, process_authorization
from services.seed import seed_all


@pytest.mark.django_db
def test_authorization_creates_pending_rows_for_valid_card():
    seed_all()
    raw = (
        "240101"
        "120000"
        "0500024453765740"
        "AUTH"
        "2505"
        "0100  "
        "POS   "
        "000000"
        "+0000000123.45"
        "5411"
        "USA"
        "01"
        f"{'MID123':<15}"
        f"{'Demo Merchant':<22}"
        f"{'Seattle':<13}"
        "WA"
        f"{'98101':<9}"
        f"{'TX123':<15}"
    )

    response = process_authorization(parse_auth_request(raw))

    assert response[31:37].strip() == "PYAUTH"
    assert PendingAuthSummary.objects.filter(card_num="0500024453765740").exists()
    assert PendingAuthDetail.objects.filter(card_num="0500024453765740").exists()


@pytest.mark.django_db
def test_authorization_allows_same_second_distinct_transactions():
    seed_all()
    base = (
        "240101"
        "120000"
        "0500024453765740"
        "AUTH"
        "2505"
        "0100  "
        "POS   "
        "000000"
        "+0000000123.45"
        "5411"
        "USA"
        "01"
        f"{'MID123':<15}"
        f"{'Demo Merchant':<22}"
        f"{'Seattle':<13}"
        "WA"
        f"{'98101':<9}"
    )

    process_authorization(parse_auth_request(base + f"{'TX123':<15}"))
    process_authorization(parse_auth_request(base + f"{'TX124':<15}"))

    summary = PendingAuthSummary.objects.get(card_num="0500024453765740")
    assert summary.approved_auth_cnt == 2
    assert PendingAuthDetail.objects.filter(
        card_num="0500024453765740", auth_date="240101", auth_time="120000"
    ).count() == 2
