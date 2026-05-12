from __future__ import annotations

ENTER = "ENTER"
PF3 = "PF3"
PF4 = "PF4"
PF7 = "PF7"
PF8 = "PF8"


def pressed(request) -> str:
    return request.POST.get("pfkey", ENTER)
