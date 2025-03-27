from django.urls import path
from .apis import LoginView, RegisterView, CustomTokenRefreshView
app_name = 'account'
urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('register/', RegisterView.as_view(), name='register'),
    path('token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
]
