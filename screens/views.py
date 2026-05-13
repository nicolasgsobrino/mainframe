from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib.auth.hashers import make_password
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from models.account import Account
from models.auth import PendingAuthDetail
from models.card import Card, CardXref
from models.customer import Customer
from models.transaction import Transaction
from models.trantype import TransactionType
from models.user import SecUser
from services import messages
from services.account import get_account_view
from services.auth_process import mark_fraud
from services.common.dates import db2_timestamp
from services.common.session import clear_commarea, get_commarea, save_commarea
from services.menu import menu_options, resolve_option
from services.signon import authenticate_user

from .pfkeys import ENTER, PF3, PF4, PF7, PF8, pressed

SCREEN_WIDTH = 80
SCREEN_HEIGHT = 24


def _blank() -> list[str]:
    return [" " * SCREEN_WIDTH for _ in range(SCREEN_HEIGHT)]


def _put(rows: list[str], row: int, col: int, text: object) -> None:
    text = str(text)
    idx = row - 1
    start = col - 1
    current = rows[idx]
    rows[idx] = (current[:start] + text + current[start + len(text) :])[:SCREEN_WIDTH].ljust(
        SCREEN_WIDTH
    )


def _screen(request: HttpRequest, template: str, rows: list[str], **context) -> HttpResponse:
    return render(
        request,
        template,
        {"rows": rows, "screen_text": "\n".join(rows), **context},
    )


def tx(request: HttpRequest, tranid: str = "CC00") -> HttpResponse:
    tranid = tranid.upper()
    handlers = {
        "CC00": signon,
        "CM00": main_menu,
        "CAVW": account_view,
        "CAUP": account_update,
        "CA00": admin_menu,
        "CCLI": card_list,
        "CCDL": card_view,
        "CCUP": card_update,
        "CT00": transaction_list,
        "CT01": transaction_view,
        "CT02": transaction_add,
        "CR00": report_menu,
        "CB00": bill_payment,
        "CU00": user_list,
        "CU01": user_add,
        "CU02": user_update,
        "CU03": user_delete,
        "CPVS": pending_auth_list,
        "CPVD": pending_auth_detail,
        "CTLI": trantype_list,
        "CTTU": trantype_update,
    }
    return handlers.get(tranid, placeholder)(request, tranid=tranid)


def signon(request: HttpRequest, tranid: str = "CC00") -> HttpResponse:
    message = ""
    if request.method == "POST":
        key = pressed(request)
        if key == PF4:
            clear_commarea(request.session)
            return redirect("screens:tx", tranid="CC00")
        user = authenticate_user(request.POST.get("user_id", ""), request.POST.get("password", ""))
        if user:
            save_commarea(
                request.session,
                from_tranid="CC00",
                to_tranid="CM00",
                user_id=user.usr_id,
                user_type=user.usr_type,
                last_map="COSGN00",
                last_mapset="COSGN00",
            )
            return redirect("screens:tx", tranid="CM00")
        message = messages.INVALID_USER

    rows = _blank()
    _put(rows, 1, 25, "AWS CardDemo - Signon")
    _put(rows, 5, 20, "User ID  . . . . . . . . .")
    _put(rows, 7, 20, "Password . . . . . . . . .")
    _put(rows, 12, 20, message or messages.ENTER_USER)
    _put(rows, 23, 2, "ENTER=Sign on  F4=Clear")
    return _screen(request, "screens/cosgn00.html", rows, message=message)


def main_menu(request: HttpRequest, tranid: str = "CM00") -> HttpResponse:
    commarea = get_commarea(request.session)
    if not commarea["user_id"]:
        return redirect("screens:tx", tranid="CC00")
    message = ""
    if request.method == "POST":
        key = pressed(request)
        if key == PF3:
            clear_commarea(request.session)
            rows = _blank()
            _put(rows, 12, 25, messages.THANK_YOU)
            return _screen(request, "screens/generic.html", rows)
        if key == ENTER:
            selected = resolve_option(commarea["user_type"], request.POST.get("option", ""))
            if selected:
                save_commarea(
                    request.session,
                    from_tranid="CM00",
                    from_program="COMEN01C",
                    to_tranid=selected.tranid,
                    to_program=selected.program,
                )
                return redirect("screens:tx", tranid=selected.tranid)
            message = messages.INVALID_MENU_OPTION

    rows = _blank()
    _put(rows, 1, 25, "AWS CardDemo - Main Menu")
    _put(rows, 3, 2, f"User: {commarea['user_id']}  Type: {commarea['user_type']}")
    for idx, option in enumerate(menu_options(commarea["user_type"]), start=5):
        _put(rows, idx, 10, f"{option.number:>2}. {option.name}")
    _put(rows, 20, 10, "Option . . .")
    _put(rows, 22, 2, message)
    _put(rows, 23, 2, "ENTER=Select  F3=Exit")
    return _screen(request, "screens/comen01.html", rows, message=message)


