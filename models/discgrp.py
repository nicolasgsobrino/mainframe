from __future__ import annotations

from django.db import models


class DisclosureGroup(models.Model):
    acct_group_id = models.CharField(max_length=10)
    tran_type_cd = models.CharField(max_length=2)
    tran_cat_cd = models.CharField(max_length=4)
    int_rate = models.DecimalField(max_digits=6, decimal_places=2)

    class Meta:
        db_table = "disclosure_group"
        constraints = [
            models.UniqueConstraint(
                fields=["acct_group_id", "tran_type_cd", "tran_cat_cd"],
                name="disclosure_group_pk",
            )
        ]
        indexes = [models.Index(fields=["acct_group_id", "tran_type_cd", "tran_cat_cd"])]
