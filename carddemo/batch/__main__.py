from __future__ import annotations

import os
import time
from pathlib import Path

import django
import typer

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "carddemo.settings")
django.setup()

from models.account import Account
from models.card import Card, CardXref
from models.customer import Customer
from models.transaction import DailyReject, DailyTransaction, Transaction
from models.trantype import TransactionType
from services.interest import apply_interest
from services.posting import post_daily_transactions
from services.seed import seed_all

app = typer.Typer(help="CardDemo batch job equivalents.")
OUTPUT_DIR = Path(os.getenv("CARDDEMO_OUTPUT_DIR", "runtime/output"))


def _ensure_output_dir(path: Path = OUTPUT_DIR) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


@app.command()
def seed(only: str | None = typer.Option(None, help="Seed only one logical file.")) -> None:
    for result in seed_all(only=only):
        typer.echo(f"{result.name}: {result.count}")


def _seed_one(name: str) -> None:
    for result in seed_all(only=name):
        typer.echo(f"{result.name}: {result.count}")


@app.command("acctfile")
def acctfile() -> None:
    _seed_one("account")


@app.command("cardfile")
def cardfile() -> None:
    _seed_one("card")


@app.command("custfile")
def custfile() -> None:
    _seed_one("customer")


@app.command("xrefile")
def xrefile() -> None:
    _seed_one("card_xref")


@app.command("tranfile")
def tranfile() -> None:
    _seed_one("daily_transaction")


@app.command("discgrp")
def discgrp() -> None:
    _seed_one("disclosure_group")


@app.command("trancatg")
def trancatg() -> None:
    _seed_one("transaction_category")


@app.command("trantype")
def trantype() -> None:
    _seed_one("transaction_type")


@app.command("tcatbalf")
def tcatbalf() -> None:
    _seed_one("tran_cat_balance")


@app.command("dusrsecj")
def dusrsecj() -> None:
    _seed_one("sec_user")


@app.command()
def posttran() -> None:
    result = post_daily_transactions()
    typer.echo(f"transactions processed: {result.processed}")
    typer.echo(f"transactions posted: {result.posted}")
    typer.echo(f"transactions rejected: {result.rejected}")
    if result.rejected:
        raise typer.Exit(code=4)


@app.command()
def intcalc() -> None:
    result = apply_interest()
    typer.echo(f"accounts updated: {result.accounts}")
    typer.echo(f"total interest: {result.total_interest}")


@app.command()
def creastmt(output_dir: Path = OUTPUT_DIR / "statements") -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for account in Account.objects.order_by("acct_id"):
        card_numbers = list(
            CardXref.objects.filter(xref_acct_id=account.acct_id).values_list(
                "xref_card_num", flat=True
            )
        )
        transactions = Transaction.objects.filter(card_num__in=card_numbers).order_by("orig_ts")
        path = output_dir / f"statement-{int(account.acct_id):011d}.txt"
        with path.open("w", encoding="utf-8") as handle:
            handle.write(f"ACCOUNT {int(account.acct_id):011d}\n")
            handle.write(f"STATUS {account.acct_active_status}\n")
            handle.write(f"CURRENT BALANCE {account.acct_curr_bal}\n")
            handle.write("TRANSACTIONS\n")
            for tran in transactions:
                handle.write(f"{tran.tran_id} {tran.orig_ts} {tran.amt} {tran.desc}\n")
        written += 1
    typer.echo(f"statements written: {written}")


@app.command()
def tranrept(start: str = "", end: str = "", output: Path = OUTPUT_DIR / "tranrept.txt") -> None:
    qs = Transaction.objects.all()
    if start:
        qs = qs.filter(orig_ts__gte=start)
    if end:
        qs = qs.filter(orig_ts__lte=end)
    _ensure_output_dir(output.parent)
    total = sum(row.amt for row in qs)
    with output.open("w", encoding="utf-8") as handle:
        handle.write(f"TRANREPT {start} {end}\n".strip() + "\n")
        handle.write(f"transactions: {qs.count()}\n")
        handle.write(f"total amount: {total}\n")
        for row in qs.order_by("orig_ts", "tran_id"):
            handle.write(f"{row.tran_id},{row.card_num},{row.amt},{row.orig_ts},{row.desc}\n")
    typer.echo(f"TRANREPT {start} {end}".strip())
    typer.echo(f"transactions: {qs.count()}")
    typer.echo(f"total amount: {total}")
    typer.echo(f"wrote {output}")


@app.command()
def combtran(output: Path = OUTPUT_DIR / "combined_daily_transactions.txt") -> None:
    _ensure_output_dir(output.parent)
    count = 0
    with output.open("w", encoding="utf-8") as handle:
        for row in DailyTransaction.objects.order_by("orig_ts", "dalytran_id"):
            handle.write(f"{row.dalytran_id},{row.card_num},{row.amt},{row.orig_ts},{row.desc}\n")
            count += 1
    typer.echo(f"COMBTRAN sorted daily transactions: {count}")
    typer.echo(f"wrote {output}")