def admin_menu(request: HttpRequest, tranid: str = "CA00") -> HttpResponse:
    return main_menu(request, tranid)


def _clean_account_id(raw_value: object) -> tuple[str, str]:
    account_id = str(raw_value or "").strip()
    if not account_id:
        return "", messages.ACCOUNT_ID_REQUIRED
    if not account_id.isdecimal():
        return account_id, messages.INVALID_ACCOUNT_ID
    return account_id, ""


def _clean_decimal(raw_value: object, label: str = "Amount") -> tuple[Decimal | None, str]:
    value = str(raw_value or "").strip()
    if not value:
        return None, f"{label} is required"
    try:
        return Decimal(value), ""
    except InvalidOperation:
        return None, f"{label} must be numeric"


def _require_login(request: HttpRequest) -> dict | HttpResponse:
    commarea = get_commarea(request.session)
    if not commarea["user_id"]:
        return redirect("screens:tx", tranid="CC00")
    return commarea


def _require_admin(request: HttpRequest) -> tuple[dict | None, HttpResponse | None]:
    commarea = _require_login(request)
    if isinstance(commarea, HttpResponse):
        return None, commarea
    if commarea["user_type"] != "A":
        rows = _blank()
        _put(rows, 10, 24, messages.ADMIN_REQUIRED)
        _put(rows, 23, 2, "F3=Back")
        return None, _screen(request, "screens/generic.html", rows)
    return commarea, None


def _page_from_request(request: HttpRequest) -> int:
    try:
        page = int(request.POST.get("page", request.GET.get("page", "0")))
    except ValueError:
        page = 0
    key = pressed(request)
    if request.method == "POST" and key == PF7:
        page -= 1
    elif request.method == "POST" and key == PF8:
        page += 1
    return max(page, 0)


def _form_field(
    name: str,
    label: str,
    value: object = "",
    maxlength: int = 80,
    inputmode: str = "",
    field_type: str = "text",
) -> dict[str, object]:
    return {
        "name": name,
        "label": label,
        "value": value,
        "maxlength": maxlength,
        "inputmode": inputmode,
        "type": field_type,
    }


def _hidden_field(name: str, value: object) -> dict[str, object]:
    return {"name": name, "value": value}


def account_view(request: HttpRequest, tranid: str = "CAVW") -> HttpResponse:
    commarea = get_commarea(request.session)
    if not commarea["user_id"]:
        return redirect("screens:tx", tranid="CC00")
    message = ""
    detail = None
    acct_id = (request.POST.get("acct_id") or commarea.get("acct_id", "")).strip()
    if request.method == "POST":
        if pressed(request) == PF3:
            return redirect("screens:tx", tranid="CM00")
        if pressed(request) == PF4:
            acct_id = ""
        else:
            acct_id, message = _clean_account_id(acct_id)
            if not message:
                detail = get_account_view(acct_id)
                if detail:
                    save_commarea(request.session, acct_id=str(detail["account"].acct_id))
                else:
                    message = messages.ACCOUNT_NOT_FOUND
    elif acct_id:
        acct_id, message = _clean_account_id(acct_id)
        if not message:
            detail = get_account_view(acct_id)
            if not detail:
                message = messages.ACCOUNT_NOT_FOUND
            else:
                save_commarea(request.session, acct_id=str(detail["account"].acct_id))

    rows = _blank()
    _put(rows, 1, 25, "Account View")
    _put(rows, 4, 5, "Account ID . . .")
    if acct_id:
        _put(rows, 4, 24, acct_id)
    if detail:
        account = detail["account"]
        customer = detail["customer"]
        xref = detail["card_xref"]
        _put(rows, 7, 5, f"Status       : {account.acct_active_status}")
        _put(rows, 8, 5, f"Current Bal  : {account.acct_curr_bal}")
        _put(rows, 9, 5, f"Credit Limit : {account.acct_credit_limit}")
        _put(rows, 10, 5, f"Open Date    : {account.acct_open_date}")
        _put(rows, 11, 5, f"Expiry Date  : {account.acct_expiraion_date}")
        _put(rows, 12, 5, f"Group ID     : {account.acct_group_id}")
        if xref:
            _put(rows, 14, 5, f"Card Number  : {xref.xref_card_num}")
        if customer:
            _put(
                rows,
                16,
                5,
                f"Customer     : {customer.cust_first_name} {customer.cust_last_name}",
            )
            _put(rows, 17, 5, f"Address      : {customer.cust_addr_line_1}")
    _put(rows, 21, 5, message)
    _put(rows, 23, 2, "ENTER=View  F3=Back  F4=Clear")
    return _screen(request, "screens/coactvw.html", rows, message=message, acct_id=acct_id)


