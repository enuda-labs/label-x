from django.urls import reverse
from rest_framework.test import APITransactionTestCase

from account.models import CustomUser

class RegisterTestCase(APITransactionTestCase):
    def setUp(self):
        self.register_path = reverse("account:register")
        CustomUser.objects.create_user(username='dama', email="test@gmail.com")

    def test_register_success(self):
        response = self.client.post(
            self.register_path, data={'username': 'dama1', "email": "test1@gmail.com", 'password': '123456'}
        )
        for field in {"id", "email"}:
            self.assertTrue(field in response.data)
    

    def test_register_integrity_failure(self):
        response = self.client.post(
            self.register_path, data={'username': 'dama', "email": "test@gmail.com"}
        )
        self.assertEqual(
            response.data["email"][0], "custom user with this email already exists."
        )
        
    def test_register_failure_for_password(self):
        response = self.client.post(
            self.register_path, data={'username': 'test', "email": "test3@gmail.com", 'password': '1234'}
        )
        print(response.data['password'])
        self.assertEqual(
            response.data["password"][0], "'Ensure this field has at least 6 characters."
        )

    def tearDown(self):
        CustomUser.objects.all().delete()
