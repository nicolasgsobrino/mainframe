from __future__ import annotations

from django.urls import path

from . import views

app_name = "screens"

urlpatterns = [
    path("<str:tranid>", views.tx, name="tx"),
]