def account_update(request: HttpRequest, tranid: str = "CAUP") -> HttpResponse:
    commarea = _require_login(request)
    if isinstance(commarea, HttpResponse):
        return commarea
    message = ""
    acct_id = (request.POST.get("acct_id") or commarea.get("acct_id", "")).strip()
    account = None
    if request.method == "POST":
        key = pressed(request)
        if key == PF3:
            return redirect("screens:tx", tranid="CM00")
        if key == PF4:
            acct_id = ""
        else:
            acct_id, message = _clean_account_id(acct_id)
            if not message:
                account = Account.objects.filter(acct_id=acct_id).first()
                if not account:
                    message = messages.ACCOUNT_NOT_FOUND
                else:
                    status = request.POST.get("acct_active_status", account.acct_active_status).strip()[:1]
                    limit, amount_error = _clean_decimal(
                        request.POST.get("acct_credit_limit", account.acct_credit_limit),
                        "Credit limit",
                    )
                    if amount_error:
                        message = amount_error
                    else:
                        account.acct_active_status = status or account.acct_active_status
                        account.acct_credit_limit = limit
                        account.save(update_fields=["acct_active_status", "acct_credit_limit"])
                        save_commarea(request.session, acct_id=str(account.acct_id))
                        message = messages.RECORD_UPDATED
    elif acct_id:
        acct_id, message = _clean_account_id(acct_id)
        if not message:
            account = Account.objects.filter(acct_id=acct_id).first()
            if not account:
                message = messages.ACCOUNT_NOT_FOUND

    rows = _blank()
    _put(rows, 1, 25, "Account Update")
    _put(rows, 4, 5, "Account ID . . .")
    _put(rows, 4, 24, acct_id)
    if account:
        _put(rows, 7, 5, f"Status       : {account.acct_active_status}")
        _put(rows, 8, 5, f"Credit Limit : {account.acct_credit_limit}")
        _put(rows, 9, 5, f"Current Bal  : {account.acct_curr_bal}")
    _put(rows, 21, 5, message)
    fields = [
        _form_field("acct_id", "Account ID", acct_id, 11, "numeric"),
        _form_field(
            "acct_active_status",
            "Status",
            account.acct_active_status if account else "",
            1,
        ),
        _form_field(
            "acct_credit_limit",
            "Credit Limit",
            account.acct_credit_limit if account else "",
            12,
            "decimal",
        ),
    ]
    return _screen(request, "screens/form.html", rows, fields=fields, hidden_fields=[])


def card_list(request: HttpRequest, tranid: str = "CCLI") -> HttpResponse:
    commarea = _require_login(request)
    if isinstance(commarea, HttpResponse):
        return commarea
    if request.method == "POST" and pressed(request) == PF3:
        return redirect("screens:tx", tranid="CM00")
    page = _page_from_request(request)
    per_page = 12
    cards = list(Card.objects.order_by("card_num")[page * per_page : (page + 1) * per_page])
    rows = _blank()
    _put(rows, 1, 25, "Credit Card List")
    _put(rows, 3, 2, "Card Number       Account ID  Status  Name")
    for idx, card in enumerate(cards, start=5):
        _put(
            rows,
            idx,
            2,
            f"{card.card_num:<16} {int(card.card_acct_id):011d}   {card.card_active_status:<1}     {card.card_embossed_name[:30]}",
        )
    _put(rows, 21, 2, f"Page {page + 1}")
    _put(rows, 23, 2, "F3=Back  F7=Prev  F8=Next")
    return _screen(
        request,
        "screens/form.html",
        rows,
        fields=[],
        hidden_fields=[_hidden_field("page", page)],
    )


def _clean_card_num(raw_value: object) -> tuple[str, str]:
    card_num = str(raw_value or "").strip()
    if not card_num:
        return "", messages.CARD_NUMBER_REQUIRED
    if len(card_num) > 16:
        return card_num, "Card number is too long"
    return card_num, ""


