from django.core.management.base import BaseCommand
from subscription.models import SubscriptionPlan


class Command(BaseCommand):
    help = 'Populate features for existing subscription plans'

    def handle(self, *args, **options):
        # Default features for each plan
        plan_features = {
            'starter': [
                'Up to 10,000 data points',
                '48-hour turnaround time',
                'Basic API access',
                'Email support',
            ],
            'teams': [
                'Up to 50,000 data points',
                '24-hour turnaround time',
                'Full API access',
                'Priority support',
                'Custom reports',
                'Team collaboration',
            ],
            'pro': [
                'Up to 50,000 data points',
                '24-hour turnaround time',
                'Full API access',
                'Priority support',
                'Custom reports',
            ],
            'enterprise': [
                'Unlimited data points',
                '12-hour turnaround time',
                'Advanced API access',
                '24/7 dedicated support',
                'Custom integrations',
                'Team collaboration',
            ],
        }

        updated_count = 0
        skipped_count = 0
        for plan_name, features in plan_features.items():
            plan = SubscriptionPlan.objects.filter(name__iexact=plan_name).first()
            if plan:
                # Only update if features are empty or not set
                if not plan.features or len(plan.features) == 0:
                    plan.features = features
                    plan.save()
                    self.stdout.write(
                        self.style.SUCCESS(f'Updated {plan.name} with {len(features)} features')
                    )
                    updated_count += 1
                else:
                    self.stdout.write(
                        self.style.WARNING(f'Plan "{plan.name}" already has features, skipping...')
                    )
                    skipped_count += 1
            else:
                self.stdout.write(
                    self.style.WARNING(f'Plan "{plan_name}" not found, skipping...')
                )

        self.stdout.write(
            self.style.SUCCESS(f'\n✅ Successfully updated {updated_count} plan(s)')
        )
        if skipped_count > 0:
            self.stdout.write(
                self.style.WARNING(f'⚠️  Skipped {skipped_count} plan(s) (already have features)')
            )

