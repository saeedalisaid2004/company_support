from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError, APIException
from rest_framework import status
from .models import Ticket, AuditLog

class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'حدث تعارض في الطلب (Conflict).'
    default_code = 'conflict'

def claim_ticket_service(*, ticket_id: int, agent_user):
    with transaction.atomic():
        ticket = Ticket.objects.select_for_update().filter(id=ticket_id).first()
        
        if not ticket:
            raise ValidationError({"detail": "التكت غير موجود."})

        if ticket.status.is_terminal:
            raise ValidationError({"detail": "لا يمكن حجز تكت مغلق/منتهي."})

        if ticket.assigned_agent is not None:
            raise Conflict()

        ticket.assigned_agent = agent_user
        ticket.save()

        AuditLog.objects.create(
            ticket=ticket,
            actor=agent_user,
            event_type=AuditLog.EventType.ASSIGNMENT,
            old_value={"assigned_agent": None},
            new_value={"assigned_agent": agent_user.id}
        )
    return ticket

def transition_ticket_status_service(*, ticket_id: int, user, target_status):
    
    from .models import WorkflowTransition

    with transaction.atomic():
        ticket = Ticket.objects.select_for_update().filter(id=ticket_id).first()

        if not ticket:
            raise ValidationError({"detail": "التكت غير موجود."})

        if ticket.status.is_terminal:
            raise ValidationError({"detail": "لا يمكن تغيير حالة تكت منتهي/مغلق."})

        allowed_transition = WorkflowTransition.objects.filter(
            company_id=ticket.company_id,
            from_status=ticket.status,
            to_status=target_status
        ).exists()

        if not allowed_transition:
            raise ValidationError({
                "detail": f"غير مسموح بالانتقال المباشر من الحالة '{ticket.status.name}' إلى '{target_status.name}'."
            })

        old_status_name = ticket.status.name
        ticket.status = target_status
        ticket.save()

        AuditLog.objects.create(
            ticket=ticket,
            actor=user,
            event_type=AuditLog.EventType.STATUS_CHANGE,
            old_value={"status": old_status_name},
            new_value={"status": target_status.name}
        )

    return ticket