def card_view(request: HttpRequest, tranid: str = "CCDL") -> HttpResponse:
    commarea = _require_login(request)
    if isinstance(commarea, HttpResponse):
        return commarea
    message = ""
    card_num = (request.POST.get("card_num") or commarea.get("card_num", "")).strip()
    card = None
    xref = None
    if request.method == "POST":
        key = pressed(request)
        if key == PF3:
            return redirect("screens:tx", tranid="CM00")
        if key == PF4:
            card_num = ""
        else:
            card_num, message = _clean_card_num(card_num)
            if not message:
                card = Card.objects.filter(card_num=card_num).first()
                xref = CardXref.objects.filter(xref_card_num=card_num).first()
                if card:
                    save_commarea(request.session, card_num=card.card_num, acct_id=str(card.card_acct_id))
                else:
                    message = messages.CARD_NOT_FOUND
    rows = _blank()
    _put(rows, 1, 25, "Credit Card View")
    _put(rows, 4, 5, "Card Number . . .")
    _put(rows, 4, 24, card_num)
    if card:
        _put(rows, 7, 5, f"Account ID : {int(card.card_acct_id):011d}")
        _put(rows, 8, 5, f"CVV        : {card.card_cvv_cd.zfill(3)}")
        _put(rows, 9, 5, f"Name       : {card.card_embossed_name}")
        _put(rows, 10, 5, f"Expiry     : {card.card_expiraion_date}")
        _put(rows, 11, 5, f"Status     : {card.card_active_status}")
        if xref:
            _put(rows, 13, 5, f"Customer ID: {int(xref.xref_cust_id):09d}")
    _put(rows, 21, 5, message)
    return _screen(
        request,
        "screens/form.html",
        rows,
        fields=[_form_field("card_num", "Card Number", card_num, 16, "numeric")],
        hidden_fields=[],
    )


def card_update(request: HttpRequest, tranid: str = "CCUP") -> HttpResponse:
    commarea = _require_login(request)
    if isinstance(commarea, HttpResponse):
        return commarea
    message = ""
    card_num = (request.POST.get("card_num") or commarea.get("card_num", "")).strip()
    card = None
    if request.method == "POST":
        key = pressed(request)
        if key == PF3:
            return redirect("screens:tx", tranid="CM00")
        if key == PF4:
            card_num = ""
        else:
            card_num, message = _clean_card_num(card_num)
            if not message:
                card = Card.objects.filter(card_num=card_num).first()
                if not card:
                    message = messages.CARD_NOT_FOUND
                else:
                    card.card_active_status = request.POST.get(
                        "card_active_status", card.card_active_status
                    ).strip()[:1] or card.card_active_status
                    card.card_expiraion_date = request.POST.get(
                        "card_expiraion_date", card.card_expiraion_date
                    ).strip()[:10] or card.card_expiraion_date
                    card.save(update_fields=["card_active_status", "card_expiraion_date"])
                    save_commarea(request.session, card_num=card.card_num, acct_id=str(card.card_acct_id))
                    message = messages.RECORD_UPDATED
    rows = _blank()
    _put(rows, 1, 24, "Credit Card Update")
    _put(rows, 4, 5, "Card Number . . .")
    _put(rows, 4, 24, card_num)
    if card:
        _put(rows, 7, 5, f"Name   : {card.card_embossed_name}")
        _put(rows, 8, 5, f"Expiry : {card.card_expiraion_date}")
        _put(rows, 9, 5, f"Status : {card.card_active_status}")
    _put(rows, 21, 5, message)
    return _screen(
        request,
        "screens/form.html",
        rows,
        fields=[
            _form_field("card_num", "Card Number", card_num, 16, "numeric"),
            _form_field("card_expiraion_date", "Expiry", card.card_expiraion_date if card else "", 10),
            _form_field("card_active_status", "Status", card.card_active_status if card else "", 1),
        ],
        hidden_fields=[],
    )


def transaction_list(request: HttpRequest, tranid: str = "CT00") -> HttpResponse:
    commarea = _require_login(request)
    if isinstance(commarea, HttpResponse):
        return commarea
    if request.method == "POST" and pressed(request) == PF3:
        return redirect("screens:tx", tranid="CM00")
    page = _page_from_request(request)
    per_page = 12
    qs = Transaction.objects.order_by("tran_id")
    acct_id = str(request.POST.get("acct_id") or commarea.get("acct_id") or "").strip()
    if acct_id and acct_id.isdecimal():
        card_nums = CardXref.objects.filter(xref_acct_id=acct_id).values_list("xref_card_num", flat=True)
        qs = qs.filter(card_num__in=list(card_nums))
    transactions = list(qs[page * per_page : (page + 1) * per_page])
    rows = _blank()
    _put(rows, 1, 25, "Transaction List")
    _put(rows, 3, 2, "Tran ID          Typ Cat  Amount     Card Number")
    for idx, tran in enumerate(transactions, start=5):
        _put(
            rows,
            idx,
            2,
            f"{tran.tran_id:<16} {tran.type_cd:<2}  {tran.cat_cd:<4} {tran.amt:>10} {tran.card_num:<16}",
        )
    _put(rows, 21, 2, f"Page {page + 1}")
    _put(rows, 23, 2, "ENTER=Filter  F3=Back  F7=Prev  F8=Next")
    return _screen(
        request,
        "screens/form.html",
        rows,
        fields=[_form_field("acct_id", "Account ID", acct_id, 11, "numeric")],
        hidden_fields=[_hidden_field("page", page)],
    )


