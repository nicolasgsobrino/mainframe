from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

POSITIVE_ZONED = {"{": "0", "A": "1", "B": "2", "C": "3", "D": "4", "E": "5", "F": "6", "G": "7", "H": "8", "I": "9"}
NEGATIVE_ZONED = {"}": "0", "J": "1", "K": "2", "L": "3", "M": "4", "N": "5", "O": "6", "P": "7", "Q": "8", "R": "9"}


def parse_display_int(raw: str) -> int:
    value = raw.strip()
    return int(value or "0")


def parse_zoned_decimal(raw: str, scale: int = 2) -> Decimal:
    value = raw.strip()
    if not value:
        return Decimal("0").quantize(Decimal(10) ** -scale)
    last = value[-1]
    sign = 1
    if last in POSITIVE_ZONED:
        digits = value[:-1] + POSITIVE_ZONED[last]
    elif last in NEGATIVE_ZONED:
        sign = -1
        digits = value[:-1] + NEGATIVE_ZONED[last]
    else:
        digits = value
    amount = Decimal(int(digits) * sign) / (Decimal(10) ** scale)
    return amount.quantize(Decimal(10) ** -scale)


def money(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
