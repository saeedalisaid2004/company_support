from rest_framework import serializers
from .models import Status, WorkflowTransition


class StatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Status
        fields = ['id', 'company', 'name', 'is_initial', 'is_terminal']
        read_only_fields = ['id', 'company']
        extra_kwargs = {'name': {'validators': []}}   


class TransitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowTransition
        fields = ['id', 'from_status', 'to_status', 'allow_agent', 'allow_manager']
        read_only_fields = ['id']
        validators = []     