from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404

from .models import Company, CompanyMembership
from .serializers import (
    CompanyCreateSerializer, 
    CompanyMembershipSerializer, 
    AddOrUpdateMemberSerializer
)
from .permissions import IsCompanyManager


class CompanyViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        return CompanyCreateSerializer

    def get_queryset(self):
        return Company.objects.filter(companymembership__user=self.request.user).distinct()

    def perform_create(self, serializer):
        with transaction.atomic():
            company = serializer.save()
            CompanyMembership.objects.create(
                company=company,
                user=self.request.user,
                role=CompanyMembership.Role.MANAGER
            )
    def perform_create(self, serializer):
        company = serializer.save()
        
        CompanyMembership.objects.get_or_create(
            company=company,
            user=self.request.user,
            defaults={'role': CompanyMembership.Role.MANAGER}
        )

    @action(detail=True, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def members(self, request, pk=None):
        company = self.get_object()
        memberships = CompanyMembership.objects.filter(company=company).select_related('user')
        serializer = CompanyMembershipSerializer(memberships, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated, IsCompanyManager], url_path='add-member')
    def add_or_update_member(self, request, pk=None):
        company = self.get_object()
        serializer = AddOrUpdateMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = serializer.validated_data['user_id']
        new_role = serializer.validated_data['role']

        membership = CompanyMembership.objects.filter(company=company, user_id=user_id).first()

        if membership:
            if membership.role == CompanyMembership.Role.MANAGER and new_role != CompanyMembership.Role.MANAGER:
                managers_count = CompanyMembership.objects.filter(
                    company=company, role=CompanyMembership.Role.MANAGER
                ).count()
                if managers_count <= 1:
                    raise ValidationError({"detail": "لا يمكن خفض دور مدير الشركة الأخير."})

            if membership.role == CompanyMembership.Role.AGENT and new_role != CompanyMembership.Role.AGENT:
                has_unresolved_tickets = membership.user.assigned_tickets.filter(
                    company=company, status__is_terminal=False
                ).exists()
                if has_unresolved_tickets:
                    raise ValidationError({"detail": "لا يمكن تغيير دور وكيل لديه تكتات جارية غير منتهية."})

            membership.role = new_role
            membership.save()
            msg = "تم تحديث دور العضو بنجاح."
        else:
            membership = CompanyMembership.objects.create(
                company=company,
                user_id=user_id,
                role=new_role
            )
            msg = "تمت إضافة العضو للشركة بنجاح."

        return Response({"detail": msg, "data": CompanyMembershipSerializer(membership).data}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['delete'], permission_classes=[permissions.IsAuthenticated, IsCompanyManager], url_path=r'remove-member/(?P<user_id>\d+)')
    def remove_member(self, request, pk=None, user_id=None):
        company = self.get_object()
        membership = get_object_or_404(CompanyMembership, company=company, user_id=user_id)

        if membership.role == CompanyMembership.Role.MANAGER:
            managers_count = CompanyMembership.objects.filter(
                company=company, role=CompanyMembership.Role.MANAGER
            ).count()
            if managers_count <= 1:
                raise ValidationError({"detail": "لا يمكن إزالة مدير الشركة الأخير."})

        if membership.role == CompanyMembership.Role.AGENT:
            has_unresolved_tickets = membership.user.assigned_tickets.filter(
                company=company, status__is_terminal=False
            ).exists()
            if has_unresolved_tickets:
                raise ValidationError({"detail": "لا يمكن إزالة وكيل لديه تكتات جارية غير منتهية."})

        membership.delete()
        return Response({"detail": "تمت إزالة العضو من الشركة بنجاح."}, status=status.HTTP_204_NO_CONTENT)