from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from payment.models import Transaction

@receiver([post_save, post_delete], sender=Transaction)
def invalidate_transaction_cache(sender, instance, **kwargs):
    print('invalidating transaction cache')
    cache.delete_pattern(f"*user_transaction_history_{instance.user.id}*")