
from django.db import models
from django.conf import settings

class Company(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

class CompanyMembership(models.Model):
    class Role(models.TextChoices):
        CUSTOMER = 'CUSTOMER', 'Customer'
        AGENT = 'AGENT', 'Agent'
        MANAGER = 'MANAGER', 'Manager'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=Role.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'company'], name='unique_company_membership')
        ]