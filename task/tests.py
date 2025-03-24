from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth import get_user_model

from .models import Task

User = get_user_model()

class TaskSubmissionTestCase(APITestCase):
    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(
            username='testuser', 
            email='test@example.com', 
            password='Testp@ssword123'
        )
        
        # Get token for authentication
        self.token = str(AccessToken.for_user(user=self.user))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        
        # API endpoint
        self.task_create_url = reverse('task:task_create')
        
        # Test data for different content types
        self.text_task_data = {
            "task_type": "TEXT",
            "priority": "NORMAL",
            "data": {
                "content": "This is a sample text to analyze for inappropriate content.",
                "language": "en",
                "metadata": {
                    "source": "user_input",
                    "context": "social_media_post"
                }
            }
        }
        
        self.image_task_data = {
            "task_type": "IMAGE",
            "priority": "URGENT",
            "data": {
                "image_url": "https://example.com/sample-image.jpg",
                "file_type": "jpg",
                "dimensions": {
                    "width": 1920,
                    "height": 1080
                },
                "metadata": {
                    "source": "user_upload",
                    "context": "profile_picture"
                }
            }
        }
        
        self.video_task_data = {
            "task_type": "VIDEO",
            "priority": "NORMAL",
            "data": {
                "video_url": "https://example.com/sample-video.mp4",
                "duration": "00:02:30",
                "file_type": "mp4",
                "resolution": "1080p",
                "metadata": {
                    "source": "user_upload",
                    "context": "social_media_post",
                    "frames_per_second": 30
                }
            }
        }
        
        self.multimodal_task_data = {
            "task_type": "MULTIMODAL",
            "priority": "URGENT",
            "data": {
                "text_content": "Check this product advertisement",
                "image_url": "https://example.com/product-image.jpg",
                "components": {
                    "text": {
                        "language": "en",
                        "type": "product_description"
                    },
                    "image": {
                        "file_type": "jpg",
                        "dimensions": {
                            "width": 800,
                            "height": 600
                        }
                    }
                },
                "metadata": {
                    "source": "marketing_team",
                    "context": "advertisement",
                    "campaign_id": "CAMP123"
                }
            }
        }

    def test_submit_text_task(self):
        """Test submitting a text task"""
        response = self.client.post(
            self.task_create_url,
            self.text_task_data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('task_id', response.data['data'])
        self.assertIn('celery_task_id', response.data['data'])
        
        # Verify task in database
        task = Task.objects.get(id=response.data['data']['task_id'])
        self.assertEqual(task.task_type, 'TEXT')
        self.assertEqual(task.status, 'PENDING')
        self.assertEqual(task.user, self.user)

    def test_submit_image_task(self):
        """Test submitting an image task"""
        response = self.client.post(
            self.task_create_url,
            self.image_task_data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('task_id', response.data['data'])
        
        task = Task.objects.get(id=response.data['data']['task_id'])
        self.assertEqual(task.task_type, 'IMAGE')
        self.assertEqual(task.priority, 'URGENT')

    def test_submit_video_task(self):
        """Test submitting a video task"""
        response = self.client.post(
            self.task_create_url,
            self.video_task_data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('task_id', response.data['data'])
        
        task = Task.objects.get(id=response.data['data']['task_id'])
        self.assertEqual(task.task_type, 'VIDEO')
        self.assertEqual(task.data['duration'], '00:02:30')

    def test_submit_multimodal_task(self):
        """Test submitting a multimodal task"""
        response = self.client.post(
            self.task_create_url,
            self.multimodal_task_data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('task_id', response.data['data'])
        
        task = Task.objects.get(id=response.data['data']['task_id'])
        self.assertEqual(task.task_type, 'MULTIMODAL')
        self.assertTrue('text_content' in task.data)
        self.assertTrue('image_url' in task.data)

    def test_submit_task_without_auth(self):
        """Test submitting without authentication"""
        self.client.credentials()  # Remove auth credentials
        response = self.client.post(
            self.task_create_url,
            self.text_task_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_submit_invalid_task_type(self):
        """Test submitting with invalid task type"""
        invalid_data = self.text_task_data.copy()
        invalid_data['task_type'] = 'INVALID_TYPE'
        
        response = self.client.post(
            self.task_create_url,
            invalid_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def tearDown(self):
        Task.objects.all().delete()
        User.objects.all().delete()

class TaskStatusTestCase(APITestCase):
    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(
            username='testuser', 
            email='test@example.com', 
            password='Testp@ssword123'
        )
        
        # Create another user for testing isolation
        self.other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='Otherp@ssword123'
        )
        
        # Set up authentication
        self.token = str(AccessToken.for_user(user=self.user))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        
        # Create a test task
        self.task = Task.objects.create(
            user=self.user,
            task_type='TEXT',
            priority='NORMAL',
            data={
                "content": "Test content",
                "metadata": {"source": "test"}
            }
        )
        
        # Create a task for other user
        self.other_task = Task.objects.create(
            user=self.other_user,
            task_type='TEXT',
            priority='NORMAL',
            data={"content": "Other content"}
        )
        
        # API endpoints
        self.status_url = reverse('task:task_status', kwargs={'identifier': self.task.id})
        self.status_url_serial = reverse('task:task_status', kwargs={'identifier': self.task.serial_no})

    def test_get_task_status_by_id(self):
        """Test getting task status using task ID"""
        response = self.client.get(self.status_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['data']['task_id'], self.task.id)
        self.assertEqual(response.data['data']['submitted_by'], self.user.username)

    def test_get_task_status_by_serial_no(self):
        """Test getting task status using serial number"""
        response = self.client.get(self.status_url_serial)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['serial_no'], self.task.serial_no)

    def test_get_nonexistent_task(self):
        """Test getting status of non-existent task"""
        url = reverse('task:task_status', kwargs={'identifier': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data['status'], 'error')

    def test_get_other_user_task(self):
        """Test attempting to get another user's task"""
        url = reverse('task:task_status', kwargs={'identifier': self.other_task.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_task_without_auth(self):
        """Test getting task status without authentication"""
        self.client.credentials()
        response = self.client.get(self.status_url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class UserTaskListTestCase(APITestCase):
    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(
            username='testuser', 
            email='test@example.com', 
            password='Testp@ssword123'
        )
        
        # Set up authentication
        self.token = str(AccessToken.for_user(user=self.user))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        
        # Create multiple tasks for the user
        self.tasks = []
        task_types = ['TEXT', 'IMAGE', 'VIDEO']
        for i, task_type in enumerate(task_types):
            task = Task.objects.create(
                user=self.user,
                task_type=task_type,
                priority='NORMAL',
                data={"content": f"Test content {i}"}
            )
            self.tasks.append(task)
        
        # Create task for another user
        self.other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='Otherp@ssword123'
        )
        self.other_task = Task.objects.create(
            user=self.other_user,
            task_type='TEXT',
            data={"content": "Other content"}
        )
        
        # API endpoint
        self.task_list_url = reverse('task:user_tasks')

    def test_get_user_tasks(self):
        """Test getting list of user's tasks"""
        response = self.client.get(self.task_list_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), len(self.tasks))
        
        # Verify tasks belong to user
        task_ids = [task['id'] for task in response.data]
        for task in self.tasks:
            self.assertIn(task.id, task_ids)
        
        # Verify other user's task is not included
        self.assertNotIn(self.other_task.id, task_ids)

    def test_tasks_ordered_by_created_at(self):
        """Test tasks are ordered by creation date (newest first)"""
        response = self.client.get(self.task_list_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        created_dates = [task['created_at'] for task in response.data]
        self.assertEqual(created_dates, sorted(created_dates, reverse=True))

    def test_get_tasks_without_auth(self):
        """Test getting tasks without authentication"""
        self.client.credentials()
        response = self.client.get(self.task_list_url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def tearDown(self):
        Task.objects.all().delete()
        User.objects.all().delete()

