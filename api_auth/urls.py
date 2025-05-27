from django.urls import path
from .apis import (
    DeleteApiKey,
    GenerateApiKeyView,
    ViewApiKeyView,
    RollApiKey,
    DeleteApiKey,
)


app_name = "api_keys"
urlpatterns = [
    path("generate/<str:key_type>/", GenerateApiKeyView.as_view(), name="generate-api-key"),
    path("", ViewApiKeyView.as_view(), name="view-api-key"),
    path("roll/", RollApiKey.as_view(), name="roll-api-key"),
    path("delete/", DeleteApiKey.as_view(), name="delete-api-key"),
]
