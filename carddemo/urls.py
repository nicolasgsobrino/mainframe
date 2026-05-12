from __future__ import annotations

from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(url="/tx/CC00", permanent=False)),
    path("tx/", include("screens.urls")),
]