@app.command()
def tranbkp(output: Path = OUTPUT_DIR / "transaction_backup.txt") -> None:
    _ensure_output_dir(output.parent)
    with output.open("w", encoding="utf-8") as handle:
        for row in Transaction.objects.order_by("tran_id"):
            handle.write(f"{row.tran_id},{row.card_num},{row.amt},{row.orig_ts}\n")
    typer.echo(f"wrote {output}")


@app.command()
def tranidx() -> None:
    typer.echo("TRANIDX parity stub: PostgreSQL indexes are maintained online.")


@app.command()
def cbpaup0() -> None:
    from models.auth import PendingAuthDetail

    count, _ = PendingAuthDetail.objects.filter(match_status="E").delete()
    typer.echo(f"purged pending auth details: {count}")


@app.command()
def mnttrdb2(file: Path = typer.Option(Path("app/data/ASCII/trantype.txt"))) -> None:
    from services.common.ebcdic_loader import TRAN_TYPE_LAYOUT, read_fixed_width

    rows = read_fixed_width(file, TRAN_TYPE_LAYOUT)
    for row in rows:
        TransactionType.objects.update_or_create(
            tr_type=row["tr_type"],
            defaults={"tr_description": row["tr_description"]},
        )
    typer.echo(f"transaction types applied: {len(rows)}")


@app.command()
def tranextr(output: Path = OUTPUT_DIR / "transaction_types_extract.txt") -> None:
    _ensure_output_dir(output.parent)
    with output.open("w", encoding="utf-8") as handle:
        for row in TransactionType.objects.order_by("tr_type"):
            handle.write(f"{row.tr_type}{row.tr_description:<50}\n")
    typer.echo(f"wrote {output}")


@app.command()
def readacct(acct_id: str) -> None:
    account = Account.objects.filter(acct_id=acct_id).first()
    if not account:
        typer.echo("ACCOUNT RECORD NOT FOUND")
        raise typer.Exit(code=4)
    typer.echo(f"{int(account.acct_id):011d} {account.acct_active_status} {account.acct_curr_bal}")


@app.command()
def readcard(card_num: str) -> None:
    card = Card.objects.filter(card_num=card_num).first()
    if not card:
        typer.echo("CARD RECORD NOT FOUND")
        raise typer.Exit(code=4)
    typer.echo(f"{card.card_num} {int(card.card_acct_id):011d} {card.card_active_status}")


@app.command()
def readcust(cust_id: str) -> None:
    customer = Customer.objects.filter(cust_id=cust_id).first()
    if not customer:
        typer.echo("CUSTOMER RECORD NOT FOUND")
        raise typer.Exit(code=4)
    typer.echo(f"{int(customer.cust_id):09d} {customer.cust_first_name} {customer.cust_last_name}")


@app.command()
def readxref(card_num: str) -> None:
    xref = CardXref.objects.filter(xref_card_num=card_num).first()
    if not xref:
        typer.echo("XREF RECORD NOT FOUND")
        raise typer.Exit(code=4)
    typer.echo(f"{xref.xref_card_num} {int(xref.xref_cust_id):09d} {int(xref.xref_acct_id):011d}")


@app.command()
def cbexport(output: Path = OUTPUT_DIR / "accounts_export.csv") -> None:
    _ensure_output_dir(output.parent)
    with output.open("w", encoding="utf-8") as handle:
        handle.write("acct_id,status,current_balance,credit_limit\n")
        for account in Account.objects.order_by("acct_id"):
            handle.write(
                f"{int(account.acct_id):011d},{account.acct_active_status},{account.acct_curr_bal},{account.acct_credit_limit}\n"
            )
    typer.echo(f"wrote {output}")


@app.command()
def cbimport(input_file: Path) -> None:
    typer.echo(f"CBIMPORT accepted {input_file}; source-controlled seed files remain canonical")


@app.command()
def waitstep(seconds: int = 1) -> None:
    time.sleep(seconds)
    typer.echo(f"waited {seconds} seconds")


@app.command()
def closefil() -> None:
    typer.echo("CLOSEFIL parity no-op")


@app.command()
def openfil() -> None:
    typer.echo("OPENFIL parity no-op")


@app.command()
def counts() -> None:
    typer.echo(f"accounts: {Account.objects.count()}")
    typer.echo(f"daily transactions: {DailyTransaction.objects.count()}")
    typer.echo(f"transactions: {Transaction.objects.count()}")
    typer.echo(f"daily rejects: {DailyReject.objects.count()}")


if __name__ == "__main__":
    app()
