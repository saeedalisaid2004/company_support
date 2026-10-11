from django.db import transaction
from rest_framework.exceptions import ValidationError

from companies.models import Company
from tickets.models import Ticket
from tickets.services import Conflict
from .models import Status, WorkflowTransition


def _lock_company(company_id):
    
    Company.objects.select_for_update().get(pk=company_id)


def create_default_workflow(company):
    open_s = Status.objects.create(company=company, name='Open', is_initial=True)
    prog = Status.objects.create(company=company, name='In Progress')
    done = Status.objects.create(company=company, name='Resolved', is_terminal=True)
    WorkflowTransition.objects.create(company=company, from_status=open_s, to_status=prog,
                                      allow_agent=True, allow_manager=True)
    WorkflowTransition.objects.create(company=company, from_status=prog, to_status=done,
                                      allow_agent=True, allow_manager=True)


def _name_taken(company_id, name, exclude_pk=None):
    qs = Status.objects.filter(company_id=company_id, name__iexact=name)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return qs.exists()


def _other_terminal_exists(company_id, exclude_pk):
    return Status.objects.filter(company_id=company_id, is_terminal=True).exclude(pk=exclude_pk).exists()


def create_status(*, company_id, name, is_initial=False, is_terminal=False):
    if is_initial and is_terminal:
        raise ValidationError({"detail": "الحالة لا يمكن أن تكون ابتدائية ونهائية معاً."})
    with transaction.atomic():
        _lock_company(company_id)
        if _name_taken(company_id, name):
            raise ValidationError({"name": "الاسم مستخدم بالفعل في هذه الشركة."})
        if is_initial:  
            Status.objects.filter(company_id=company_id, is_initial=True).update(is_initial=False)
        return Status.objects.create(company_id=company_id, name=name,
                                     is_initial=is_initial, is_terminal=is_terminal)


def update_status(status, **changes):
    with transaction.atomic():
        _lock_company(status.company_id)
        status = Status.objects.get(pk=status.pk)          
        name = changes.get('name', status.name)
        is_initial = changes.get('is_initial', status.is_initial)
        is_terminal = changes.get('is_terminal', status.is_terminal)

        if is_initial and is_terminal:
            raise ValidationError({"detail": "الحالة لا يمكن أن تكون ابتدائية ونهائية معاً."})
        if name != status.name and _name_taken(status.company_id, name, status.pk):
            raise ValidationError({"name": "الاسم مستخدم بالفعل في هذه الشركة."})
        if status.is_initial and not is_initial:
            raise ValidationError({"detail": "عيّن حالة أخرى كابتدائية بدل إزالة العلامة."})
        if status.is_terminal and not is_terminal:
            if Ticket.objects.filter(status=status).exists():
                raise Conflict("لا يمكن إلغاء 'نهائية' عن حالة مستخدمة في تكتات.")
            if not _other_terminal_exists(status.company_id, status.pk):
                raise ValidationError({"detail": "لازم تبقى حالة نهائية واحدة على الأقل."})
        if is_terminal and not status.is_terminal:
            if WorkflowTransition.objects.filter(from_status=status).exists():
                raise ValidationError({"detail": "احذف الانتقالات الخارجة من الحالة أولاً."})
        if is_initial and not status.is_initial:
            Status.objects.filter(company_id=status.company_id, is_initial=True).update(is_initial=False)

        status.name, status.is_initial, status.is_terminal = name, is_initial, is_terminal
        status.save()
        return status


def delete_status(status):
    with transaction.atomic():
        _lock_company(status.company_id)
        status = Status.objects.get(pk=status.pk)
        if status.is_initial:
            raise ValidationError({"detail": "لا يمكن حذف الحالة الابتدائية."})
        if status.is_terminal and not _other_terminal_exists(status.company_id, status.pk):
            raise ValidationError({"detail": "لا يمكن حذف آخر حالة نهائية."})
        if Ticket.objects.filter(status=status).exists():
            raise Conflict("لا يمكن حذف حالة مستخدمة في تكتات.")
        status.delete()      


def create_transition(*, company_id, from_status, to_status, allow_agent, allow_manager):
    with transaction.atomic():
        _lock_company(company_id)
        
        if from_status.company_id != company_id or to_status.company_id != company_id:
            raise ValidationError({"detail": "الحالات لازم تكون من نفس الشركة."})
        if from_status.pk == to_status.pk:
            raise ValidationError({"detail": "لا يمكن الانتقال من حالة إلى نفسها."})
        if from_status.is_terminal:
            raise ValidationError({"detail": "الحالة النهائية ليس لها انتقالات خارجة."})
        if not (allow_agent or allow_manager):
            raise ValidationError({"detail": "حدد دور واحد على الأقل."})
        if WorkflowTransition.objects.filter(company_id=company_id, from_status=from_status,
                                             to_status=to_status).exists():
            raise Conflict("هذا الانتقال موجود بالفعل.")
        return WorkflowTransition.objects.create(
            company_id=company_id, from_status=from_status, to_status=to_status,
            allow_agent=allow_agent, allow_manager=allow_manager)


def update_transition_roles(transition, *, allow_agent, allow_manager):
    if not (allow_agent or allow_manager):
        raise ValidationError({"detail": "حدد دور واحد على الأقل."})
    transition.allow_agent, transition.allow_manager = allow_agent, allow_manager
    transition.save(update_fields=['allow_agent', 'allow_manager'])
    return transition