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
    path('projects/list/', apis.ListProjectsView.as_view(), name='list-project'),
    path('users/not-in-project/<int:project_id>/', apis.UsersNotInProjectView.as_view(), name='users-not-in-project'),
    path('users/in-project/<int:project_id>/', apis.UsersInProjectView.as_view(), name='users-in-project'),
    path("projects/create/", apis.CreateProjectView.as_view(), name="create-project"),
    path("organization/project/", apis.CreateUserProject.as_view(), name='create-user-project'),
    path("organization/project/list/", apis.ListUserProjectView.as_view(), name='list-user-project'),  
    path('2fa/setup/', apis.Setup2faView.as_view(), name='setup-2fa'),
    path("2fa/disable/", apis.Disable2FAView.as_view(), name='disable-2fa'),
    path('logout/', apis.LogoutView.as_view(), name='logout-user'),
    path('change-password/', apis.ChangePasswordView.as_view(), name='change-password'),
    path('update-username/', apis.UpdateNameView.as_view(), name='update-username')
]