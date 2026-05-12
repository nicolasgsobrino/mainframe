from __future__ import annotations

from typing import Any

COMMAREA_KEY = "carddemo_commarea"

DEFAULT_COMMAREA = {
    "from_tranid": "",
    "from_program": "",
    "to_tranid": "",
    "to_program": "",
    "user_id": "",
    "user_type": "",
    "cust_id": "",
    "acct_id": "",
    "card_num": "",
    "last_map": "",
    "last_mapset": "",
}


def get_commarea(session: dict[str, Any]) -> dict[str, Any]:
    commarea = dict(DEFAULT_COMMAREA)
    commarea.update(session.get(COMMAREA_KEY, {}))
    return commarea


def save_commarea(session: dict[str, Any], **updates: Any) -> dict[str, Any]:
    commarea = get_commarea(session)
    commarea.update(updates)
    session[COMMAREA_KEY] = commarea
    session.modified = True
    return commarea


def clear_commarea(session: dict[str, Any]) -> None:
    session.pop(COMMAREA_KEY, None)
    session.modified = True
