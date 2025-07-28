from typing import Any
from django.core.management import BaseCommand
import requests
import json

from account.models import CustomUser


class FlowTest:
    def __init__(self, user_data, base_url="http://localhost:8080") -> None:
        self.user_data = user_data
        self.base_url = base_url
        self.auth_token = None
        self.session = requests.Session()
    
    def register(self):
        """Register a new user"""
        url = f"{self.base_url}/api/v1/account/register/"
        response = self.session.post(url, json=self.user_data)
        
        if response.status_code == 201:
            print(f"✅ User {self.user_data['username']} registered successfully")
            return response.json()
        else:
            print(f"❌ Registration failed for {self.user_data['username']}: {response.status_code}")
            print(f"Response: {response.text}")
            return None
    
    def login(self):
        """Login user and store auth token"""
        url = f"{self.base_url}/api/v1/account/login/"
        login_data = {
            "username": self.user_data["username"],
            "password": self.user_data["password"]
        }
        response = self.session.post(url, json=login_data)
        
        if response.status_code == 200:
            data = response.json()
            self.auth_token = data.get('token') or data.get('access_token')
            if self.auth_token:
                self.session.headers.update({'Authorization': f'Bearer {self.auth_token}'})
            print(f"✅ User {self.user_data['username']} logged in successfully")
            return data
        else:
            print(f"❌ Login failed for {self.user_data['username']}: {response.status_code}")
            return None
    
    def make_authenticated_request(self, method, endpoint, data=None):
        """Helper method for making authenticated requests"""
        url = f"{self.base_url}{endpoint}"
        
        if method.upper() == 'GET':
            response = self.session.get(url)
        elif method.upper() == 'POST':
            response = self.session.post(url, json=data)
        elif method.upper() == 'PUT':
            response = self.session.put(url, json=data)
        elif method.upper() == 'DELETE':
            response = self.session.delete(url)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        return response
    
    def test_endpoint(self, method, endpoint, data=None, expected_status=200, test_name=""):
        """Generic method to test any endpoint"""
        response = self.make_authenticated_request(method, endpoint, data)
        
        if response.status_code == expected_status:
            print(f"✅ {test_name or f'{method} {endpoint}'} - Status: {response.status_code}")
            return response.json() if response.content else None
        else:
            print(f"❌ {test_name or f'{method} {endpoint}'} - Expected: {expected_status}, Got: {response.status_code}")
            print(f"Response: {response.text}")
            return None
    
    def teardown(self):
        print(f"Deleting {self.user_data.get('email')}...")
        CustomUser.objects.filter(email=self.user_data.get('email')).delete()
    
    def start(self):
        """Main test flow"""
        print(f"\n🚀 Starting tests for user: {self.user_data['username']}")
        
        # Basic flow: register -> login
        self.register()
        self.login()
        self.teardown()
        
        # Add your custom test methods here
        print(f"✅ Basic flow completed for {self.user_data['username']}\n")


class Command(BaseCommand):
    help = 'Run functional tests on API endpoints'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--base-url',
            type=str,
            default='http://localhost:8080',
            help='Base URL for the API (default: http://localhost:8080)'
        )
        parser.add_argument(
            '--users',
            type=int,
            default=5,
            help='Number of test users to create (default: 5)'
        )
    
    def handle(self, *args: Any, **options: Any) -> str | None:
        base_url = options['base_url']
        user_count = options['users']
        
        print(f"🧪 Starting API functional tests with {user_count} users")
        print(f"🌐 Base URL: {base_url}\n")
        
        # Generate synthetic user data
        user_list = []
        for count in range(user_count):
            user_data = {
                "username": f"testuser{count}",
                "email": f"testuser{count}@example.com",
                "password": f"TestP@ssword{count}!"
            }
            user_list.append(user_data)
        
        # Run tests for each user    
        for user_data in user_list:
            flow_test = FlowTest(user_data, base_url)
            flow_test.start()
        
        print("🎉 All functional tests completed!")