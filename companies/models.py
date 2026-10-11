from django.conf import settings
from django.db import models

class Company(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class CompanyMembership(models.Model):
    class Role(models.TextChoices):
        CUSTOMER = 'CUSTOMER', 'Customer'
        AGENT = 'AGENT', 'Agent'
        MANAGER = 'MANAGER', 'Manager'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='memberships')
    company = models.ForeignKey(Company, on_delete=models.CASCADE,
                                related_name='memberships')
    role = models.CharField(max_length=20, choices=Role.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'company'], name='unique_company_membership')
        ]