def transaction_view(request: HttpRequest, tranid: str = "CT01") -> HttpResponse:
    commarea = _require_login(request)
    if isinstance(commarea, HttpResponse):
        return commarea
    message = ""
    tran_id = request.POST.get("tran_id", "").strip()
    tran = None
    if request.method == "POST":
        if pressed(request) == PF3:
            return redirect("screens:tx", tranid="CM00")
        if pressed(request) == PF4:
            tran_id = ""
        elif tran_id:
            tran = Transaction.objects.filter(tran_id=tran_id).first()
            if not tran:
                message = messages.INVALID_TRANSACTION
        else:
            message = "Please enter a transaction id"
    rows = _blank()
    _put(rows, 1, 25, "Transaction View")
    _put(rows, 4, 5, "Transaction ID . . .")
    _put(rows, 4, 28, tran_id)
    if tran:
        _put(rows, 7, 5, f"Type/Category : {tran.type_cd}/{tran.cat_cd}")
        _put(rows, 8, 5, f"Amount        : {tran.amt}")
        _put(rows, 9, 5, f"Card          : {tran.card_num}")
        _put(rows, 10, 5, f"Merchant      : {tran.merchant_name}")
        _put(rows, 11, 5, f"City/Zip      : {tran.merchant_city} {tran.merchant_zip}")
        _put(rows, 12, 5, f"Description   : {tran.desc[:55]}")
    _put(rows, 21, 5, message)
    return _screen(
        request,
        "screens/form.html",
        rows,
        fields=[_form_field("tran_id", "Transaction ID", tran_id, 16)],
        hidden_fields=[],
    )


def transaction_add(request: HttpRequest, tranid: str = "CT02") -> HttpResponse:
    commarea = _require_login(request)
    if isinstance(commarea, HttpResponse):
        return commarea
    message = ""
    values = {key: request.POST.get(key, "").strip() for key in request.POST}
    if request.method == "POST":
        if pressed(request) == PF3:
            return redirect("screens:tx", tranid="CM00")
        if pressed(request) == PF4:
            values = {}
        else:
            amount, message = _clean_decimal(values.get("amt"), "Amount")
            card_num, card_message = _clean_card_num(values.get("card_num"))
            if not message:
                message = card_message
            if not message and not Card.objects.filter(card_num=card_num).exists():
                message = messages.CARD_NOT_FOUND
            tran_id = values.get("tran_id", "")[:16]
            if not message and not tran_id:
                message = "Please enter a transaction id"
            if not message and Transaction.objects.filter(tran_id=tran_id).exists():
                message = "Transaction already exists"
            if not message:
                merchant_id, merchant_error = _clean_decimal(values.get("merchant_id") or "0", "Merchant id")
                if merchant_error:
                    message = merchant_error
            if not message:
                Transaction.objects.create(
                    tran_id=tran_id,
                    type_cd=(values.get("type_cd") or "01")[:2],
                    cat_cd=(values.get("cat_cd") or "0001")[:4],
                    source=(values.get("source") or "ONLINE")[:10],
                    desc=(values.get("desc") or "Online transaction")[:100],
                    amt=amount,
                    merchant_id=merchant_id,
                    merchant_name=(values.get("merchant_name") or "ONLINE")[:50],
                    merchant_city=(values.get("merchant_city") or "")[:50],
                    merchant_zip=(values.get("merchant_zip") or "")[:10],
                    card_num=card_num,
                    orig_ts=db2_timestamp(),
                    proc_ts=db2_timestamp(),
                )
                message = messages.RECORD_CREATED
    rows = _blank()
    _put(rows, 1, 25, "Transaction Add")
    _put(rows, 21, 5, message)
    fields = [
        _form_field("tran_id", "Transaction ID", values.get("tran_id", ""), 16),
        _form_field("card_num", "Card Number", values.get("card_num", ""), 16, "numeric"),
        _form_field("type_cd", "Type", values.get("type_cd", "01"), 2),
        _form_field("cat_cd", "Category", values.get("cat_cd", "0001"), 4),
        _form_field("amt", "Amount", values.get("amt", ""), 11, "decimal"),
        _form_field("merchant_id", "Merchant ID", values.get("merchant_id", "0"), 9, "numeric"),
        _form_field("desc", "Description", values.get("desc", ""), 100),
    ]
    return _screen(request, "screens/form.html", rows, fields=fields, hidden_fields=[])


