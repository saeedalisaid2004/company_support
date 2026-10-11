from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from companies.models import Company, CompanyMembership
from workflows.models import Status, WorkflowTransition
from tickets.models import Category, Ticket, Comment
from django.utils import timezone

User = get_user_model()

class Command(BaseCommand):
    help = "Seeding the database with initial dummy data for testing."

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("Starting database seeding..."))

        manager_user, _ = User.objects.get_or_create(
            username="manager_alex", 
            defaults={"email": "manager@techcorp.com", "first_name": "Alex", "last_name": "Manager"}
        )
        manager_user.set_password("password123")
        manager_user.save()

        agent_user, _ = User.objects.get_or_create(
            username="agent_sarah", 
            defaults={"email": "sarah@techcorp.com", "first_name": "Sarah", "last_name": "Agent"}
        )
        agent_user.set_password("password123")
        agent_user.save()

        customer_user, _ = User.objects.get_or_create(
            username="customer_john", 
            defaults={"email": "john@example.com", "first_name": "John", "last_name": "Customer"}
        )
        customer_user.set_password("password123")
        customer_user.save()

        company, _ = Company.objects.get_or_create(name="TechCorp Solutions")

        CompanyMembership.objects.get_or_create(company=company, user=manager_user, defaults={"role": CompanyMembership.Role.MANAGER})
        CompanyMembership.objects.get_or_create(company=company, user=agent_user, defaults={"role": CompanyMembership.Role.AGENT})
        CompanyMembership.objects.get_or_create(company=company, user=customer_user, defaults={"role": CompanyMembership.Role.CUSTOMER})

        status_new, _ = Status.objects.get_or_create(company=company, name="New", defaults={"is_initial": True, "is_terminal": False})
        status_in_progress, _ = Status.objects.get_or_create(company=company, name="In Progress", defaults={"is_initial": False, "is_terminal": False})
        status_resolved, _ = Status.objects.get_or_create(company=company, name="Resolved", defaults={"is_initial": False, "is_terminal": True})
        status_closed, _ = Status.objects.get_or_create(company=company, name="Closed", defaults={"is_initial": False, "is_terminal": True})

        WorkflowTransition.objects.get_or_create(company=company, from_status=status_new, to_status=status_in_progress)
        WorkflowTransition.objects.get_or_create(company=company, from_status=status_in_progress, to_status=status_resolved)
        WorkflowTransition.objects.get_or_create(company=company, from_status=status_resolved, to_status=status_closed)

        cat_tech, _ = Category.objects.get_or_create(company=company, name="Technical Issue")
        cat_billing, _ = Category.objects.get_or_create(company=company, name="Billing Query")

        ticket, created = Ticket.objects.get_or_create(
            title="Cannot access dashboard",
            company=company,
            creator=customer_user,
            defaults={
                "description": "Getting 500 error when trying to open analytics page.",
                "status": status_new,
                "category": cat_tech,
                "priority": Ticket.Priority.HIGH,
            }
        )

        if created:
            Comment.objects.create(
                ticket=ticket,
                author=customer_user,
                body="Please fix this urgently.",
                type=Comment.CommentType.PUBLIC
            )

        self.stdout.write(self.style.SUCCESS("Database seeded successfully!"))
        self.stdout.write(self.style.SUCCESS("Test Users Created (Password for all: password123):"))
        self.stdout.write(f" - Manager: manager_alex")
        self.stdout.write(f" - Agent: agent_sarah")
        self.stdout.write(f" - Customer: customer_john")