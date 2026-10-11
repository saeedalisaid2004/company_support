from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, DurationField, F, ProtectedError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from companies.models import CompanyMembership
from workflows.models import Status
from .filters import TicketFilter
from .models import AuditLog, Category, Comment, Ticket
from .permissions import MemberReadManagerWrite
from .selectors import (
    accessible_tickets, get_accessible_ticket, get_membership, is_staff,
)
from .serializers import (
    AuditLogSerializer, CategorySerializer, CommentSerializer,
    TicketCreateSerializer, TicketDetailSerializer,
)
from .services import (
    Conflict, assign_ticket_service, claim_ticket_service,
    transition_ticket_status_service,
)

Role = CompanyMembership.Role


def _lock_ticket(ticket_id):
    """يقفل صف التذكرة (لازم تتندهي جوه transaction.atomic)."""
    return (Ticket.objects.select_for_update(of=('self',))
            .select_related('status').get(pk=ticket_id))


# ======================= Categories =======================
class CategoryViewSet(viewsets.ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
    serializer_class = CategorySerializer
    permission_classes = [MemberReadManagerWrite]

    def get_queryset(self):
        return Category.objects.filter(
            company_id=self.kwargs['company_pk']).order_by('name', 'id')

    def _name_taken(self, name, exclude_pk=None):
        qs = Category.objects.filter(
            company_id=self.kwargs['company_pk'], name__iexact=name)
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        return qs.exists()

    def perform_create(self, serializer):
        if self._name_taken(serializer.validated_data['name']):
            raise Conflict("اسم الفئة مستخدم بالفعل في هذه الشركة.")
        try:
            with transaction.atomic():
                serializer.save(company_id=int(self.kwargs['company_pk']))
        except IntegrityError:          
            raise Conflict("اسم الفئة مستخدم بالفعل في هذه الشركة.")

    def perform_update(self, serializer):
        name = serializer.validated_data.get('name')
        if name and self._name_taken(name, serializer.instance.pk):
            raise Conflict("اسم الفئة مستخدم بالفعل في هذه الشركة.")
        try:
            with transaction.atomic():
                serializer.save()
        except IntegrityError:
            raise Conflict("اسم الفئة مستخدم بالفعل في هذه الشركة.")

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError:         
            raise Conflict("لا يمكن حذف فئة مستخدمة في تكتات.")


# ======================= Comments =======================
class CommentViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                     mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]

    @property
    def membership(self):
        if not hasattr(self, '_membership'):
            self._membership = get_membership(
                self.request.user, self.kwargs['company_pk'])
        return self._membership

    def get_queryset(self):
        ticket = get_accessible_ticket(
            self.request.user, self.membership, self.kwargs['ticket_pk'])
        qs = ticket.comments.select_related('author')
        if not is_staff(self.membership):
            qs = qs.filter(type=Comment.CommentType.PUBLIC)
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        membership = self.membership
        ticket = get_accessible_ticket(user, membership, self.kwargs['ticket_pk'])
        comment_type = serializer.validated_data.get('type', Comment.CommentType.PUBLIC)

        if membership.role == Role.CUSTOMER and comment_type == Comment.CommentType.INTERNAL_NOTE:
            raise PermissionDenied("العملاء لا يمكنهم إنشاء ملاحظات داخلية.")
        if membership.role == Role.AGENT and ticket.assigned_agent_id != user.id:
            raise PermissionDenied("يجب حجز التكت أولاً قبل إضافة تعليق أو ملاحظة.")

        with transaction.atomic():
            locked = _lock_ticket(ticket.pk)
            if locked.status.is_terminal:
                raise ValidationError({"detail": "لا يمكن إضافة تعليقات على تكت منتهي."})
            serializer.save(author=user, ticket=locked)


