from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.db.models import Count, Avg, F, ExpressionWrapper, DurationField

from companies.models import CompanyMembership
from tickets.models import Ticket

class CompanyReportsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, company_pk=None):
        membership = get_object_or_404(CompanyMembership, user=request.user, company_id=company_pk)
        
        if membership.role == CompanyMembership.Role.CUSTOMER:
            raise PermissionDenied("لا تملك الصلاحية للوصول لتقارير الشركة.")

        queryset = Ticket.objects.filter(company_id=company_pk)

        total_tickets = queryset.count()
        open_tickets = queryset.filter(status__is_terminal=False).count()
        closed_tickets = queryset.filter(status__is_terminal=True).count()

        resolved_tickets = queryset.filter(
            status__is_terminal=True, 
            resolved_at__isnull=False
        ).annotate(
            resolution_time=ExpressionWrapper(
                F('resolved_at') - F('created_at'),
                output_field=DurationField()
            )
        )
        
        avg_resolution = resolved_tickets.aggregate(avg_time=Avg('resolution_time'))['avg_time']
        avg_resolution_seconds = avg_resolution.total_seconds() if avg_resolution else 0

        status_breakdown = list(
            queryset.values('status__name')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

        return Response({
            "total_tickets": total_tickets,
            "open_tickets": open_tickets,
            "closed_tickets": closed_tickets,
            "avg_resolution_time_seconds": round(avg_resolution_seconds, 2),
            "status_breakdown": status_breakdown
        }, status=status.HTTP_200_OK)