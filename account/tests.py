from datetime import timedelta, datetime
import pytz

from django.urls import reverse
from rest_framework.test import APITransactionTestCase
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from account.models import CustomUser

class RegisterTestCase(APITransactionTestCase):
    def setUp(self):
        self.register_path = reverse("account:register")
        self.login_path = reverse('account:login')
        CustomUser.objects.create_user(username='dama', email="test@gmail.com")

    def test_register_success(self):
        response = self.client.post(
            self.register_path, data={'username': 'dama1', "email": "test1@gmail.com", 'password': '123456789ASas@'}
        )
        for field in {"status", "user_data"}:
            self.assertTrue(field in response.data)
    

    def test_register_integrity_failure(self):
        response = self.client.post(
            self.register_path, data={'username': 'dama', "email": "test@gmail.com"}
        )
        self.assertEqual(
            response.data["status"], "error"
        )
        self.assertEqual(
            response.data["error"], "Username already exists"
        )
        
    def test_register_failure_for_password(self):
        response = self.client.post(
            self.register_path, data={'username': 'test', "email": "test3@gmail.com", 'password': '1234GHJ@'}
        )

        self.assertEqual(
            response.data["status"], "error"
        )
        self.assertEqual(
            response.data["error"], "Password must contain at least one lowercase letter"
        )

    def tearDown(self):
        CustomUser.objects.all().delete()
        