def report_menu(request: HttpRequest, tranid: str = "CR00") -> HttpResponse:
    commarea = _require_login(request)
    if isinstance(commarea, HttpResponse):
        return commarea
    if request.method == "POST" and pressed(request) == PF3:
        return redirect("screens:tx", tranid="CM00")
    count = Transaction.objects.count()
    total = sum(tran.amt for tran in Transaction.objects.all())
    rows = _blank()
    _put(rows, 1, 24, "Transaction Reports")
    _put(rows, 6, 8, f"Posted transaction count : {count}")
    _put(rows, 7, 8, f"Posted transaction total : {total}")
    _put(rows, 23, 2, "F3=Back")
    return _screen(request, "screens/generic.html", rows)


def bill_payment(request: HttpRequest, tranid: str = "CB00") -> HttpResponse:
    commarea = _require_login(request)
    if isinstance(commarea, HttpResponse):
        return commarea
    message = ""
    acct_id = (request.POST.get("acct_id") or commarea.get("acct_id", "")).strip()
    amount_value = request.POST.get("amount", "").strip()
    if request.method == "POST":
        if pressed(request) == PF3:
            return redirect("screens:tx", tranid="CM00")
        acct_id, message = _clean_account_id(acct_id)
        amount, amount_message = _clean_decimal(amount_value, "Payment amount")
        if not message:
            message = amount_message
        if not message and amount is not None and amount <= 0:
            message = "Payment amount must be greater than 0"
        if not message:
            account = Account.objects.filter(acct_id=acct_id).first()
            if not account:
                message = messages.ACCOUNT_NOT_FOUND
            else:
                account.acct_curr_bal -= amount
                account.acct_curr_cyc_debit -= amount
                account.save(update_fields=["acct_curr_bal", "acct_curr_cyc_debit"])
                save_commarea(request.session, acct_id=str(account.acct_id))
                message = messages.RECORD_UPDATED
    rows = _blank()
    _put(rows, 1, 28, "Bill Payment")
    _put(rows, 21, 5, message)
    return _screen(
        request,
        "screens/form.html",
        rows,
        fields=[
            _form_field("acct_id", "Account ID", acct_id, 11, "numeric"),
            _form_field("amount", "Payment Amount", amount_value, 12, "decimal"),
        ],
        hidden_fields=[],
    )


def user_list(request: HttpRequest, tranid: str = "CU00") -> HttpResponse:
    _commarea, response = _require_admin(request)
    if response:
        return response
    if request.method == "POST" and pressed(request) == PF3:
        return redirect("screens:tx", tranid="CM00")
    page = _page_from_request(request)
    per_page = 12
    users = list(SecUser.objects.order_by("usr_id")[page * per_page : (page + 1) * per_page])
    rows = _blank()
    _put(rows, 1, 27, "User List")
    _put(rows, 3, 5, "User ID   Type  First Name           Last Name")
    for idx, user in enumerate(users, start=5):
        _put(rows, idx, 5, f"{user.usr_id:<8}  {user.usr_type:<1}    {user.usr_fname:<20} {user.usr_lname:<20}")
    _put(rows, 21, 5, f"Page {page + 1}")
    _put(rows, 23, 2, "F3=Back  F7=Prev  F8=Next")
    return _screen(
        request,
        "screens/form.html",
        rows,
        fields=[],
        hidden_fields=[_hidden_field("page", page)],
    )


def _clean_user_id(raw_value: object) -> tuple[str, str]:
    user_id = str(raw_value or "").strip().upper()
    if not user_id:
        return "", messages.INVALID_USER_ID
    if len(user_id) > 8:
        return user_id, "User id is too long"
    return user_id, ""


def user_add(request: HttpRequest, tranid: str = "CU01") -> HttpResponse:
    _commarea, response = _require_admin(request)
    if response:
        return response
    message = ""
    values = {key: request.POST.get(key, "").strip() for key in request.POST}
    if request.method == "POST":
        if pressed(request) == PF3:
            return redirect("screens:tx", tranid="CM00")
        if pressed(request) == PF4:
            values = {}
        else:
            user_id, message = _clean_user_id(values.get("usr_id"))
            if not message and SecUser.objects.filter(usr_id=user_id).exists():
                message = "User already exists"
            if not message and not values.get("usr_pwd"):
                message = "Password is required"
            if not message:
                SecUser.objects.create(
                    usr_id=user_id,
                    usr_fname=values.get("usr_fname", "")[:20],
                    usr_lname=values.get("usr_lname", "")[:20],
                    usr_pwd=make_password(values.get("usr_pwd", "")[:8]),
                    usr_type=(values.get("usr_type") or "U")[:1],
                )
                values["usr_id"] = user_id
                message = messages.RECORD_CREATED
    rows = _blank()
    _put(rows, 1, 29, "User Add")
    _put(rows, 21, 5, message)
    return _screen(
        request,
        "screens/form.html",
        rows,
        fields=[
            _form_field("usr_id", "User ID", values.get("usr_id", ""), 8),
            _form_field("usr_fname", "First Name", values.get("usr_fname", ""), 20),
            _form_field("usr_lname", "Last Name", values.get("usr_lname", ""), 20),
            _form_field("usr_pwd", "Password", "", 8, field_type="password"),
            _form_field("usr_type", "Type", values.get("usr_type", "U"), 1),
        ],
        hidden_fields=[],
    )


