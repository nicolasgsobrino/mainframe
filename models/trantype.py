from __future__ import annotations

from django.db import models


class TransactionType(models.Model):
    tr_type = models.CharField(max_length=2, primary_key=True)
    tr_description = models.CharField(max_length=50)

    class Meta:
        db_table = "transaction_type"
