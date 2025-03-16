from django.urls import reverse
from rest_framework.test import APITransactionTestCase
from rest_framework import status

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
