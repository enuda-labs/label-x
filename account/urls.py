from django.urls import path
from .apis import LoginView, RegisterView, CustomTokenRefreshView, MakeUserReviewerView, CreateProjectView, MakeUserAdminView
app_name = 'account'
urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('register/', RegisterView.as_view(), name='register'),
    path('make-reviewer/', MakeUserReviewerView().as_view(), name='create-reviewer'),
    path('make-admin/', MakeUserAdminView().as_view(), name='create-reviewer'),
    path('token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    path('projects/create/', CreateProjectView.as_view(), name='create-project'),
]
