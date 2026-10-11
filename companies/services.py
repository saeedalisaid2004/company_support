from django.db import transaction
from rest_framework import status
from rest_framework.exceptions import APIException, NotFound

from .models import Company, CompanyMembership

Role = CompanyMembership.Role


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'تعارض في الطلب.'
    default_code = 'conflict'


def _lock_company(company_id):
    
    Company.objects.select_for_update().get(pk=company_id)


def _lock_membership(company_id, user_id):
    try:
        return (CompanyMembership.objects
                .select_for_update(of=('self',))
                .get(company_id=company_id, user_id=user_id))
    except CompanyMembership.DoesNotExist:
        raise NotFound("العضو غير موجود في هذه الشركة.")


def _check_can_leave_role(membership, new_role):
    from tickets.models import Ticket   

    if membership.role == Role.MANAGER and new_role != Role.MANAGER:
        managers = CompanyMembership.objects.filter(
            company_id=membership.company_id, role=Role.MANAGER).count()
        if managers <= 1:
            raise Conflict("لا يمكن إزالة أو خفض دور مدير الشركة الأخير.")

    if membership.role == Role.AGENT and new_role != Role.AGENT:
        if Ticket.objects.filter(company_id=membership.company_id,
                                 assigned_agent_id=membership.user_id,
                                 status__is_terminal=False).exists():
            raise Conflict("الوكيل لديه تذاكر غير محلولة مسندة إليه.")


def add_member(*, company_id, user_id, role):
    with transaction.atomic():
        _lock_company(company_id)
        if CompanyMembership.objects.filter(company_id=company_id, user_id=user_id).exists():
            raise Conflict("المستخدم عضو بالفعل في هذه الشركة.")
        return CompanyMembership.objects.create(
            company_id=company_id, user_id=user_id, role=role)


def change_role(*, company_id, user_id, new_role):
    with transaction.atomic():
        _lock_company(company_id)
        membership = _lock_membership(company_id, user_id)
        if membership.role == new_role:
            return membership
        _check_can_leave_role(membership, new_role)
        membership.role = new_role
        membership.save(update_fields=['role'])
        return membership


def remove_member(*, company_id, user_id):
    with transaction.atomic():
        _lock_company(company_id)
        membership = _lock_membership(company_id, user_id)
        _check_can_leave_role(membership, None)
        membership.delete()