def user_update(request: HttpRequest, tranid: str = "CU02") -> HttpResponse:
    _commarea, response = _require_admin(request)
    if response:
        return response
    message = ""
    user = None
    values = {key: request.POST.get(key, "").strip() for key in request.POST}
    user_id = values.get("usr_id", "")
    if request.method == "POST":
        if pressed(request) == PF3:
            return redirect("screens:tx", tranid="CM00")
        if pressed(request) == PF4:
            values = {}
            user_id = ""
        else:
            user_id, message = _clean_user_id(user_id)
            if not message:
                user = SecUser.objects.filter(usr_id=user_id).first()
                if not user:
                    message = messages.USER_NOT_FOUND
                else:
                    user.usr_fname = values.get("usr_fname")[:20] or user.usr_fname
                    user.usr_lname = values.get("usr_lname")[:20] or user.usr_lname
                    user.usr_type = (values.get("usr_type") or user.usr_type)[:1]
                    if values.get("usr_pwd"):
                        user.usr_pwd = make_password(values["usr_pwd"][:8])
                        user.save(update_fields=["usr_fname", "usr_lname", "usr_type", "usr_pwd"])
                    else:
                        user.save(update_fields=["usr_fname", "usr_lname", "usr_type"])
                    message = messages.RECORD_UPDATED
    rows = _blank()
    _put(rows, 1, 28, "User Update")
    if user:
        _put(rows, 6, 5, f"Current: {user.usr_id} {user.usr_type} {user.usr_fname} {user.usr_lname}")
    _put(rows, 21, 5, message)
    return _screen(
        request,
        "screens/form.html",
        rows,
        fields=[
            _form_field("usr_id", "User ID", user_id, 8),
            _form_field("usr_fname", "First Name", user.usr_fname if user else values.get("usr_fname", ""), 20),
            _form_field("usr_lname", "Last Name", user.usr_lname if user else values.get("usr_lname", ""), 20),
            _form_field("usr_pwd", "New Password", "", 8, field_type="password"),
            _form_field("usr_type", "Type", user.usr_type if user else values.get("usr_type", "U"), 1),
        ],
        hidden_fields=[],
    )


def user_delete(request: HttpRequest, tranid: str = "CU03") -> HttpResponse:
    _commarea, response = _require_admin(request)
    if response:
        return response
    message = ""
    user_id = request.POST.get("usr_id", "").strip().upper()
    if request.method == "POST":
        if pressed(request) == PF3:
            return redirect("screens:tx", tranid="CM00")
        user_id, message = _clean_user_id(user_id)
        if not message:
            deleted, _ = SecUser.objects.filter(usr_id=user_id).delete()
            message = messages.RECORD_DELETED if deleted else messages.USER_NOT_FOUND
    rows = _blank()
    _put(rows, 1, 28, "User Delete")
    _put(rows, 21, 5, message)
    return _screen(
        request,
        "screens/form.html",
        rows,
        fields=[_form_field("usr_id", "User ID", user_id, 8)],
        hidden_fields=[],
    )


def pending_auth_list(request: HttpRequest, tranid: str = "CPVS") -> HttpResponse:
    commarea = _require_login(request)
    if isinstance(commarea, HttpResponse):
        return commarea
    if request.method == "POST" and pressed(request) == PF3:
        return redirect("screens:tx", tranid="CM00")
    rows = _blank()
    _put(rows, 1, 23, "Pending Authorization View")
    for idx, detail in enumerate(PendingAuthDetail.objects.order_by("auth_date", "auth_time")[:15], 4):
        _put(
            rows,
            idx,
            2,
            f"{detail.id:<4} {detail.auth_date} {detail.auth_time} {detail.card_num} {detail.transaction_amt} {detail.match_status}",
        )
    _put(rows, 23, 2, "ENTER=Detail  F3=Back")
    if request.method == "POST" and pressed(request) == ENTER and request.POST.get("detail_id"):
        return redirect(f"/tx/CPVD?detail_id={request.POST['detail_id'].strip()}")
    return _screen(
        request,
        "screens/form.html",
        rows,
        fields=[_form_field("detail_id", "Detail ID", request.POST.get("detail_id", ""), 10, "numeric")],
        hidden_fields=[],
    )


