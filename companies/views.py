from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from . import services
from .models import Company, CompanyMembership
from .permissions import IsCompanyManager
from .serializers import (
    AddMemberSerializer, ChangeRoleSerializer,
    CompanyCreateSerializer, CompanyMembershipSerializer,
)


class CompanyViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                     mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = CompanyCreateSerializer
    permission_classes = [permissions.IsAuthenticated]
    company_lookup_kwarg = 'pk'

    def get_queryset(self):
        return Company.objects.filter(memberships__user=self.request.user).order_by('id')

    @action(detail=True, methods=['get'])
    def members(self, request, pk=None):
        company = self.get_object()
        mine = CompanyMembership.objects.get(company=company, user=request.user)
        if mine.role == CompanyMembership.Role.CUSTOMER:
            raise PermissionDenied("قائمة الأعضاء للموظفين فقط.")
        qs = company.memberships.select_related('user').order_by('id')
        return Response(CompanyMembershipSerializer(qs, many=True).data)

    @action(detail=True, methods=['post'], url_path='add-member',
            permission_classes=[permissions.IsAuthenticated, IsCompanyManager])
    def add_member(self, request, pk=None):
        company = self.get_object()
        s = AddMemberSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        m = services.add_member(company_id=company.pk, **s.validated_data)
        return Response(CompanyMembershipSerializer(m).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['patch'], url_path=r'change-role/(?P<user_id>\d+)',
            permission_classes=[permissions.IsAuthenticated, IsCompanyManager])
    def change_role(self, request, pk=None, user_id=None):
        company = self.get_object()
        s = ChangeRoleSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        m = services.change_role(company_id=company.pk, user_id=int(user_id),
                                 new_role=s.validated_data['role'])
        return Response(CompanyMembershipSerializer(m).data)

    @action(detail=True, methods=['delete'], url_path=r'remove-member/(?P<user_id>\d+)',
            permission_classes=[permissions.IsAuthenticated, IsCompanyManager])
    def remove_member(self, request, pk=None, user_id=None):
        company = self.get_object()
        services.remove_member(company_id=company.pk, user_id=int(user_id))
        return Response(status=status.HTTP_204_NO_CONTENT)