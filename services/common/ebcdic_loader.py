from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from .cobol_numerics import parse_display_int, parse_zoned_decimal

ROOT_DIR = Path(__file__).resolve().parents[2]
ASCII_DIR = ROOT_DIR / "app" / "data" / "ASCII"


@dataclass(frozen=True)
class FieldSpec:
    name: str
    width: int
    parser: Callable[[str], object] = lambda raw: raw.rstrip()


def chars(name: str, width: int) -> FieldSpec:
    return FieldSpec(name, width, lambda raw: raw.rstrip())


def digits(name: str, width: int) -> FieldSpec:
    return FieldSpec(name, width, parse_display_int)


def zoned(name: str, width: int, scale: int = 2) -> FieldSpec:
    return FieldSpec(name, width, lambda raw: parse_zoned_decimal(raw, scale=scale))


def read_fixed_width(path: Path, specs: Iterable[FieldSpec]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    field_specs = list(specs)
    for line in path.read_text(encoding="latin-1").splitlines():
        pos = 0
        row: dict[str, object] = {}
        for spec in field_specs:
            raw = line[pos : pos + spec.width]
            pos += spec.width
            if spec.name != "_":
                row[spec.name] = spec.parser(raw)
        rows.append(row)
    return rows


ACCOUNT_LAYOUT = [
    digits("acct_id", 11),
    chars("acct_active_status", 1),
    zoned("acct_curr_bal", 12),
    zoned("acct_credit_limit", 12),
    zoned("acct_cash_credit_limit", 12),
    chars("acct_open_date", 10),
    chars("acct_expiraion_date", 10),
    chars("acct_reissue_date", 10),
    zoned("acct_curr_cyc_credit", 12),
    zoned("acct_curr_cyc_debit", 12),
    chars("acct_addr_zip", 10),
    chars("acct_group_id", 10),
    chars("_", 178),
]

CUSTOMER_LAYOUT = [
    digits("cust_id", 9),
    chars("cust_first_name", 25),
    chars("cust_middle_name", 25),
    chars("cust_last_name", 25),
    chars("cust_addr_line_1", 50),
    chars("cust_addr_line_2", 50),
    chars("cust_addr_line_3", 50),
    chars("cust_addr_state_cd", 2),
    chars("cust_addr_country_cd", 3),
    chars("cust_addr_zip", 10),
    chars("cust_phone_num_1", 15),
    chars("cust_phone_num_2", 15),
    digits("cust_ssn", 9),
    chars("cust_govt_issued_id", 20),
    chars("cust_dob_yyyy_mm_dd", 10),
    chars("cust_eft_account_id", 10),
    chars("cust_pri_card_holder_ind", 1),
    digits("cust_fico_credit_score", 3),
    chars("_", 168),
]

CARD_LAYOUT = [
    chars("card_num", 16),
    digits("card_acct_id", 11),
    digits("card_cvv_cd", 3),
    chars("card_embossed_name", 50),
    chars("card_expiraion_date", 10),
    chars("card_active_status", 1),
    chars("_", 59),
]

CARD_XREF_LAYOUT = [
    chars("xref_card_num", 16),
    digits("xref_cust_id", 9),
    digits("xref_acct_id", 11),
]

TRAN_TYPE_LAYOUT = [
    chars("tr_type", 2),
    chars("tr_description", 50),
    chars("_", 8),
]

TRAN_CATEGORY_LAYOUT = [
    chars("tr_type", 2),
    chars("tr_cat_cd", 4),
    chars("tr_cat_type_desc", 50),
    chars("_", 4),
]

DISCLOSURE_GROUP_LAYOUT = [
    chars("acct_group_id", 10),
    chars("tran_type_cd", 2),
    chars("tran_cat_cd", 4),
    zoned("int_rate", 6),
    chars("_", 28),
]

TRAN_CAT_BALANCE_LAYOUT = [
    digits("acct_id", 11),
    chars("type_cd", 2),
    chars("cat_cd", 4),
    zoned("tran_cat_bal", 11),
    chars("_", 22),
]

DAILY_TRANSACTION_LAYOUT = [
    chars("dalytran_id", 16),
    chars("type_cd", 2),
    chars("cat_cd", 4),
    chars("source", 10),
    chars("desc", 100),
    zoned("amt", 11),
    digits("merchant_id", 9),
    chars("merchant_name", 50),
    chars("merchant_city", 50),
    chars("merchant_zip", 10),
    chars("card_num", 16),
    chars("orig_ts", 26),
    chars("proc_ts", 26),
    chars("_", 20),
]
