from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import (
    APIException, NotFound, PermissionDenied, ValidationError,
)

from companies.models import CompanyMembership
from workflows.models import Status, WorkflowTransition
from .models import Ticket, AuditLog

Role = CompanyMembership.Role


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'حدث تعارض في الطلب.'
    default_code = 'conflict'


def _lock_ticket(company_id, ticket_id):
    try:
        return (Ticket.objects.select_for_update(of=('self',))
                .select_related('status')
                .get(pk=ticket_id, company_id=company_id))   # الشركة جزء من البحث
    except (Ticket.DoesNotExist, ValueError):
        raise NotFound("التكت غير موجود.")


def _lock_agent_membership(company_id, user_id):
    """يقفل عضوية الـ agent. لو بيتشال أو بيتغير دوره في نفس اللحظة، واحد بيستنى التاني."""
    return (CompanyMembership.objects
            .select_for_update(of=('self',))
            .filter(company_id=company_id, user_id=user_id, role=Role.AGENT)
            .exists())


def _role_allowed(transition, role):
    if role == Role.AGENT:
        return transition.allow_agent
    if role == Role.MANAGER:
        return transition.allow_manager
    return False


def claim_ticket_service(*, company_id, ticket_id, agent_user):
    with transaction.atomic():
        ticket = _lock_ticket(company_id, ticket_id)

        if not _lock_agent_membership(company_id, agent_user.id):
            raise PermissionDenied("الوكلاء فقط هم من يمكنهم حجز التكتات.")
        if ticket.status.is_terminal:
            raise ValidationError({"detail": "لا يمكن حجز تكت منتهي."})
        if ticket.assigned_agent_id is not None:
            raise Conflict("التكت محجوز بالفعل.")

        ticket.assigned_agent = agent_user
        ticket.save(update_fields=['assigned_agent', 'updated_at'])

        AuditLog.objects.create(
            ticket=ticket, actor=agent_user,
            event_type=AuditLog.EventType.ASSIGNMENT,
            old_value={"assigned_agent": None},
            new_value={"assigned_agent": agent_user.id},
        )
    return ticket


def assign_ticket_service(*, company_id, ticket_id, actor, agent_id):
    with transaction.atomic():
        ticket = _lock_ticket(company_id, ticket_id)

        if not _lock_agent_membership(company_id, agent_id):
            raise ValidationError({"agent_id": "لازم يكون وكيل (Agent) في نفس الشركة."})
        if ticket.status.is_terminal:
            raise ValidationError({"detail": "لا يمكن إسناد تكت منتهي."})

        old_id = ticket.assigned_agent_id
        if old_id == agent_id:
            raise ValidationError({"detail": "التكت مسند لنفس الوكيل بالفعل."})

        ticket.assigned_agent_id = agent_id
        ticket.save(update_fields=['assigned_agent', 'updated_at'])

        AuditLog.objects.create(
            ticket=ticket, actor=actor,
            event_type=(AuditLog.EventType.ASSIGNMENT if old_id is None
                        else AuditLog.EventType.REASSIGNMENT),
            old_value={"assigned_agent": old_id},
            new_value={"assigned_agent": agent_id},
        )
    return ticket


def transition_ticket_status_service(*, company_id, ticket_id, user, role,
                                     target_status_id, expected_status_id=None):
    try:
        target_status_id = int(target_status_id)
    except (TypeError, ValueError):
        raise ValidationError({"status_id": "قيمة صحيحة مطلوبة."})

    with transaction.atomic():
        ticket = _lock_ticket(company_id, ticket_id)

        if role == Role.CUSTOMER:
            raise PermissionDenied("العميل لا يستطيع تغيير الحالة.")
        if role == Role.AGENT and ticket.assigned_agent_id != user.id:
            raise PermissionDenied("يمكنك تغيير حالة التكتات المسندة إليك فقط.")

        target = Status.objects.filter(pk=target_status_id, company_id=company_id).first()
        if target is None:
            raise ValidationError({"status_id": "حالة غير صالحة."})

        if expected_status_id is not None and str(ticket.status_id) != str(expected_status_id):
            raise Conflict("حالة التكت تغيّرت. أعد التحميل وحاول مجدداً.")

        if ticket.status.is_terminal:
            raise ValidationError({"detail": "لا يمكن تغيير حالة تكت منتهي."})

        transition = WorkflowTransition.objects.filter(
            company_id=company_id, from_status=ticket.status, to_status=target
        ).first()
        if transition is None or not _role_allowed(transition, role):
            raise ValidationError({"detail": "هذا الانتقال غير مسموح."})

        old = ticket.status
        if old.is_initial:
            ticket.has_left_initial_status = True        
        ticket.status = target
        if target.is_terminal:
            ticket.resolved_at = timezone.now()
        ticket.save(update_fields=['status', 'has_left_initial_status',
                                   'resolved_at', 'updated_at'])

        AuditLog.objects.create(
            ticket=ticket, actor=user,
            event_type=AuditLog.EventType.STATUS_CHANGE,
            old_value={"status": old.name},
            new_value={"status": target.name},
        )
    return ticket