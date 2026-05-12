from __future__ import annotations

from django.apps import AppConfig


class ModelsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "models"

    def import_models(self) -> None:
        super().import_models()
        from . import account, auth, card, customer, discgrp, trancat, transaction, trantype, user

        self._model_modules = [
            account,
            auth,
            card,
            customer,
            discgrp,
            trancat,
            transaction,
            trantype,
            user,
        ]
