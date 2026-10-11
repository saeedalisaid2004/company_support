from rest_framework.permissions import BasePermission, SAFE_METHODS
from companies.models import CompanyMembership

Role = CompanyMembership.Role


class MemberReadManagerWrite(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        m = CompanyMembership.objects.filter(
            user=request.user, company_id=view.kwargs['company_pk']).first()
        if m is None:
            return False
        return request.method in SAFE_METHODS or m.role == Role.MANAGER