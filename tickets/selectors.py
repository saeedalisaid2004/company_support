from django.db.models import Q
from django.shortcuts import get_object_or_404

from companies.models import CompanyMembership
from .models import Ticket

Role = CompanyMembership.Role


def get_membership(user, company_id):
    return get_object_or_404(CompanyMembership, user=user, company_id=company_id)


def is_staff(membership):
    return membership.role in (Role.AGENT, Role.MANAGER)


def accessible_tickets(user, membership):
    qs = Ticket.objects.filter(company_id=membership.company_id)

    if membership.role == Role.CUSTOMER:
        qs = qs.filter(creator=user)
    elif membership.role == Role.AGENT:
        qs = qs.filter(Q(assigned_agent__isnull=True) | Q(assigned_agent=user))

    return qs.select_related('category', 'status', 'creator', 'assigned_agent')


def get_accessible_ticket(user, membership, ticket_id):
    return get_object_or_404(accessible_tickets(user, membership), pk=ticket_id)