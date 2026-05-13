from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MenuOption:
    number: int
    name: str
    program: str
    tranid: str
    min_user_type: str = "U"


MAIN_MENU = [
    MenuOption(1, "Account View", "COACTVWC", "CAVW"),
    MenuOption(2, "Account Update", "COACTUPC", "CAUP"),
    MenuOption(3, "Credit Card List", "COCRDLIC", "CCLI"),
    MenuOption(4, "Credit Card View", "COCRDSLC", "CCDL"),
    MenuOption(5, "Credit Card Update", "COCRDUPC", "CCUP"),
    MenuOption(6, "Transaction List", "COTRN00C", "CT00"),
    MenuOption(7, "Transaction View", "COTRN01C", "CT01"),
    MenuOption(8, "Transaction Add", "COTRN02C", "CT02"),
    MenuOption(9, "Transaction Reports", "CORPT00C", "CR00"),
    MenuOption(10, "Bill Payment", "COBIL00C", "CB00"),
    MenuOption(11, "Pending Authorization View", "COPAUS0C", "CPVS"),
]

ADMIN_MENU = [
    MenuOption(1, "User List (Security)", "COUSR00C", "CU00", "A"),
    MenuOption(2, "User Add (Security)", "COUSR01C", "CU01", "A"),
    MenuOption(3, "User Update (Security)", "COUSR02C", "CU02", "A"),
    MenuOption(4, "User Delete (Security)", "COUSR03C", "CU03", "A"),
    MenuOption(5, "Transaction Type List/Update (Db2)", "COTRTLIC", "CTLI", "A"),
    MenuOption(6, "Transaction Type Maintenance (Db2)", "COTRTUPC", "CTTU", "A"),
]


def menu_options(user_type: str) -> list[MenuOption]:
    return (ADMIN_MENU + MAIN_MENU) if user_type == "A" else MAIN_MENU


def resolve_option(user_type: str, option: str) -> MenuOption | None:
    try:
        number = int(option.strip())
    except ValueError:
        return None
    for item in menu_options(user_type):
        if item.number == number:
            return item
    return None
