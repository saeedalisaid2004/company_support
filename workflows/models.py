from django.db import models
from companies.models import Company

class Status(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='statuses')
    name = models.CharField(max_length=50)
    is_initial = models.BooleanField(default=False)
    is_terminal = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = 'Statuses'

    def __str__(self):
        return f"{self.company.name} - {self.name}"


class WorkflowTransition(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='workflow_transitions')
    from_status = models.ForeignKey(Status, on_delete=models.CASCADE, related_name='transitions_from')
    to_status = models.ForeignKey(Status, on_delete=models.CASCADE, related_name='transitions_to')

    class Meta:
        unique_together = ('company', 'from_status', 'to_status')

    def __str__(self):
        return f"{self.from_status.name} -> {self.to_status.name}"