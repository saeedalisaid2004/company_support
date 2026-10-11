from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Company


@receiver(post_save, sender=Company)
def create_default_workflow(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        from workflows.services import create_default_workflow as build
        build(instance)