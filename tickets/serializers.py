from rest_framework import serializers

from .models import Ticket, Category, Comment, AuditLog


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'company', 'name']
        read_only_fields = ['id', 'company']


class TicketCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = ['id', 'title', 'description', 'category', 'priority', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_category(self, value):
        company_id = self.context['view'].kwargs.get('company_pk')
        if value.company_id != int(company_id):
            raise serializers.ValidationError("هذه الفئة لا تنتمي لهذه الشركة.")
        return value


class TicketDetailSerializer(serializers.ModelSerializer):
    creator_username = serializers.CharField(source='creator.username', read_only=True)
    assigned_agent_username = serializers.CharField(
        source='assigned_agent.username', read_only=True, default=None)
    category_name = serializers.CharField(source='category.name', read_only=True)
    status_name = serializers.CharField(source='status.name', read_only=True)

    class Meta:
        model = Ticket
        fields = [
            'id', 'company', 'creator', 'creator_username', 'title', 'description',
            'category', 'category_name', 'priority', 'status', 'status_name',
            'assigned_agent', 'assigned_agent_username', 'has_left_initial_status',
            'created_at', 'updated_at', 'resolved_at',
        ]
        read_only_fields = fields


class CommentSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'ticket', 'author', 'author_username', 'text', 'type', 'created_at']
        read_only_fields = ['id', 'ticket', 'author', 'created_at']


class AuditLogSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source='actor.username', read_only=True)

    class Meta:
        model = AuditLog
        fields = ['id', 'ticket', 'actor', 'actor_username', 'event_type', 'old_value', 'new_value', 'created_at']
        read_only_fields = ['id', 'ticket', 'actor', 'created_at']