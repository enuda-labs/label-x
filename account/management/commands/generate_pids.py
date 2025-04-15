import uuid
from django.core.management import BaseCommand

from account.models import CustomUser

class Command(BaseCommand):
    help = "Assigns pids to all user accounts if they dont already have one"
    
    def handle(self, *args, **options):
        print('assigning pids')
        users = CustomUser.objects.all()
        for user in users:
            if not user.pid:
                user.pid = uuid.uuid4()
                user.save()
                print('assigned pid to', user.email)
            