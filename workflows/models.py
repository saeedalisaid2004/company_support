from django.db import models
from django.db.models import Q
from companies.models import Company


class Status(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='statuses')
    name = models.CharField(max_length=50)
    is_initial = models.BooleanField(default=False)
    is_terminal = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = 'Statuses'
        constraints = [
            models.UniqueConstraint(fields=['company', 'name'],
                                    name='unique_status_name_per_company'),
            models.UniqueConstraint(fields=['company'], condition=Q(is_initial=True),
                                    name='one_initial_status_per_company'),
            models.CheckConstraint(check=~(Q(is_initial=True) & Q(is_terminal=True)),
                                   name='status_not_initial_and_terminal'),
        ]

    def __str__(self):
        return f"{self.company.name} - {self.name}"


class WorkflowTransition(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='workflow_transitions')
    from_status = models.ForeignKey(Status, on_delete=models.CASCADE, related_name='transitions_from')
    to_status = models.ForeignKey(Status, on_delete=models.CASCADE, related_name='transitions_to')
    allow_agent = models.BooleanField(default=True)
    allow_manager = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['company', 'from_status', 'to_status'],
                                    name='unique_transition_per_company'),
            models.CheckConstraint(check=~Q(from_status=models.F('to_status')),
                                   name='transition_not_self'),
            models.CheckConstraint(check=Q(allow_agent=True) | Q(allow_manager=True),
                                   name='transition_has_a_role'),
        ]

    def __str__(self):
        return f"{self.from_status.name} -> {self.to_status.name}"