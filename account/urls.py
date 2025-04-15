from django.urls import path
from . import apis
app_name = 'account'
urlpatterns = [
    path('login/', apis.LoginView.as_view(), name='login'),
    path('register/', apis.RegisterView.as_view(), name='register'),
    path('make-reviewer/', apis.MakeUserReviewerView().as_view(), name='create-reviewer'),
    path('remove-reviewer/', apis.RemoveUserReviewerView().as_view(), name='create-reviewer'),
    path('user/detail/', apis.UserDetailView.as_view(), name='user-detail'),
    path('make-admin/', apis.MakeUserAdminView().as_view(), name='create-reviewer'),
    path('token/refresh/', apis.CustomTokenRefreshView.as_view(), name='token_refresh'),
    path('projects/create/', apis.CreateProjectView.as_view(), name='create-project'),
    path('projects/list/', apis.ProjectListView.as_view(), name='list -project'),
    path('users/not-in-project/<int:project_id>/', apis.UsersNotInProjectView.as_view(), name='users-not-in-project'),
    path('users/in-project/<int:project_id>/', apis.UsersInProjectView.as_view(), name='users-in-project'),
]
