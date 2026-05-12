from __future__ import annotations

import pytest

from services.seed import seed_all


@pytest.mark.django_db
def test_account_view_renders_seeded_account(client):
    seed_all()
    client.post("/tx/CC00", {"user_id": "USER0001", "password": "PASSWORD", "pfkey": "ENTER"})

    response = client.post("/tx/CAVW", {"acct_id": "1", "pfkey": "ENTER"})

    assert response.status_code == 200
    content = response.content.decode()
    assert "Account View" in content
    assert "Current Bal" in content
    assert "00000000001" in content or "1" in content


@pytest.mark.django_db
def test_account_view_rejects_non_numeric_account_id(client):
    seed_all()
    client.post("/tx/CC00", {"user_id": "USER0001", "password": "PASSWORD", "pfkey": "ENTER"})

    response = client.post("/tx/CAVW", {"acct_id": "USER0001", "pfkey": "ENTER"})

    assert response.status_code == 200
    content = response.content.decode()
    assert "Account number must be numeric" in content
    assert "ValidationError" not in content
