from __future__ import annotations

from django.db import models


class AccountStatus(models.TextChoices):
    ACTIVE = "Y", "Active"
    INACTIVE = "N", "Inactive"


class Account(models.Model):
    acct_id = models.DecimalField(max_digits=11, decimal_places=0, primary_key=True)
    acct_active_status = models.CharField(max_length=1)
    acct_curr_bal = models.DecimalField(max_digits=12, decimal_places=2)
    acct_credit_limit = models.DecimalField(max_digits=12, decimal_places=2)
    acct_cash_credit_limit = models.DecimalField(max_digits=12, decimal_places=2)
    acct_open_date = models.CharField(max_length=10)
    acct_expiraion_date = models.CharField(max_length=10)
    acct_reissue_date = models.CharField(max_length=10)
    acct_curr_cyc_credit = models.DecimalField(max_digits=12, decimal_places=2)
    acct_curr_cyc_debit = models.DecimalField(max_digits=12, decimal_places=2)
    acct_addr_zip = models.CharField(max_length=10)
    acct_group_id = models.CharField(max_length=10)

    class Meta:
        db_table = "account"

    def __str__(self) -> str:
        return str(self.acct_id)
