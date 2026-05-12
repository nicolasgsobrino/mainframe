from __future__ import annotations

from django.db import models


class PendingAuthSummary(models.Model):
    card_num = models.CharField(max_length=16, primary_key=True)
    acct_id = models.DecimalField(max_digits=11, decimal_places=0)
    cust_id = models.DecimalField(max_digits=9, decimal_places=0)
    auth_status = models.CharField(max_length=1, default="P")
    account_status = models.CharField(max_length=10, blank=True)
    credit_limit = models.DecimalField(max_digits=11, decimal_places=2)
    cash_limit = models.DecimalField(max_digits=11, decimal_places=2)
    credit_balance = models.DecimalField(max_digits=11, decimal_places=2)
    cash_balance = models.DecimalField(max_digits=11, decimal_places=2)
    approved_auth_cnt = models.IntegerField(default=0)
    declined_auth_cnt = models.IntegerField(default=0)
    approved_auth_amt = models.DecimalField(max_digits=11, decimal_places=2, default=0)
    declined_auth_amt = models.DecimalField(max_digits=11, decimal_places=2, default=0)

    class Meta:
        db_table = "pending_auth_summary"


class PendingAuthDetail(models.Model):
    auth_date = models.CharField(max_length=6)
    auth_time = models.CharField(max_length=6)
    auth_orig_date = models.CharField(max_length=6)
    auth_orig_time = models.CharField(max_length=6)
    card_num = models.CharField(max_length=16, db_index=True)
    auth_type = models.CharField(max_length=4)
    card_expiry_date = models.CharField(max_length=4)
    message_type = models.CharField(max_length=6)
    message_source = models.CharField(max_length=6)
    auth_id_code = models.CharField(max_length=6)
    auth_resp_code = models.CharField(max_length=2)
    auth_resp_reason = models.CharField(max_length=4)
    processing_code = models.CharField(max_length=6)
    transaction_amt = models.DecimalField(max_digits=12, decimal_places=2)
    approved_amt = models.DecimalField(max_digits=12, decimal_places=2)
    merchant_catagory_code = models.CharField(max_length=4)
    acqr_country_code = models.CharField(max_length=3)
    pos_entry_mode = models.IntegerField()
    merchant_id = models.CharField(max_length=15)
    merchant_name = models.CharField(max_length=22)
    merchant_city = models.CharField(max_length=13)
    merchant_state = models.CharField(max_length=2)
    merchant_zip = models.CharField(max_length=9)
    transaction_id = models.CharField(max_length=15)
    match_status = models.CharField(max_length=1, default="P")
    auth_fraud = models.CharField(max_length=1, blank=True)
    fraud_rpt_date = models.CharField(max_length=8, blank=True)

    class Meta:
        db_table = "pending_auth_detail"
        constraints = [
            models.UniqueConstraint(fields=["auth_date", "auth_time"], name="pending_auth_detail_pk")
        ]
        indexes = [models.Index(fields=["auth_date", "auth_time"])]


class AuthFraud(models.Model):
    card_num = models.CharField(max_length=16)
    auth_ts = models.DateTimeField()
    auth_type = models.CharField(max_length=4, blank=True)
    card_expiry_date = models.CharField(max_length=4, blank=True)
    message_type = models.CharField(max_length=6, blank=True)
    message_source = models.CharField(max_length=6, blank=True)
    auth_id_code = models.CharField(max_length=6, blank=True)
    auth_resp_code = models.CharField(max_length=2, blank=True)
    auth_resp_reason = models.CharField(max_length=4, blank=True)
    processing_code = models.CharField(max_length=6, blank=True)
    transaction_amt = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    approved_amt = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    merchant_catagory_code = models.CharField(max_length=4, blank=True)
    acqr_country_code = models.CharField(max_length=3, blank=True)
    pos_entry_mode = models.IntegerField(default=0)
    merchant_id = models.CharField(max_length=15, blank=True)
    merchant_name = models.CharField(max_length=22, blank=True)
    merchant_city = models.CharField(max_length=13, blank=True)
    merchant_state = models.CharField(max_length=2, blank=True)
    merchant_zip = models.CharField(max_length=9, blank=True)
    transaction_id = models.CharField(max_length=15, blank=True)
    match_status = models.CharField(max_length=1, blank=True)
    auth_fraud = models.CharField(max_length=1, blank=True)
    fraud_rpt_date = models.DateField(null=True, blank=True)
    acct_id = models.DecimalField(max_digits=11, decimal_places=0, null=True, blank=True)
    cust_id = models.DecimalField(max_digits=9, decimal_places=0, null=True, blank=True)

    class Meta:
        db_table = "auth_fraud"
        constraints = [models.UniqueConstraint(fields=["card_num", "auth_ts"], name="auth_fraud_pk")]
        indexes = [models.Index(fields=["card_num", "auth_ts"])]
