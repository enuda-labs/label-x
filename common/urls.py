#only put app wide system configuration or functionality here, no urls for individual apps should be put here

from django.urls import path
from . import apis

urlpatterns = [
    path('cost-settings/', apis.GetSystemSettingsView.as_view(), name='get-system-settings')
]