"""CardDemo data models — translated from COBOL copybooks.

VSAM record layouts (CVACT01Y, CVCUS01Y, CVCRD01Y, CVTRA05Y, CSUSR01Y)
mapped to Python dataclasses.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional


@dataclass
class Account:
    """ACCOUNT-RECORD (CVACT01Y) — 300-byte VSAM KSDS."""
    id: int
    active_status: str = "Y"
    curr_bal: Decimal = Decimal("0")
    credit_limit: Decimal = Decimal("0")
    cash_credit_limit: Decimal = Decimal("0")
    open_date: Optional[date] = None
    expiry_date: Optional[date] = None
    reissue_date: Optional[date] = None
    curr_cyc_credit: Decimal = Decimal("0")
    curr_cyc_debit: Decimal = Decimal("0")
    group_id: str = ""


@dataclass
class Customer:
    """CUSTOMER-RECORD (CVCUS01Y) — 500-byte VSAM KSDS."""
    id: int
    first_name: str = ""
    middle_name: str = ""
    last_name: str = ""
    addr_line1: str = ""
    addr_line2: str = ""
    city: str = ""
    state_cd: str = ""
    zip_code: str = ""
    country_cd: str = "USA"
    phone1: str = ""
    phone2: str = ""
    ssn: str = ""
    dob: Optional[date] = None
    fico_score: int = 0
    eft_account_id: str = ""
    pri_holder_ind: str = "Y"


@dataclass
class CreditCard:
    """CARD-RECORD (CVCRD01Y) — 150-byte VSAM KSDS."""
    num: str
    acct_id: int
    cvv: str = ""
    embossed_name: str = ""
    expiry_date: Optional[date] = None
    active_status: str = "Y"


@dataclass
class CardXref:
    """CARD-XREF-RECORD (CVACT03Y) — account/card/customer cross-reference."""
    card_num: str
    cust_id: int
    acct_id: int


@dataclass
class Transaction:
    """TRAN-RECORD (CVTRA05Y) — 350-byte VSAM KSDS."""
    id: str
    type_cd: str = ""
    cat_cd: int = 0
    source: str = ""
    desc: str = ""
    amt: Decimal = Decimal("0")
    merchant_id: int = 0
    merchant_name: str = ""
    merchant_city: str = ""
    merchant_zip: str = ""
    card_num: str = ""
    orig_ts: Optional[datetime] = None
    proc_ts: Optional[datetime] = None


@dataclass
class User:
    """SEC-USER-DATA (CSUSR01Y) — 80-byte USRSEC VSAM KSDS."""
    id: str
    first_name: str = ""
    last_name: str = ""
    password: str = ""
    user_type: str = "U"  # A=Admin, U=User


@dataclass
class DisclosureGroup:
    """Interest rate disclosure group — linked to accounts via group_id."""
    group_id: str
    interest_rate: Decimal = Decimal("0")


@dataclass
class TranCatBalance:
    """Transaction category balance — for interest calculation (CVTRA01Y)."""
    acct_id: int
    type_cd: str = ""
    cat_cd: int = 0
    balance: Decimal = Decimal("0")
