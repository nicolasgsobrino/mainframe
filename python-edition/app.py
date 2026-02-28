"""CardDemo Python Edition — Web Application

Credit card management system translated from COBOL/CICS/VSAM to Python.
Original: 30,175 lines of COBOL across 44 programs.
"""
from datetime import date, datetime
from decimal import Decimal
from flask import Flask, request, jsonify, send_file
from pathlib import Path

from services import CardDemoService, AuthenticationError, ValidationError, NotFoundError, InsufficientFundsError

app = Flask(__name__)
svc = CardDemoService()
svc.load_sample_data()

sessions = {}


@app.route("/")
def index():
    return send_file(str(Path(__file__).parent / "index.html"))


@app.route("/api/login", methods=["POST"])
def login():
    data = request.json or {}
    try:
        user = svc.sign_on(data.get("user_id", ""), data.get("password", ""))
        sid = f"SID-{user.id}"
        sessions[sid] = user
        return jsonify({"success": True, "session_id": sid,
                        "user_type": user.user_type,
                        "user_name": f"{user.first_name} {user.last_name}"})
    except (AuthenticationError, ValidationError) as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/accounts")
def list_accounts():
    return jsonify({"accounts": [
        {"id": a.id, "status": a.active_status,
         "balance": float(a.curr_bal), "credit_limit": float(a.credit_limit),
         "cash_limit": float(a.cash_credit_limit), "group": a.group_id,
         "open_date": a.open_date.isoformat() if a.open_date else "",
         "expiry_date": a.expiry_date.isoformat() if a.expiry_date else ""}
        for a in svc.accounts.values()
    ]})


@app.route("/api/account/<int:acct_id>")
def view_account(acct_id):
    try:
        a = svc.get_account(acct_id)
        c = svc.get_customer_for_account(acct_id)
        return jsonify({"success": True, "account": {
            "id": a.id, "status": a.active_status,
            "balance": float(a.curr_bal), "credit_limit": float(a.credit_limit),
            "cash_limit": float(a.cash_credit_limit), "group": a.group_id,
        }, "customer": {
            "name": f"{c.first_name} {c.last_name}" if c else "N/A",
            "city": c.city if c else "", "state": c.state_cd if c else "",
        } if c else None})
    except NotFoundError as e:
        return jsonify({"success": False, "error": str(e)}), 404


@app.route("/api/account/<int:acct_id>/update", methods=["POST"])
def update_account(acct_id):
    data = request.json or {}
    try:
        acct = svc.update_account(acct_id, **data)
        return jsonify({"success": True, "balance": float(acct.curr_bal)})
    except (ValidationError, NotFoundError) as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/cards")
def list_cards():
    acct_id = request.args.get("acct_id", type=int)
    cards, total = svc.list_cards(acct_id=acct_id)
    return jsonify({"cards": [
        {"num": c.num, "acct_id": c.acct_id, "name": c.embossed_name,
         "expiry": c.expiry_date.isoformat() if c.expiry_date else "",
         "status": c.active_status}
        for c in cards
    ], "total": total})


@app.route("/api/card/<card_num>/update", methods=["POST"])
def update_card(card_num):
    data = request.json or {}
    try:
        if "expiry_date" in data and isinstance(data["expiry_date"], str):
            pass
        card = svc.update_card(card_num, **data)
        return jsonify({"success": True, "card": {
            "num": card.num, "name": card.embossed_name,
            "status": card.active_status,
            "expiry": card.expiry_date.isoformat() if card.expiry_date else "",
        }})
    except (ValidationError, NotFoundError) as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/transactions")
def list_transactions():
    page = request.args.get("page", 1, type=int)
    txns, total = svc.list_transactions(page=page)
    return jsonify({"transactions": [
        {"id": t.id, "card": t.card_num[-4:] if t.card_num else "",
         "amt": float(t.amt), "type": t.type_cd, "desc": t.desc,
         "merchant": t.merchant_name, "city": t.merchant_city,
         "date": t.orig_ts.strftime("%Y-%m-%d") if t.orig_ts else ""}
        for t in txns
    ], "total": total, "page": page,
        "pages": (total + 9) // 10})


@app.route("/api/transaction/add", methods=["POST"])
def add_transaction():
    data = request.json or {}
    try:
        txn = svc.add_transaction(
            acct_id=int(data.get("acct_id", 0)),
            amt=Decimal(str(data.get("amt", 0))),
            type_cd=data.get("type_cd", "01"),
            desc=data.get("desc", ""),
            merchant_name=data.get("merchant_name", ""),
            merchant_city=data.get("merchant_city", ""),
            merchant_zip=data.get("merchant_zip", ""),
            source=data.get("source", "ONLINE"),
        )
        return jsonify({"success": True, "transaction_id": txn.id})
    except (ValidationError, NotFoundError) as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/bill/pay", methods=["POST"])
def pay_bill():
    data = request.json or {}
    try:
        paid, txn = svc.pay_bill(int(data.get("acct_id", 0)))
        return jsonify({"success": True, "paid": float(paid),
                        "transaction_id": txn.id})
    except (NotFoundError, InsufficientFundsError, ValidationError) as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/users")
def list_users():
    return jsonify({"users": [
        {"id": u.id, "first_name": u.first_name,
         "last_name": u.last_name, "type": u.user_type}
        for u in svc.list_users()
    ]})


@app.route("/api/user/add", methods=["POST"])
def add_user():
    data = request.json or {}
    try:
        user = svc.add_user(
            data.get("user_id", ""), data.get("first_name", ""),
            data.get("last_name", ""), data.get("password", ""),
            data.get("user_type", "U"),
        )
        return jsonify({"success": True, "user_id": user.id})
    except ValidationError as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/user/<uid>/update", methods=["POST"])
def update_user(uid):
    data = request.json or {}
    try:
        svc.update_user(uid, **data)
        return jsonify({"success": True})
    except (ValidationError, NotFoundError) as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/user/<uid>/delete", methods=["POST"])
def delete_user(uid):
    data = request.json or {}
    try:
        svc.delete_user(uid, current_user_id=data.get("current_user_id"))
        return jsonify({"success": True})
    except (ValidationError, NotFoundError) as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/interest/calculate", methods=["POST"])
def calc_interest():
    results = svc.calculate_interest()
    return jsonify({"success": True, "results": results,
                    "accounts_processed": len(results)})


@app.route("/api/statement/<int:acct_id>")
def get_statement(acct_id):
    try:
        return jsonify(svc.generate_statement(acct_id))
    except NotFoundError as e:
        return jsonify({"error": str(e)}), 404


@app.route("/api/report", methods=["POST"])
def get_report():
    data = request.json or {}
    try:
        return jsonify(svc.generate_report(
            date.fromisoformat(data.get("start_date", "2026-02-01")),
            date.fromisoformat(data.get("end_date", "2026-02-28")),
        ))
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/stats")
def stats():
    return jsonify({
        "accounts": len(svc.accounts),
        "cards": len(svc.cards),
        "transactions": len(svc.transactions),
        "users": len(svc.users),
        "cobol_programs_translated": 18,
        "cobol_lines_original": 30175,
        "bugs_fixed": 14,
    })


if __name__ == "__main__":
    print("CardDemo Python Edition")
    print(f"  Accounts: {len(svc.accounts)} | Cards: {len(svc.cards)} | Transactions: {len(svc.transactions)}")
    app.run(port=5003, debug=True)