class LoginTestCase(APITransactionTestCase):
    def setUp(self):
        self.login_path = reverse('account:login')
        # Create test user for login tests
        self.test_user = CustomUser.objects.create_user(
            username='testlogin', 
            email="testlogin@gmail.com",
            password='123456789ASas@'
        )

    def test_login_success(self):
        response = self.client.post(
            self.login_path, 
            {
                'username': 'testlogin',
                'password': '123456789ASas@'
            }, 
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # self.assertEqual(response.data['status'], 'success')
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertIn('user_data', response.data)
        self.assertEqual(
            response.data['user_data']['username'], 
            self.test_user.username
        )

    def test_login_invalid_credentials(self):
        response = self.client.post(
            self.login_path, 
            {
                'username': 'wronguser',
                'password': 'wrongpass'
            }, 
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data['status'], 'error')
        self.assertEqual(response.data['error'], 'Invalid Credentials')

    def test_login_inactive_user(self):
        # Set user to inactive
        self.test_user.is_active = False
        self.test_user.save()

        response = self.client.post(
            self.login_path, 
            {
                'username': 'testlogin',
                'password': '123456789ASas@'
            }, 
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data['status'], 'error')
        self.assertEqual(response.data['error'], 'Invalid Credentials')
        
class RefreshTokenTestCase(APITransactionTestCase):
    def setUp(self):
        self.refresh_path = reverse("account:token_refresh")  # Ensure this matches your URLs
        self.user = CustomUser.objects.create_user(
            username="testuser",
            email="testuser@gmail.com",
            password="TestPassword123!"
        )
        # Generate tokens
        refresh = RefreshToken.for_user(self.user)
        self.refresh_token = str(refresh)
        self.access_token = str(refresh.access_token)

    def test_refresh_token_success(self):
        """
        Ensure a valid refresh token returns a new access token.
        """
        response = self.client.post(
            self.refresh_path, 
            {"refresh": self.refresh_token}, 
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertTrue(len(response.data["access"]) > 0)

    def test_refresh_token_failure(self):
        """
        Ensure an invalid refresh token returns a 401 error.
        """
        response = self.client.post(
            self.refresh_path, 
            {"refresh": "invalid_refresh_token"}, 
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["detail"], "Your session has expired. Please log in again.")

    def test_refresh_token_expired(self):
        """
        Ensure an expired refresh token is rejected.
        """
        expired_refresh = RefreshToken.for_user(self.user)
        expired_refresh.set_exp(from_time=datetime.now(pytz.UTC) - timedelta(days=3))
        expired_refresh_token = str(expired_refresh)

        response = self.client.post(
            self.refresh_path, 
            {"refresh": expired_refresh_token}, 
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["status"], "error")

    def tearDown(self):
        CustomUser.objects.all().delete()

class ChangePasswordTestCase(APITransactionTestCase):
    def setUp(self):
        # Create test user
        self.user = CustomUser.objects.create_user(
            username='testuser', 
            email='test@example.com', 
            password='Testp@ssword123'
        )
        
        # Get token for authentication
        refresh = RefreshToken.for_user(self.user)
        self.token = str(refresh.access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        
        # API endpoint
        self.change_password_url = reverse('account:change-password')
        
        # Test data
        self.valid_password_data = {
            "current_password": "Testp@ssword123",
            "new_password": "Newp@ssword123",
            "confirm_password": "Newp@ssword123"
        }
        
        self.invalid_current_password_data = {
            "current_password": "WrongPassword123",
            "new_password": "Newp@ssword123",
            "confirm_password": "Newp@ssword123"
        }
        
        self.mismatched_passwords_data = {
            "current_password": "Testp@ssword123",
            "new_password": "Newp@ssword123",
            "confirm_password": "DifferentPassword123"
        }
        
        self.short_password_data = {
            "current_password": "Testp@ssword123",
            "new_password": "short",
            "confirm_password": "short"
        }

    def test_change_password_success(self):
        """Test successful password change"""
        response = self.client.post(
            self.change_password_url,
            self.valid_password_data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['message'], 'Password changed successfully')
        
        # Refresh user from database
        self.user.refresh_from_db()
        
        # Verify new password works
        self.assertTrue(self.user.check_password("Newp@ssword123"))
        
        # Verify old password doesn't work
        self.assertFalse(self.user.check_password("Testp@ssword123"))

    def test_change_password_wrong_current_password(self):
        """Test password change with incorrect current password"""
        response = self.client.post(
            self.change_password_url,
            self.invalid_current_password_data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['status'], 'error')
        self.assertEqual(response.data['error'], 'Current password is incorrect')
        
        # Verify password hasn't changed
        self.assertTrue(self.user.check_password("Testp@ssword123"))

    def test_change_password_mismatched_passwords(self):
        """Test password change with mismatched new passwords"""
        response = self.client.post(
            self.change_password_url,
            self.mismatched_passwords_data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['status'], 'error')
        self.assertIn('confirm_password', response.data['error'])
        
        # Verify password hasn't changed
        self.assertTrue(self.user.check_password("Testp@ssword123"))

    def test_change_password_short_password(self):
        """Test password change with password shorter than minimum length"""
        response = self.client.post(
            self.change_password_url,
            self.short_password_data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['status'], 'error')
        
        # Verify password hasn't changed
        self.assertTrue(self.user.check_password("Testp@ssword123"))

    def test_change_password_without_auth(self):
        """Test password change without authentication"""
        self.client.credentials()  # Remove auth credentials
        response = self.client.post(
            self.change_password_url,
            self.valid_password_data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Verify password hasn't changed
        self.assertTrue(self.user.check_password("Testp@ssword123"))

    def test_change_password_missing_fields(self):
        """Test password change with missing required fields"""
        # Test missing current password
        data = self.valid_password_data.copy()
        del data['current_password']
        response = self.client.post(
            self.change_password_url,
            data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Test missing new password
        data = self.valid_password_data.copy()
        del data['new_password']
        response = self.client.post(
            self.change_password_url,
            data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Test missing confirm password
        data = self.valid_password_data.copy()
        del data['confirm_password']
        response = self.client.post(
            self.change_password_url,
            data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Verify password hasn't changed in any case
        self.assertTrue(self.user.check_password("Testp@ssword123"))

    def tearDown(self):
        CustomUser.objects.all().delete()

class UpdateUsernameTestCase(APITransactionTestCase):
    def setUp(self):
        # Create test user
        self.user = CustomUser.objects.create_user(
            username='testuser', 
            email='test@example.com', 
            password='Testp@ssword123'
        )
        
        # Create another user to test username uniqueness
        self.other_user = CustomUser.objects.create_user(
            username='existinguser',
            email='other@example.com',
            password='Testp@ssword123'
        )
        
        # Get token for authentication
        refresh = RefreshToken.for_user(self.user)
        self.token = str(refresh.access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        
        # API endpoint
        self.update_username_url = reverse('account:update-username')
        
        # Test data
        self.valid_username_data = {
            "username": "newusername"
        }
        
        self.existing_username_data = {
            "username": "existinguser"
        }
        
        self.empty_username_data = {
            "username": ""
        }

    def test_update_username_success(self):
        """Test successful username update"""
        response = self.client.post(
            self.update_username_url,
            self.valid_username_data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['message'], 'Username updated successfully')
        
        # Refresh user from database
        self.user.refresh_from_db()
        
        # Verify username has changed
        self.assertEqual(self.user.username, "newusername")

    def test_update_username_already_exists(self):
        """Test username update with existing username"""
        response = self.client.post(
            self.update_username_url,
            self.existing_username_data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['status'], 'error')
        self.assertEqual(response.data['error'], 'This username is already taken')
        
        # Verify username hasn't changed
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "testuser")

    def test_update_username_empty(self):
        """Test username update with empty username"""
        response = self.client.post(
            self.update_username_url,
            self.empty_username_data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['status'], 'error')
        
        # Verify username hasn't changed
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "testuser")

    def test_update_username_without_auth(self):
        """Test username update without authentication"""
        self.client.credentials()  # Remove auth credentials
        response = self.client.post(
            self.update_username_url,
            self.valid_username_data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Verify username hasn't changed
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "testuser")

    def test_update_username_missing_field(self):
        """Test username update with missing username field"""
        response = self.client.post(
            self.update_username_url,
            {},
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['status'], 'error')
        
        # Verify username hasn't changed
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "testuser")

    def tearDown(self):
        CustomUser.objects.all().delete()
