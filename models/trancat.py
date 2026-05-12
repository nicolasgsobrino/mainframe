from __future__ import annotations

from django.db import models


class TransactionCategory(models.Model):
    tr_type = models.CharField(max_length=2)
    tr_cat_cd = models.CharField(max_length=4)
    tr_cat_type_desc = models.CharField(max_length=50)

    class Meta:
        db_table = "transaction_category"
        constraints = [
            models.UniqueConstraint(fields=["tr_type", "tr_cat_cd"], name="transaction_category_pk")
        ]
        indexes = [models.Index(fields=["tr_type", "tr_cat_cd"])]


class TransactionCategoryBalance(models.Model):
    acct_id = models.DecimalField(max_digits=11, decimal_places=0)
    type_cd = models.CharField(max_length=2)
    cat_cd = models.CharField(max_length=4)
    tran_cat_bal = models.DecimalField(max_digits=11, decimal_places=2)

    class Meta:
        db_table = "tran_cat_balance"
        constraints = [
            models.UniqueConstraint(
                fields=["acct_id", "type_cd", "cat_cd"], name="tran_cat_balance_pk"
            )
        ]
        indexes = [models.Index(fields=["acct_id", "type_cd", "cat_cd"])]
