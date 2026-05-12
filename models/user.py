from __future__ import annotations

from django.db import models


class SecUser(models.Model):
    usr_id = models.CharField(max_length=8, primary_key=True)
    usr_fname = models.CharField(max_length=20)
    usr_lname = models.CharField(max_length=20)
    usr_pwd = models.CharField(max_length=128)
    usr_type = models.CharField(max_length=1)

    class Meta:
        db_table = "sec_user"
