from __future__ import annotations

from django.contrib.auth.hashers import check_password

from models.user import SecUser


def authenticate_user(user_id: str, password: str) -> SecUser | None:
    user_id = user_id.strip().upper()
    try:
        user = SecUser.objects.get(usr_id=user_id)
    except SecUser.DoesNotExist:
        return None
    return user if check_password(password.strip(), user.usr_pwd) else None
