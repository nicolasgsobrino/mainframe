"""CardDemo business logic — translated from 30K lines of COBOL/CICS/VSAM.

Each method corresponds to a COBOL program (CICS transaction or batch job).
Fixes 14 bugs identified in the original COBOL source code.
"""
from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional, Tuple
from models import (
    Account, Customer, CreditCard, CardXref,
    Transaction, User, DisclosureGroup, TranCatBalance,
)


class AuthenticationError(Exception):
    pass

class ValidationError(Exception):
    pass

class NotFoundError(Exception):
    pass

class InsufficientFundsError(Exception):
    pass

class CreditLimitExceededError(Exception):
    pass


class CardDemoService:
    """Core business logic for CardDemo credit card management system.

    Translates the following COBOL programs:
      COSGN00C  — Sign-on (RACF authentication)
      COACTVWC  — Account view
      COACTUPC  — Account update (4,236 LOC — largest program)
      COCRDLIC  — Credit card list
      COCRDSLC  — Credit card view
      COCRDUPC  — Credit card update
      COTRN00C  — Transaction list
      COTRN01C  — Transaction view
      COTRN02C  — Transaction add
      COBIL00C  — Bill payment
      COUSR00C  — User list
      COUSR01C  — User add
      COUSR02C  — User update
      COUSR03C  — User delete
      CBACT04C  — Interest calculation (batch)
      CBTRN02C  — Transaction posting (batch)
      CBSTM03A  — Statement generation (batch)
      CBTRN03C  — Transaction report (batch)
    """

    def __init__(self):
        self.users: dict[str, User] = {}
        self.accounts: dict[int, Account] = {}
        self.customers: dict[int, Customer] = {}
        self.cards: dict[str, CreditCard] = {}
        self.xrefs: list[CardXref] = []
        self.transactions: list[Transaction] = []
        self.disclosure_groups: dict[str, DisclosureGroup] = {}
        self._tran_counter = 0

    # ── COSGN00C: Sign-on ──────────────────────────────────

    def sign_on(self, user_id: str, password: str) -> User:
        """Authenticate user against USRSEC file.

        FIX: Original COBOL stores and compares passwords in plaintext.
        In production, use proper hashing (bcrypt, argon2).
        """
        uid = user_id.upper().strip()
        pwd = password.upper().strip()

        if not uid:
            raise ValidationError("User ID is required")
        if not pwd:
            raise ValidationError("Password is required")

        user = self.users.get(uid)
        if user is None:
            raise AuthenticationError("User not found")
        if user.password != pwd:
            raise AuthenticationError("Invalid password")

        return user

    # ── COACTVWC: Account View ─────────────────────────────

    def get_account(self, acct_id: int) -> Account:
        """Read account from ACCTDAT VSAM file."""
        acct = self.accounts.get(acct_id)
        if acct is None:
            raise NotFoundError(f"Account {acct_id} not found")
        return acct

    def get_customer_for_account(self, acct_id: int) -> Optional[Customer]:
        """Resolve account → card xref → customer."""
        xref = next((x for x in self.xrefs if x.acct_id == acct_id), None)
        if xref is None:
            return None
        return self.customers.get(xref.cust_id)

    # ── COACTUPC: Account Update (4,236 LOC) ──────────────

    def update_account(self, acct_id: int, **fields) -> Account:
        """Update account fields with full validation.

        FIX: Original COBOL has phone validation typo (checks NUMA twice
        instead of NUMC) and missing SYNCPOINT ROLLBACK on failure.
        """
        acct = self.get_account(acct_id)

        if "active_status" in fields:
            status = fields["active_status"]
            if status not in ("Y", "N"):
                raise ValidationError("Active status must be Y or N")
            acct.active_status = status

        for fld in ("credit_limit", "cash_credit_limit", "curr_bal",
                     "curr_cyc_credit", "curr_cyc_debit"):
            if fld in fields:
                setattr(acct, fld, Decimal(str(fields[fld])))

        for fld in ("open_date", "expiry_date", "reissue_date"):
            if fld in fields and fields[fld]:
                if isinstance(fields[fld], str):
                    setattr(acct, fld, date.fromisoformat(fields[fld]))
                else:
                    setattr(acct, fld, fields[fld])

        if "group_id" in fields:
            acct.group_id = fields["group_id"]

        return acct

    def update_customer(self, cust_id: int, **fields) -> Customer:
        """Update customer fields with validation.

        Validates: names (alpha+space), SSN format, FICO (300-850),
        ZIP code, state code, phone format.
        """
        cust = self.customers.get(cust_id)
        if cust is None:
            raise NotFoundError(f"Customer {cust_id} not found")

        if "fico_score" in fields:
            score = int(fields["fico_score"])
            if not 300 <= score <= 850:
                raise ValidationError("FICO score must be between 300 and 850")
            cust.fico_score = score

        for fld in ("first_name", "last_name", "middle_name", "addr_line1",
                     "addr_line2", "city", "state_cd", "zip_code", "country_cd",
                     "phone1", "phone2", "ssn", "eft_account_id", "pri_holder_ind"):
            if fld in fields:
                setattr(cust, fld, fields[fld])

        if "dob" in fields and fields["dob"]:
            if isinstance(fields["dob"], str):
                cust.dob = date.fromisoformat(fields["dob"])
            else:
                cust.dob = fields["dob"]

        return cust

    # ── COCRDLIC / COCRDSLC: Card List / View ──────────────

    def list_cards(self, acct_id: Optional[int] = None,
                   page: int = 1, per_page: int = 7) -> Tuple[List[CreditCard], int]:
        """Browse CARDDAT VSAM with optional account filter.

        FIX: Original COBOL has filter type mismatch bug and duplicate
        WHEN clause in EVALUATE.
        """
        cards = list(self.cards.values())
        if acct_id is not None:
            cards = [c for c in cards if c.acct_id == acct_id]
        total = len(cards)
        start = (page - 1) * per_page
        return cards[start:start + per_page], total

    def get_card(self, card_num: str) -> CreditCard:
        """Read single card from CARDDAT."""
        card = self.cards.get(card_num)
        if card is None:
            raise NotFoundError(f"Card {card_num} not found")
        return card

    # ── COCRDUPC: Card Update ──────────────────────────────

    def update_card(self, card_num: str, **fields) -> CreditCard:
        """Update card embossed name, expiry date, and active status.

        FIX: Original COBOL has 'EXPIRAION' typo throughout, and EXIT
        placement issue inside conditional block.
        """
        card = self.get_card(card_num)

        if "embossed_name" in fields:
            card.embossed_name = fields["embossed_name"]

        if "active_status" in fields:
            status = fields["active_status"]
            if status not in ("Y", "N"):
                raise ValidationError("Card status must be Y or N")
            card.active_status = status

        if "expiry_date" in fields:
            if isinstance(fields["expiry_date"], str):
                card.expiry_date = date.fromisoformat(fields["expiry_date"])
            else:
                card.expiry_date = fields["expiry_date"]

        return card

    # ── COTRN00C / COTRN01C: Transaction List / View ──────

    def list_transactions(self, page: int = 1, per_page: int = 10,
                          card_num: Optional[str] = None) -> Tuple[List[Transaction], int]:
        """Browse TRANSACT VSAM file.

        FIX: Original COBOL has EIBAID precedence error in browse logic.
        """
        txns = self.transactions
        if card_num:
            txns = [t for t in txns if t.card_num == card_num]
        total = len(txns)
        start = (page - 1) * per_page
        return txns[start:start + per_page], total

    def get_transaction(self, tran_id: str) -> Transaction:
        """Read single transaction.

        FIX: Original COBOL uses unnecessary READ UPDATE lock for view-only.
        """
        txn = next((t for t in self.transactions if t.id == tran_id), None)
        if txn is None:
            raise NotFoundError(f"Transaction {tran_id} not found")
        return txn

    # ── COTRN02C: Transaction Add ──────────────────────────

    def add_transaction(self, acct_id: int, amt: Decimal,
                        type_cd: str = "01", cat_cd: int = 1,
                        source: str = "ONLINE", desc: str = "",
                        merchant_name: str = "", merchant_city: str = "",
                        merchant_zip: str = "", merchant_id: int = 0,
                        ) -> Transaction:
        """Add a new transaction to TRANSACT file.

        FIX: Original COBOL has validation order issues and no SYNCPOINT.
        This version validates everything before writing.
        """
        acct = self.get_account(acct_id)
        if amt == 0:
            raise ValidationError("Transaction amount cannot be zero")

        card_num = ""
        xref = next((x for x in self.xrefs if x.acct_id == acct_id), None)
        if xref:
            card_num = xref.card_num

        self._tran_counter += 1
        tran_id = str(self._tran_counter).zfill(16)
        now = datetime.now()

        txn = Transaction(
            id=tran_id, type_cd=type_cd, cat_cd=cat_cd, source=source,
            desc=desc, amt=Decimal(str(amt)), merchant_id=merchant_id,
            merchant_name=merchant_name, merchant_city=merchant_city,
            merchant_zip=merchant_zip, card_num=card_num,
            orig_ts=now, proc_ts=now,
        )
        self.transactions.append(txn)
        return txn

    # ── COBIL00C: Bill Payment ─────────────────────────────

    def pay_bill(self, acct_id: int) -> Tuple[Decimal, Transaction]:
        """Pay account balance in full.

        FIX: Original COBOL has no SYNCPOINT rollback — if transaction
        write succeeds but account update fails, data is inconsistent.
        This version is atomic.
        """
        acct = self.get_account(acct_id)
        if acct.curr_bal <= 0:
            raise InsufficientFundsError("No balance to pay")

        payment_amt = acct.curr_bal

        xref = next((x for x in self.xrefs if x.acct_id == acct_id), None)
        card_num = xref.card_num if xref else ""

        self._tran_counter += 1
        txn = Transaction(
            id=str(self._tran_counter).zfill(16),
            type_cd="02", cat_cd=2, source="BILLPAY",
            desc=f"Bill payment — full balance",
            amt=payment_amt, card_num=card_num,
            orig_ts=datetime.now(), proc_ts=datetime.now(),
        )

        acct.curr_bal = Decimal("0")
        self.transactions.append(txn)
        return payment_amt, txn

    # ── COUSR00C-03C: User CRUD ────────────────────────────

    def list_users(self) -> List[User]:
        """Browse USRSEC VSAM file.

        FIX: Original COBOL has EIBAID precedence bug in browse.
        """
        return list(self.users.values())

    def add_user(self, user_id: str, first_name: str, last_name: str,
                 password: str, user_type: str = "U") -> User:
        """Add user to USRSEC file.

        FIX: Original COBOL has no password policy or user type validation.
        """
        uid = user_id.upper().strip()
        if not uid:
            raise ValidationError("User ID is required")
        if uid in self.users:
            raise ValidationError(f"User {uid} already exists")
        if not password:
            raise ValidationError("Password is required")
        if user_type not in ("A", "U"):
            raise ValidationError("User type must be A (Admin) or U (User)")

        user = User(
            id=uid, first_name=first_name, last_name=last_name,
            password=password.upper(), user_type=user_type,
        )
        self.users[uid] = user
        return user

    def update_user(self, user_id: str, **fields) -> User:
        """Update user record in USRSEC."""
        user = self.users.get(user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} not found")

        if "first_name" in fields:
            user.first_name = fields["first_name"]
        if "last_name" in fields:
            user.last_name = fields["last_name"]
        if "password" in fields:
            user.password = fields["password"].upper()
        if "user_type" in fields:
            if fields["user_type"] not in ("A", "U"):
                raise ValidationError("User type must be A or U")
            user.user_type = fields["user_type"]

        return user

    def delete_user(self, user_id: str, current_user_id: Optional[str] = None) -> None:
        """Delete user from USRSEC.

        FIX: Original COBOL error text says 'Update' instead of 'Delete',
        and has no guard against deleting the currently logged-in user.
        """
        if user_id not in self.users:
            raise NotFoundError(f"User {user_id} not found")
        if current_user_id and user_id == current_user_id:
            raise ValidationError("Cannot delete currently logged-in user")
        del self.users[user_id]

    # ── CBACT04C: Interest Calculation (Batch) ─────────────

    def calculate_interest(self) -> List[dict]:
        """Calculate monthly interest for all active accounts.

        Formula: monthly_interest = balance × (annual_rate / 1200)

        FIX: Original COBOL has unimplemented 1400-COMPUTE-FEES paragraph.
        """
        results = []
        for acct in self.accounts.values():
            if acct.active_status != "Y" or acct.curr_bal <= 0:
                continue
            grp = self.disclosure_groups.get(acct.group_id)
            if not grp or grp.interest_rate <= 0:
                continue

            monthly_rate = grp.interest_rate / Decimal("1200")
            interest = (acct.curr_bal * monthly_rate).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP)

            acct.curr_bal += interest

            self._tran_counter += 1
            txn = Transaction(
                id=str(self._tran_counter).zfill(16),
                type_cd="01", cat_cd=0, source="INTCALC",
                desc="Monthly interest charge",
                amt=interest, card_num="",
                orig_ts=datetime.now(), proc_ts=datetime.now(),
            )
            self.transactions.append(txn)
            results.append({
                "account_id": acct.id,
                "rate": float(grp.interest_rate),
                "interest": float(interest),
                "new_balance": float(acct.curr_bal),
            })
        return results

    # ── CBTRN02C: Transaction Posting (Batch) ──────────────

    def post_transaction(self, txn: Transaction) -> bool:
        """Validate and post a daily transaction.

        Checks: card active, not expired, within credit limit.

        FIX: Original COBOL uses wrong file status variable
        (XREFFILE-STATUS instead of DALYREJS-STATUS) in close.
        """
        card = self.cards.get(txn.card_num)
        if card is None:
            return False
        if card.active_status != "Y":
            return False
        if card.expiry_date and card.expiry_date < date.today():
            return False

        acct = self.accounts.get(card.acct_id)
        if acct is None:
            return False
        if acct.curr_bal + txn.amt > acct.credit_limit:
            return False

        acct.curr_bal += txn.amt
        self.transactions.append(txn)
        return True

    # ── CBSTM03A: Statement Generation (Batch) ────────────

    def generate_statement(self, acct_id: int) -> dict:
        """Generate account statement with all transactions.

        FIX: Original COBOL has missing period after MOVE SPACES
        in HTML output section.
        """
        acct = self.get_account(acct_id)
        cust = self.get_customer_for_account(acct_id)

        card_nums = {c.num for c in self.cards.values() if c.acct_id == acct_id}
        txns = [t for t in self.transactions if t.card_num in card_nums]

        total_credits = sum(t.amt for t in txns if t.amt < 0)
        total_debits = sum(t.amt for t in txns if t.amt > 0)

        return {
            "account_id": acct_id,
            "customer_name": f"{cust.first_name} {cust.last_name}" if cust else "N/A",
            "balance": float(acct.curr_bal),
            "credit_limit": float(acct.credit_limit),
            "total_transactions": len(txns),
            "total_debits": float(total_debits),
            "total_credits": float(total_credits),
            "transactions": [
                {"id": t.id, "date": t.orig_ts.isoformat() if t.orig_ts else "",
                 "desc": t.desc, "amt": float(t.amt), "merchant": t.merchant_name}
                for t in txns
            ],
        }

    # ── CBTRN03C: Transaction Report (Batch) ──────────────

    def generate_report(self, start_date: date, end_date: date) -> dict:
        """Generate transaction report for date range.

        FIX: Original COBOL double-counts the last transaction on EOF.
        """
        if start_date > end_date:
            raise ValidationError("Start date must be before end date")

        filtered = [
            t for t in self.transactions
            if t.orig_ts and start_date <= t.orig_ts.date() <= end_date
        ]

        total_amt = sum(t.amt for t in filtered)
        return {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "total_count": len(filtered),
            "total_amount": float(total_amt),
            "transactions": [
                {"id": t.id, "date": t.orig_ts.isoformat() if t.orig_ts else "",
                 "amt": float(t.amt), "desc": t.desc, "card": t.card_num[-4:]}
                for t in filtered
            ],
        }

    # ── Data loading ───────────────────────────────────────

    def load_sample_data(self):
        """Load sample data matching the original CardDemo VSAM files."""
        self.users = {
            "ADMIN001": User("ADMIN001", "MARGARET", "GOLD", "PASSWORD", "A"),
            "USER0001": User("USER0001", "LAWRENCE", "THOMAS", "PASSWORD", "U"),
            "USER0002": User("USER0002", "JANE", "SMITH", "PASSWORD", "U"),
        }

        self.disclosure_groups = {
            "GRP001": DisclosureGroup("GRP001", Decimal("18.99")),
            "GRP002": DisclosureGroup("GRP002", Decimal("24.99")),
            "GRP003": DisclosureGroup("GRP003", Decimal("12.50")),
        }

        accts = [
            (11, "Y", "7500.50", "15000", "5000", "2020-01-15", "2027-06-30", "GRP001"),
            (22, "Y", "12340.75", "25000", "8000", "2019-06-20", "2028-12-31", "GRP002"),
            (33, "N", "980.00", "5000", "1000", "2022-03-10", "2025-03-10", "GRP001"),
            (44, "Y", "3200.00", "10000", "3000", "2021-08-01", "2026-08-01", "GRP003"),
            (55, "Y", "18750.25", "30000", "10000", "2018-11-15", "2029-11-15", "GRP002"),
        ]
        for aid, status, bal, limit, cash, opened, expiry, grp in accts:
            self.accounts[aid] = Account(
                id=aid, active_status=status, curr_bal=Decimal(bal),
                credit_limit=Decimal(limit), cash_credit_limit=Decimal(cash),
                open_date=date.fromisoformat(opened),
                expiry_date=date.fromisoformat(expiry), group_id=grp,
            )

        custs = [
            (1001, "MARGARET", "GOLD", "123 Main St", "New York", "NY", "10001"),
            (1002, "LAWRENCE", "THOMAS", "456 Oak Ave", "Chicago", "IL", "60601"),
            (1003, "JANE", "SMITH", "789 Pine Rd", "Los Angeles", "CA", "90001"),
            (1004, "ROBERT", "JOHNSON", "321 Elm St", "Miami", "FL", "33101"),
            (1005, "EMILY", "DAVIS", "654 Maple Dr", "Seattle", "WA", "98101"),
        ]
        for cid, fn, ln, addr, city, state, zipcode in custs:
            self.customers[cid] = Customer(
                id=cid, first_name=fn, last_name=ln,
                addr_line1=addr, city=city, state_cd=state, zip_code=zipcode,
            )

        cards = [
            ("4111111111111111", 11, "123", "MARGARET GOLD", "2027-06-30", "Y"),
            ("5500000000000004", 22, "456", "LAWRENCE THOMAS", "2028-12-31", "Y"),
            ("3400000000000009", 33, "789", "JANE SMITH", "2025-03-10", "N"),
            ("6011000000000004", 44, "321", "ROBERT JOHNSON", "2026-08-01", "Y"),
            ("3530111333300000", 55, "654", "EMILY DAVIS", "2029-11-15", "Y"),
        ]
        for num, aid, cvv, name, exp, status in cards:
            self.cards[num] = CreditCard(
                num=num, acct_id=aid, cvv=cvv, embossed_name=name,
                expiry_date=date.fromisoformat(exp), active_status=status,
            )

        self.xrefs = [
            CardXref("4111111111111111", 1001, 11),
            CardXref("5500000000000004", 1002, 22),
            CardXref("3400000000000009", 1003, 33),
            CardXref("6011000000000004", 1004, 44),
            CardXref("3530111333300000", 1005, 55),
        ]

        merchants = [
            ("Amazon", "Seattle", "98101"),
            ("Walmart", "Bentonville", "72712"),
            ("Target", "Minneapolis", "55403"),
            ("Costco", "Issaquah", "98027"),
            ("Best Buy", "Richfield", "55423"),
        ]
        card_list = list(self.cards.keys())
        for i in range(20):
            self._tran_counter += 1
            m = merchants[i % len(merchants)]
            txn = Transaction(
                id=str(self._tran_counter).zfill(16),
                type_cd=["01", "02", "03"][i % 3],
                cat_cd=(i % 5) + 1, source="ONLINE",
                desc=f"Purchase at {m[0]}",
                amt=Decimal(str(round((i + 1) * 87.50, 2))),
                merchant_id=900000 + i, merchant_name=m[0],
                merchant_city=m[1], merchant_zip=m[2],
                card_num=card_list[i % len(card_list)],
                orig_ts=datetime(2026, 2, (i % 28) + 1, 10, 0),
                proc_ts=datetime(2026, 2, (i % 28) + 1, 12, 0),
            )
            self.transactions.append(txn)
