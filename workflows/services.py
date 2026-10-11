from django.db import transaction
from rest_framework.exceptions import ValidationError
from tickets.models import Ticket, AuditLog
from .models import WorkflowTransition

def transition_ticket_status_service(*, ticket_id: int, user, target_status):
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