def pending_auth_detail(request: HttpRequest, tranid: str = "CPVD") -> HttpResponse:
    commarea = _require_login(request)
    if isinstance(commarea, HttpResponse):
        return commarea
    detail_id = request.POST.get("detail_id") or request.GET.get("detail_id")
    detail = PendingAuthDetail.objects.filter(id=detail_id).first() if detail_id else None
    message = ""
    if request.method == "POST" and pressed(request) == PF3:
        return redirect("screens:tx", tranid="CPVS")
    if request.method == "POST" and detail and request.POST.get("fraud") == "1":
        mark_fraud(detail)
        message = messages.RECORD_UPDATED
    rows = _blank()
    _put(rows, 1, 24, "Pending Authorization Detail")
    if detail:
        _put(rows, 4, 4, f"Card: {detail.card_num}")
        _put(rows, 5, 4, f"Amount: {detail.transaction_amt}")
        _put(rows, 6, 4, f"Merchant: {detail.merchant_name}")
        _put(rows, 7, 4, f"Status: {detail.match_status} Fraud: {detail.auth_fraud}")
    elif detail_id:
        message = "Pending authorization not found"
    _put(rows, 21, 4, message)
    _put(rows, 23, 2, "ENTER=Update  F3=Back")
    return _screen(
        request,
        "screens/form.html",
        rows,
        fields=[
            _form_field("detail_id", "Detail ID", detail_id or "", 10, "numeric"),
            _form_field("fraud", "Fraud 1=Yes", "", 1, "numeric"),
        ],
        hidden_fields=[],
    )


def trantype_list(request: HttpRequest, tranid: str = "CTLI") -> HttpResponse:
    _commarea, response = _require_admin(request)
    if response:
        return response
    if request.method == "POST" and pressed(request) == PF3:
        return redirect("screens:tx", tranid="CM00")
    rows = _blank()
    _put(rows, 1, 25, "Transaction Type List")
    for idx, item in enumerate(TransactionType.objects.order_by("tr_type")[:15], 4):
        _put(rows, idx, 5, f"{item.tr_type} {item.tr_description}")
    _put(rows, 23, 2, "F3=Back")
    return _screen(request, "screens/form.html", rows, fields=[], hidden_fields=[])


def trantype_update(request: HttpRequest, tranid: str = "CTTU") -> HttpResponse:
    _commarea, response = _require_admin(request)
    if response:
        return response
    message = ""
    values = {key: request.POST.get(key, "").strip() for key in request.POST}
    if request.method == "POST":
        if pressed(request) == PF3:
            return redirect("screens:tx", tranid="CM00")
        tr_type = values.get("tr_type", "")[:2]
        desc = values.get("description", "")[:50]
        if values.get("delete") == "1" and tr_type:
            deleted, _ = TransactionType.objects.filter(tr_type=tr_type).delete()
            message = messages.RECORD_DELETED if deleted else "Transaction type not found"
        elif tr_type and desc:
            TransactionType.objects.update_or_create(
                tr_type=tr_type, defaults={"tr_description": desc[:50]}
            )
            message = "Transaction type updated"
        else:
            message = "Type and description are required"
    rows = _blank()
    _put(rows, 1, 22, "Transaction Type Maintenance")
    _put(rows, 5, 5, "Type . . .")
    _put(rows, 7, 5, "Description")
    _put(rows, 9, 5, "Delete 1=Yes")
    _put(rows, 12, 5, message)
    _put(rows, 23, 2, "ENTER=Save  F3=Back")
    return _screen(
        request,
        "screens/form.html",
        rows,
        fields=[
            _form_field("tr_type", "Type", values.get("tr_type", ""), 2),
            _form_field("description", "Description", values.get("description", ""), 50),
            _form_field("delete", "Delete 1=Yes", "", 1, "numeric"),
        ],
        hidden_fields=[],
    )


def placeholder(request: HttpRequest, tranid: str = "") -> HttpResponse:
    if request.method == "POST" and pressed(request) == PF3:
        return redirect("screens:tx", tranid="CM00")
    rows = _blank()
    _put(rows, 1, 25, f"{tranid} screen")
    _put(rows, 10, 8, "This transaction is scaffolded for COBOL parity implementation.")
    _put(rows, 23, 2, "F3=Back")
    return _screen(request, "screens/generic.html", rows)
