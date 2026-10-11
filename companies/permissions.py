from rest_framework import permissions
from .models import CompanyMembership

class IsCompanyManager(permissions.BasePermission):
    """
    يتأكد من أن المستخدم الحالي يحمل دور MANAGER في الشركة المحددة.
    
    """
    def has_permission(self, request, view):
        company_id = view.kwargs.get('company_pk') or view.kwargs.get('pk')
        if not company_id or not request.user.is_authenticated:
            return False

        return CompanyMembership.objects.filter(
            company_id=company_id,
            user=request.user,
            role=CompanyMembership.Role.MANAGER
        ).exists()