from rest_framework import permissions
from .models import CompanyMembership


class IsCompanyManager(permissions.BasePermission):

    def has_permission(self, request, view):
    
        kwarg = getattr(view, 'company_lookup_kwarg', 'company_pk')
        company_id = view.kwargs.get(kwarg)
        if not company_id or not request.user.is_authenticated:
            return False
        return CompanyMembership.objects.filter(
            company_id=company_id, user=request.user,
            role=CompanyMembership.Role.MANAGER).exists()