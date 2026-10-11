from rest_framework.permissions import BasePermission, SAFE_METHODS
from companies.models import CompanyMembership

Role = CompanyMembership.Role


class StaffReadManagerWrite(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        m = CompanyMembership.objects.filter(
            user=request.user, company_id=view.kwargs['company_pk']).first()
        if m is None:
            return False
        if request.method in SAFE_METHODS:
            return m.role in (Role.AGENT, Role.MANAGER)
        return m.role == Role.MANAGER