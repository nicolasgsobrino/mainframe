from __future__ import annotations

import pytest
from typer.testing import CliRunner

from carddemo.batch.__main__ import app
from models.card import Card
from services.posting import post_daily_transactions
from services.seed import seed_all

runner = CliRunner()


@pytest.mark.django_db
def test_batch_output_commands_write_expected_files(tmp_path):
    seed_all()
    post_daily_transactions()

    report = tmp_path / "tranrept.txt"
    result = runner.invoke(app, ["tranrept", "--output", str(report)])
    assert result.exit_code == 0
    assert report.exists()
    assert "transactions:" in report.read_text()

    combined = tmp_path / "combined.txt"
    result = runner.invoke(app, ["combtran", "--output", str(combined)])
    assert result.exit_code == 0
    assert combined.exists()
    assert "COMBTRAN sorted daily transactions" in result.output

    export = tmp_path / "accounts.csv"
    result = runner.invoke(app, ["cbexport", "--output", str(export)])
    assert result.exit_code == 0
    assert export.read_text().startswith("acct_id,status,current_balance,credit_limit")


@pytest.mark.django_db
def test_batch_read_commands_return_seeded_records():
    seed_all()
    card = Card.objects.order_by("card_num").first()

    result = runner.invoke(app, ["readacct", "1"])
    assert result.exit_code == 0
    assert "00000000001" in result.output

    result = runner.invoke(app, ["readcard", card.card_num])
    assert result.exit_code == 0
    assert card.card_num in result.output

    result = runner.invoke(app, ["readxref", card.card_num])
    assert result.exit_code == 0
    assert card.card_num in result.output
