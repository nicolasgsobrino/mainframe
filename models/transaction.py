from __future__ import annotations

from django.db import models


class TransactionBase(models.Model):
    type_cd = models.CharField(max_length=2)
    cat_cd = models.CharField(max_length=4)
    source = models.CharField(max_length=10)
    desc = models.CharField(max_length=100)
    amt = models.DecimalField(max_digits=11, decimal_places=2)
    merchant_id = models.DecimalField(max_digits=9, decimal_places=0)
    merchant_name = models.CharField(max_length=50)
    merchant_city = models.CharField(max_length=50)
    merchant_zip = models.CharField(max_length=10)
    card_num = models.CharField(max_length=16, db_index=True)
    orig_ts = models.CharField(max_length=26)
    proc_ts = models.CharField(max_length=26)

    class Meta:
        abstract = True


class Transaction(TransactionBase):
    tran_id = models.CharField(max_length=16, primary_key=True)

    class Meta:
        db_table = "transaction"


class DailyTransaction(TransactionBase):
    dalytran_id = models.CharField(max_length=16, primary_key=True)

    class Meta:
        db_table = "daily_transaction"


class DailyReject(models.Model):
    dalytran_id = models.CharField(max_length=16, unique=True)
    reason = models.CharField(max_length=80)
    card_num = models.CharField(max_length=16)
    raw_payload = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "daily_rejects"
