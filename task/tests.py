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
            password='testpassword123'
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
        self.assertIn('task_id', response.data)
        self.assertIn('celery_task_id', response.data)
        
        # Verify task in database
        task = Task.objects.get(id=response.data['task_id'])
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
        self.assertIn('task_id', response.data)
        
        task = Task.objects.get(id=response.data['task_id'])
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
        self.assertIn('task_id', response.data)
        
        task = Task.objects.get(id=response.data['task_id'])
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
        self.assertIn('task_id', response.data)
        
        task = Task.objects.get(id=response.data['task_id'])
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

