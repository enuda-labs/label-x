from django.urls import path
from . import apis

app_name = 'reviewer'
urlpatterns = [
    path('domains/', apis.GetLabelerDomains.as_view(), name='get-labeler-domains')
]