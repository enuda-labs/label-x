from concurrent.futures import ThreadPoolExecutor
from re import S
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
        self.api_key = None
        self.session = requests.Session()
        self.fail_count = 0
        self.success_count = 0

    def log(self, message):
        print(f"ℹ️ INFO {self.user_data['username']}: {message}")

    def mark_success(self):
        self.success_count += 1
    
    def mark_failure(self):
        self.fail_count +=1

    def register(self):
        """Register a new user"""
        url = f"{self.base_url}/api/v1/account/register/"
        req_data = {"role": "organization", **self.user_data}
        response = self.session.post(url, json=req_data)

        if response.status_code == 201:
            print(f"✅ User {self.user_data['username']} registered successfully")
            self.login()
            self.mark_success()
            return response.json()
        else:
            print(
                f"❌ Registration failed for {self.user_data['username']}: {response.status_code}"
            )
            print(f"Response: {response.text}")
            self.mark_failure()
            return None

    def login(self):
        """Login user and store auth token"""
        url = f"{self.base_url}/api/v1/account/login/"
        login_data = {
            "username": self.user_data["username"],
            "password": self.user_data["password"],
        }
        response = self.session.post(url, json=login_data)

        if response.status_code == 200:
            data = response.json()
            self.auth_token = data.get("access")
            if self.auth_token:

                self.session.headers.update(
                    {"Authorization": f"Bearer {self.auth_token}"}
                )
            self.log("Logged in successfully")
            self.generate_production_key()
            self.mark_success()
            return data
        else:
            print(
                f"❌ Login failed for {self.user_data['username']}: {response.status_code}"
            )
            self.mark_failure()
            return None

    def get_user_projects(self):
        self.log("Getting user project list")
        url = f"{self.base_url}/api/v1/account/organization/project/list/"
        response = self.session.get(url)
        if response.status_code == 200:
            self.log("Successfully retrieved users projects")
            self.mark_success()
            return response.json()

        else:
            self.log(f"Failed to get users projects, error code:{response.status_code}")
            self.mark_failure()
            return []

    def create_user_task(self):
        user_projects = self.get_user_projects()
        if len(user_projects) > 0:
            url = f"{self.base_url}/api/v1/tasks/"
            selected_project = user_projects[0]
            self.log(f"Creating dummy task for project {selected_project.get('name')}")

            req_data = {
                "task_type": "TEXT",
                "data": "You are very very stupid",
                "priority": "NORMAL",
                "group": selected_project.get("id"),
            }
            response = self.session.post(url, json=req_data)
            if response.status_code == 200 or response.status_code == 201:
                self.log("Successfully created dummy task")
                self.mark_success()
                self.conclude_flow()
                
            else:
                self.log(
                    f"Could not create dummy task error:{response.status_code} {response.text}"
                )
                self.mark_failure()
        else:
            self.log("Cannot create tasks when user does not have any projects")
            self.mark_failure()

    def create_project(self):
        self.log("Creating project")
        url = f"{self.base_url}/api/v1/account/organization/project/"
        req_data = {
            "name": f"Project-{self.user_data.get('username')}",
            "Description": f"A project created during testing for {self.user_data.get('username')}",
        }
        response = self.session.post(url, req_data)
        if response.status_code == 200 or response.status_code == 201:
            self.log("Project created successfully")
            self.mark_success()
        else:
            self.log(
                f"Could not create project for user error code:{response.status_code}"
            )
            self.mark_success()
        self.create_user_task()

    def get_subscriptions_plans(self):
        self.log("Getting plans lit")
        url = f"{self.base_url}/api/v1/subscription/plans"
        response = self.session.get(url)

        if response.status_code == 200:
            data = response.json()
            plans = data.get("detail")
            if len(plans) < 1:
                self.log("No plans were found on the database")
            self.mark_success()
            return plans
        else:
            self.mark_failure()
            self.log("Failed to get subscription plans")

    def generate_stripe_link(self):
        plans = self.get_subscriptions_plans()
        if len(plans) > 0:
            selected_plan = plans[0]

            self.log(
                f"Generating stripe url for payment for plan {selected_plan.get('name')}"
            )
            url = f"{self.base_url}/api/v1/subscription/initialize/"
            req_data = {"subscription_plan": selected_plan.get("id")}
            response = self.session.post(url, req_data)
            if response.status_code == 200:
                data = response.json()
                payment_url = data.get("data").get("payment_url")
                self.log(f"Generated stripe url {payment_url}")
                self.mark_success()
            else:
                self.log(
                    f"Could not generate stripe payment url error code: {response.status_code}"
                )
                self.mark_failure()

            self.create_project()

    def generate_production_key(self):
        self.log("Generating api key..")
        url = f"{self.base_url}/api/v1/keys/generate/production/"
        req_data = {"key_name": {f"{self.user_data.get('username')}-prod-key"}}
        response = self.session.post(url, req_data)
        if response.status_code == 200 or response.status_code == 201:
            data = response.json()
            # Authenticate using api key instead of Bearer token
            self.api_key = data.get("data", {}).get("api_key")
            self.session.headers.update({"X-Api-Key": self.api_key})

            # self.session.headers.pop("Authorization", None)
            self.log("Generated and set production api key")
            self.mark_success()
            self.generate_stripe_link()
            
        else:
            self.mark_failure()
            self.log(f"Failed to generate api key - status: {response.status_code}")
            return None

    def make_authenticated_request(self, method, endpoint, data=None):
        """Helper method for making authenticated requests"""
        url = f"{self.base_url}{endpoint}"

        if method.upper() == "GET":
            response = self.session.get(url)
        elif method.upper() == "POST":
            response = self.session.post(url, json=data)
        elif method.upper() == "PUT":
            response = self.session.put(url, json=data)
        elif method.upper() == "DELETE":
            response = self.session.delete(url)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        return response

    def test_endpoint(
        self, method, endpoint, data=None, expected_status=200, test_name=""
    ):
        """Generic method to test any endpoint"""
        response = self.make_authenticated_request(method, endpoint, data)

        if response.status_code == expected_status:
            print(
                f"✅ {test_name or f'{method} {endpoint}'} - Status: {response.status_code}"
            )
            return response.json() if response.content else None
        else:
            print(
                f"❌ {test_name or f'{method} {endpoint}'} - Expected: {expected_status}, Got: {response.status_code}"
            )
            print(f"Response: {response.text}")
            return None

    def conclude_flow(self):
        self.log("Test flow is complete, all hail the king")
        
        stats = {
            "total_requests_made": self.fail_count + self.success_count,
            "fail_count": self.fail_count,
            "success_count": self.success_count
        }
        self.log(f"🪼🪼🪼🪼🪼🪼🪼 Statistics report {stats}")

    def teardown(self):
        print(f"Deleting {self.user_data.get('email')}...")
        CustomUser.objects.filter(email=self.user_data.get("email")).delete()

    def start(self):
        """Main test flow"""
        print(f"\n🚀 Starting tests for user: {self.user_data['username']}")

        # Basic flow: register -> login
        self.register()
        self.teardown()

        print(f"✅ Basic flow completed for {self.user_data['username']}\n")


