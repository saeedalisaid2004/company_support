from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from workflows.models import Status
from workflows.services import transition_ticket_status_service
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Count, Avg, F, ExpressionWrapper, DurationField

from companies.models import CompanyMembership
from .models import Comment, Ticket, Status, AuditLog
from .serializers import (
    CommentSerializer,
    TicketCreateSerializer, 
    TicketDetailSerializer, 
    AuditLogSerializer
)
from .services import claim_ticket_service, transition_ticket_status_service


class CommentViewSet(viewsets.ModelViewSet):
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        company_id = self.kwargs.get('company_pk')
        ticket_id = self.kwargs.get('ticket_pk')

        membership = get_object_or_404(CompanyMembership, user=user, company_id=company_id)

        queryset = Comment.objects.filter(
            ticket__company_id=company_id,
            ticket_id=ticket_id
        ).select_related('author', 'ticket')

        if membership.role == CompanyMembership.Role.CUSTOMER:
            queryset = queryset.filter(type=Comment.CommentType.PUBLIC)

        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        company_id = self.kwargs.get('company_pk')
        ticket_id = self.kwargs.get('ticket_pk')

        ticket = get_object_or_404(Ticket, id=ticket_id, company_id=company_id)

        if ticket.status.is_terminal:
            raise ValidationError({"detail": "لا يمكن إضافة تعليقات أو ملاحظات على تكت منتهي/مغلق."})

        membership = get_object_or_404(CompanyMembership, user=user, company_id=company_id)

        comment_type = serializer.validated_data.get('type', Comment.CommentType.PUBLIC)
        
        if membership.role == CompanyMembership.Role.CUSTOMER and comment_type == Comment.CommentType.INTERNAL_NOTE:
            raise PermissionDenied("العملاء لا يمكنهم إنشاء ملاحظات داخلية.")

        if membership.role == CompanyMembership.Role.AGENT and ticket.assigned_agent != user:
            raise PermissionDenied("يجب حجز التكت أولاً قبل إضافة تعليق أو ملاحظة.")

        serializer.save(author=user, ticket=ticket)


class TicketViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'priority', 'category', 'assigned_agent']
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'updated_at', 'priority']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return TicketCreateSerializer
        return TicketDetailSerializer

    def get_queryset(self):
        user = self.request.user
        company_id = self.kwargs.get('company_pk')
        
        membership = get_object_or_404(CompanyMembership, user=user, company_id=company_id)

        if membership.role == CompanyMembership.Role.CUSTOMER:
            return Ticket.objects.filter(
                company_id=company_id, 
                creator=user
            ).select_related('category', 'status', 'creator', 'assigned_agent')
        
        elif membership.role == CompanyMembership.Role.AGENT:
            return Ticket.objects.filter(company_id=company_id).filter(
                assigned_agent__isnull=True
            ) | Ticket.objects.filter(company_id=company_id, assigned_agent=user)
        
        return Ticket.objects.filter(company_id=company_id).select_related(
            'category', 'status', 'creator', 'assigned_agent'
        )

    def perform_create(self, serializer):
        user = self.request.user
        company_id = self.kwargs.get('company_pk')
        membership = get_object_or_404(CompanyMembership, user=user, company_id=company_id)

        if membership.role != CompanyMembership.Role.CUSTOMER:
            raise PermissionDenied("العملاء فقط هم من يمكنهم إنشاء التكتات.")

        initial_status = Status.objects.filter(company_id=company_id, is_initial=True).first()
        if not initial_status:
            raise ValidationError({"detail": "لا توجد حالة ابتدائية (Initial Status) معرفة لهذه الشركة."})

        with transaction.atomic():
            ticket = serializer.save(
                creator=user, 
                company_id=company_id, 
                status=initial_status
            )
            
            AuditLog.objects.create(
                ticket=ticket,
                actor=user,
                event_type=AuditLog.EventType.CREATED,
                new_value={"status": initial_status.name, "priority": ticket.priority}
            )

    @action(detail=True, methods=['post'], url_path='claim')
    def claim(self, request, company_pk=None, pk=None):
        membership = get_object_or_404(CompanyMembership, user=request.user, company_id=company_pk)
        if membership.role != CompanyMembership.Role.AGENT:
            raise PermissionDenied("الوكلاء (Agents) فقط هم من يمكنهم حجز التكتات.")

        ticket = claim_ticket_service(ticket_id=pk, agent_user=request.user)
        return Response(TicketDetailSerializer(ticket).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='change-status')
    def change_status(self, request, company_pk=None, pk=None):
        target_status_id = request.data.get('status_id')
        if not target_status_id:
            raise ValidationError({"status_id": "هذا الحقل مطلوب."})

        target_status = get_object_or_404(Status, id=target_status_id, company_id=company_pk)
        ticket = transition_ticket_status_service(
            ticket_id=pk, 
            user=request.user, 
            target_status=target_status
        )
        return Response(TicketDetailSerializer(ticket).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='history')
    def history(self, request, company_pk=None, pk=None):
        ticket = self.get_object()
        logs = ticket.audit_logs.all().select_related('actor')
        return Response(AuditLogSerializer(logs, many=True).data)

    @action(detail=False, methods=['get'], url_path='reports')
    def reports(self, request, company_pk=None):
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