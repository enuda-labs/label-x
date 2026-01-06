from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from account.models import Project, User, UserBankAccount

@receiver([post_save, post_delete], sender=Project)
def invalidate_project_cache(sender, instance, **kwargs):
    if instance.created_by:
        cache.delete_pattern(f"*task_completion_stats_{instance.created_by.id}*")
    cache.delete_pattern(f"*project_detail_GET_/api/v1/account/projects/{instance.id}/*")
    
@receiver([post_save, post_delete], sender=User)
def invalidate_user_cache(sender, instance, **kwargs):
    cache.delete_pattern(f"*user_detail_{instance.id}*")

@receiver([post_save, post_delete], sender=UserBankAccount)
def invalidate_user_bank_account_cache(sender, instance, **kwargs):
    cache.delete_pattern(f"*user_bank_accounts_{instance.user.id}*")
    