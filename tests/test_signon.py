from __future__ import annotations

import pytest

from services.seed import seed_all


@pytest.mark.django_db
def test_signon_accepts_original_demo_users(client):
    seed_all()

    response = client.post(
        "/tx/CC00",
        {"user_id": "ADMIN001", "password": "PASSWORD", "pfkey": "ENTER"},
    )

    assert response.status_code == 302
    assert response["Location"] == "/tx/CM00"


@pytest.mark.django_db
def test_main_menu_shows_admin_options(client):
    seed_all()
    client.post("/tx/CC00", {"user_id": "ADMIN001", "password": "PASSWORD", "pfkey": "ENTER"})

    response = client.get("/tx/CM00")

    assert response.status_code == 200
    content = response.content.decode()
    assert " 1. Account View" in content
    assert "11. Pending Authorization View" in content
    assert " 6. Transaction Type Maintenance (Db2)" in content
