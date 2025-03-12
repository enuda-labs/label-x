from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework_simplejwt.tokens import AccessToken
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()

class TaskCreateViewTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', email='testemail@gmail.com', password='testpassword')
        
        self.token = str(AccessToken.for_user(user=self.user))
        self.create_task_url = reverse('task:task_create')
        self.task_data = {
            'task_type': 'TEXT',
            'content': 'Just testing',
            'priority': 'URGENT'
        }
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        
        
    def test_create_task_success(self):
        response = self.client.post(self.create_task_url, self.task_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('task_id', response.data)
        self.assertEqual(response.data['message'], 'Task submitted successfully')

    def test_create_task_invalid_data(self):
        invalid_data = self.task_data.copy()
        invalid_data['priority'] = 'INVALID_PRIORITY'
        
        response = self.client.post(self.create_task_url, invalid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('priority', response.data)

