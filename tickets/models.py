from django.db import models
from django.conf import settings
from workflows.models import Status

class Category(models.Model):
    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['company', 'name'], name='unique_category_per_company')
        ]

    def __str__(self):
        return f"{self.name} ({self.company.name})"

class Ticket(models.Model):
    class Priority(models.TextChoices):
        LOW = 'LOW', 'Low'
        MEDIUM = 'MEDIUM', 'Medium'
        HIGH = 'HIGH', 'High'
        URGENT = 'URGENT', 'Urgent'

    company = models.ForeignKey('companies.Company', on_delete=models.CASCADE, related_name='tickets')
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_tickets')
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    status = models.ForeignKey(Status, on_delete=models.PROTECT)
    assigned_agent = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='assigned_tickets'
    )
    
    title = models.CharField(max_length=255)
    description = models.TextField()
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    
    has_left_initial_status = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"#{self.id} - {self.title}"


class Comment(models.Model):
    class CommentType(models.TextChoices):
        PUBLIC = 'PUBLIC', 'Public Comment'
        INTERNAL_NOTE = 'INTERNAL_NOTE', 'Internal Note'

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.TextField()
    type = models.CharField(max_length=20, choices=CommentType.choices, default=CommentType.PUBLIC)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']


class AuditLog(models.Model):
    class EventType(models.TextChoices):
        CREATED = 'CREATED', 'Created'
        ASSIGNMENT = 'ASSIGNMENT', 'Assignment'
        REASSIGNMENT = 'REASSIGNMENT', 'Reassignment'
        STATUS_CHANGE = 'STATUS_CHANGE', 'Status Change'
        PRIORITY_CHANGE = 'PRIORITY_CHANGE', 'Priority Change'

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='audit_logs')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    event_type = models.CharField(max_length=30, choices=EventType.choices)
    old_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']