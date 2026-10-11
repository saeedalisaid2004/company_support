from rest_framework import viewsets
from . import services
from .models import Status, WorkflowTransition
from .permissions import StaffReadManagerWrite
from .serializers import StatusSerializer, TransitionSerializer


class StatusViewSet(viewsets.ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
    serializer_class = StatusSerializer
    permission_classes = [StaffReadManagerWrite]

    def get_queryset(self):
        return Status.objects.filter(company_id=self.kwargs['company_pk']).order_by('id')

    def perform_create(self, serializer):
        serializer.instance = services.create_status(
            company_id=int(self.kwargs['company_pk']), **serializer.validated_data)

    def perform_update(self, serializer):
        serializer.instance = services.update_status(
            serializer.instance, **serializer.validated_data)

    def perform_destroy(self, instance):
        services.delete_status(instance)


class TransitionViewSet(viewsets.ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
    serializer_class = TransitionSerializer
    permission_classes = [StaffReadManagerWrite]

    def get_queryset(self):
        return (WorkflowTransition.objects.filter(company_id=self.kwargs['company_pk'])
                .select_related('from_status', 'to_status').order_by('id'))

    def perform_create(self, serializer):
        d = serializer.validated_data
        serializer.instance = services.create_transition(
            company_id=int(self.kwargs['company_pk']),
            from_status=d['from_status'], to_status=d['to_status'],
            allow_agent=d.get('allow_agent', True),
            allow_manager=d.get('allow_manager', True))

    def perform_update(self, serializer):
        inst, d = serializer.instance, serializer.validated_data
        serializer.instance = services.update_transition_roles(
            inst, allow_agent=d.get('allow_agent', inst.allow_agent),
            allow_manager=d.get('allow_manager', inst.allow_manager))