class Command(BaseCommand):
    help = "Run functional tests on API endpoints"

    def add_arguments(self, parser):
        parser.add_argument(
            "--base-url",
            type=str,
            default="http://localhost:8080",
            help="Base URL for the API (default: http://localhost:8080)",
        )
        parser.add_argument(
            "--users",
            type=int,
            default=10,
            help="Number of test users to create (default: 5)",
        )

    def handle(self, *args: Any, **options: Any) -> str | None:
        base_url = options["base_url"]
        user_count = options["users"]

        print(f"🧪 Starting API functional tests with {user_count} users")
        print(f"🌐 Base URL: {base_url}\n")

        # Generate synthetic user data
        user_list = []
        for count in range(user_count):
            user_data = {
                "username": f"testuser{count}",
                "email": f"testuser{count}@example.com",
                "password": f"TestP@ssword{count}!",
            }
            user_list.append(user_data)

        # Run tests for each user
        # for user_data in user_list:
        #     flow_test = FlowTest(user_data, base_url)
        #     flow_test.start()
        
        print('Spinning up worker threads')
        print('==========================')
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for user_data in user_list:
                flow_test = FlowTest(user_data, base_url)
                future = executor.submit(flow_test.start)
                futures.append(future)
                
            for future in futures:
                try:
                    result = future.result()
                except Exception as e:
                    print(f"Flow test flowed {e}")

        """
        Register 
        Login
        Generate api key
        Get subscription list
        Subscribe
        Create a project
        create a task
        roll api key
        """

        print("🎉 All functional tests completed!")
