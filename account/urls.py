from django.urls import path
from .apis import LoginView, RegisterView, CustomTokenRefreshView, MakeUserReviewerView, CreateProjectView, MakeUserAdminView, ProjectListView, UserDetailView, UsersNotInProjectView
app_name = 'account'
urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('register/', RegisterView.as_view(), name='register'),
    path('make-reviewer/', MakeUserReviewerView().as_view(), name='create-reviewer'),
    path('user/detail/', UserDetailView.as_view(), name='user-detail'),
    path('make-admin/', MakeUserAdminView().as_view(), name='create-reviewer'),
    path('token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    path('projects/create/', CreateProjectView.as_view(), name='create-project'),
    path('projects/list/', ProjectListView.as_view(), name='list -project'),
    path('users/not-in-project/<int:project_id>/', UsersNotInProjectView.as_view(), name='users-not-in-project'),
]
