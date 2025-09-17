from typing import Any
from django.core.management import BaseCommand
from django.conf import settings
import os
from pathlib import Path

from subscription.models import SubscriptionPlan
from dotenv import load_dotenv

# Load environment variables from .env file in project root
env_file = Path(settings.BASE_DIR) / '.env'
if env_file.exists():
    load_dotenv(env_file, override=True)
else:
    print("Warning: .env file not found. Using system environment variables.")


plans = [
    {
        "name": "Starter",
        "monthly_fee": "10.00",
        "included_data_points": 5000,
        "stripe_monthly_plan_id": os.getenv("STARTER_PLAN_ID"),
        "cost_per_extra_request": 7,
        "included_requests": 10
    },
    {
        "name": "Teams",
        "monthly_fee": "19.00",
        "included_data_points": 10000,
        "stripe_monthly_plan_id": os.getenv("TEAMS_PLAN_ID"),
        "cost_per_extra_request": 7,
        "included_requests": 10

    },
    {
        "name": "Enterprise",
        "monthly_fee": "30.00",
        "included_data_points": 20000,
        "stripe_monthly_plan_id": os.getenv("ENTERPRISE_PLAN_ID"),
        "cost_per_extra_request": 7,
        "included_requests": 10
    },
]

class Command(BaseCommand):
    def handle(self, *args: Any, **options: Any) -> str | None:
        for plan in plans:
            if not SubscriptionPlan.objects.filter(name__iexact=plan.get('name', "")).exists():
                SubscriptionPlan.objects.create(
                    name=plan.get('name'),
                    monthly_fee=plan.get('monthly_fee'),
                    included_data_points= plan.get('included_data_points'),
                    stripe_monthly_plan_id=plan.get("stripe_monthly_plan_id"),
                    cost_per_extra_request=plan.get("cost_per_extra_request"),
                    included_requests=plan.get('included_requests')
                )
                print(f"Created {plan.get('name')} plan")
            else:
                print(f"Skipped {plan.get('name')} plan because it already exits")