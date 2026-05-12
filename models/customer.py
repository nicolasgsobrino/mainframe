from __future__ import annotations

from django.db import models


class Customer(models.Model):
    cust_id = models.DecimalField(max_digits=9, decimal_places=0, primary_key=True)
    cust_first_name = models.CharField(max_length=25)
    cust_middle_name = models.CharField(max_length=25)
    cust_last_name = models.CharField(max_length=25)
    cust_addr_line_1 = models.CharField(max_length=50)
    cust_addr_line_2 = models.CharField(max_length=50)
    cust_addr_line_3 = models.CharField(max_length=50)
    cust_addr_state_cd = models.CharField(max_length=2)
    cust_addr_country_cd = models.CharField(max_length=3)
    cust_addr_zip = models.CharField(max_length=10)
    cust_phone_num_1 = models.CharField(max_length=15)
    cust_phone_num_2 = models.CharField(max_length=15)
    cust_ssn = models.DecimalField(max_digits=9, decimal_places=0)
    cust_govt_issued_id = models.CharField(max_length=20)
    cust_dob_yyyy_mm_dd = models.CharField(max_length=10)
    cust_eft_account_id = models.CharField(max_length=10)
    cust_pri_card_holder_ind = models.CharField(max_length=1)
    cust_fico_credit_score = models.DecimalField(max_digits=3, decimal_places=0)

    class Meta:
        db_table = "customer"