# ======================= Tickets =======================
class TicketViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                    mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                    viewsets.GenericViewSet):
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    permission_classes = [permissions.IsAuthenticated]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = TicketFilter
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

    @property
    def membership(self):
        if not hasattr(self, '_membership'):
            self._membership = get_membership(
                self.request.user, self.kwargs['company_pk'])
        return self._membership

    def get_serializer_class(self):
        if self.action in ['create', 'partial_update']:
            return TicketCreateSerializer
        return TicketDetailSerializer

    def get_queryset(self):
        return accessible_tickets(self.request.user, self.membership)

    def filter_queryset(self, queryset):
        qs = super().filter_queryset(queryset)
        return qs.order_by(*qs.query.order_by, 'id')

    # ---------- create ----------
    def perform_create(self, serializer):
        user = self.request.user
        company_id = self.kwargs['company_pk']

        if self.membership.role != Role.CUSTOMER:
            raise PermissionDenied("العملاء فقط هم من يمكنهم إنشاء التكتات.")

        initial_status = Status.objects.filter(
            company_id=company_id, is_initial=True).first()
        if not initial_status:
            raise ValidationError({"detail": "لا توجد حالة ابتدائية لهذه الشركة."})

        with transaction.atomic():
            ticket = serializer.save(
                creator=user, company_id=company_id, status=initial_status)
            AuditLog.objects.create(
                ticket=ticket, actor=user,
                event_type=AuditLog.EventType.CREATED,
                new_value={"status": initial_status.name,
                           "priority": ticket.priority},
            )

    # ---------- update (PATCH) ----------
    def perform_update(self, serializer):
        user = self.request.user
        role = self.membership.role
        data = serializer.validated_data
        content_fields = {'title', 'description', 'category'}

        with transaction.atomic():
            ticket = _lock_ticket(serializer.instance.pk)

            if ticket.status.is_terminal:
                raise ValidationError({"detail": "لا يمكن تعديل تكت منتهي."})

            if role == Role.CUSTOMER:
                if 'priority' in data:
                    raise PermissionDenied("العميل لا يستطيع تغيير الأولوية.")
                if ticket.has_left_initial_status:
                    raise PermissionDenied("لا يمكن التعديل بعد خروج التكت من الحالة الابتدائية.")
            else:
                if role == Role.AGENT and ticket.assigned_agent_id != user.id:
                    raise PermissionDenied("يمكنك تعديل التكتات المسندة إليك فقط.")
                if content_fields & data.keys():
                    raise PermissionDenied("الموظفون لا يعدّلون محتوى التكت.")

            old_priority = ticket.priority
            serializer.instance = ticket          
            ticket = serializer.save()

            if ticket.priority != old_priority:
                AuditLog.objects.create(
                    ticket=ticket, actor=user,
                    event_type=AuditLog.EventType.PRIORITY_CHANGE,
                    old_value={"priority": old_priority},
                    new_value={"priority": ticket.priority},
                )

    # ---------- claim (agent) ----------
    @action(detail=True, methods=['post'], url_path='claim')
    def claim(self, request, company_pk=None, pk=None):
        if self.membership.role != Role.AGENT:
            raise PermissionDenied("الوكلاء فقط هم من يمكنهم حجز التكتات.")
        ticket = claim_ticket_service(
            company_id=company_pk, ticket_id=pk, agent_user=request.user)
        return Response(TicketDetailSerializer(ticket).data)

    # ---------- assign / reassign (manager) ----------
    @action(detail=True, methods=['post'], url_path='assign')
    def assign(self, request, company_pk=None, pk=None):
        if self.membership.role != Role.MANAGER:
            raise PermissionDenied("المانجر فقط يستطيع إسناد التكتات.")
        try:
            agent_id = int(request.data.get('agent_id'))
        except (TypeError, ValueError):
            raise ValidationError({"agent_id": "قيمة صحيحة مطلوبة."})
        ticket = assign_ticket_service(
            company_id=company_pk, ticket_id=pk,
            actor=request.user, agent_id=agent_id)
        return Response(TicketDetailSerializer(ticket).data)

    # ---------- change status ----------
    @action(detail=True, methods=['post'], url_path='change-status')
    def change_status(self, request, company_pk=None, pk=None):
        status_id = request.data.get('status_id')
        if not status_id:
            raise ValidationError({"status_id": "هذا الحقل مطلوب."})
        ticket = transition_ticket_status_service(
            company_id=company_pk, ticket_id=pk, user=request.user,
            role=self.membership.role, target_status_id=status_id,
            expected_status_id=request.data.get('expected_status_id'),
        )
        return Response(TicketDetailSerializer(ticket).data)

    # ---------- history (staff only) ----------
    @action(detail=True, methods=['get'], url_path='history')
    def history(self, request, company_pk=None, pk=None):
        if not is_staff(self.membership):
            raise PermissionDenied("السجل متاح للموظفين فقط.")
        ticket = self.get_object()
        logs = ticket.audit_logs.select_related('actor')
        return Response(AuditLogSerializer(logs, many=True).data)

    # ---------- reports ----------
    @action(detail=False, methods=['get'], url_path='reports')
    def reports(self, request, company_pk=None):
        qs = accessible_tickets(request.user, self.membership).order_by()

        by_status = list(qs.values('status__name')
                           .annotate(count=Count('id')).order_by('status__name'))
        by_priority = list(qs.values('priority')
                             .annotate(count=Count('id')).order_by('priority'))
        unassigned = qs.filter(assigned_agent__isnull=True).count()

        avg = qs.filter(status__is_terminal=True, resolved_at__isnull=False).aggregate(
            avg=Avg(F('resolved_at') - F('created_at'), output_field=DurationField())
        )['avg']

        return Response({
            "by_status": by_status,
            "by_priority": by_priority,
            "unassigned_count": unassigned,
            "avg_resolution_seconds": avg.total_seconds() if avg is not None else None,
        })