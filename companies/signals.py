from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Company
from workflows.models import Status, WorkflowTransition

@receiver(post_save, sender=Company)
def create_default_workflow(sender, instance, created, **kwargs):
    if created:
        open_status = Status.objects.create(company=instance, name='Open', is_initial=True)
        in_progress = Status.objects.create(company=instance, name='In Progress')
        resolved = Status.objects.create(company=instance, name='Resolved', is_terminal=True)

        WorkflowTransition.objects.create(
            company=instance,
            from_status=open_status,
            to_status=in_progress
        )
        WorkflowTransition.objects.create(
            company=instance,
            from_status=in_progress,
            to_status=resolved
        )