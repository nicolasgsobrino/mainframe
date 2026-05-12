from __future__ import annotations

from django.db import models


class Card(models.Model):
    card_num = models.CharField(max_length=16, primary_key=True)
    card_acct_id = models.DecimalField(max_digits=11, decimal_places=0, db_index=True)
    card_cvv_cd = models.DecimalField(max_digits=3, decimal_places=0)
    card_embossed_name = models.CharField(max_length=50)
    card_expiraion_date = models.CharField(max_length=10)
    card_active_status = models.CharField(max_length=1)

    class Meta:
        db_table = "card"


class CardXref(models.Model):
    xref_card_num = models.CharField(max_length=16, primary_key=True)
    xref_cust_id = models.DecimalField(max_digits=9, decimal_places=0, db_index=True)
    xref_acct_id = models.DecimalField(max_digits=11, decimal_places=0, db_index=True)

    class Meta:
        db_table = "card_xref"
