from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db import transaction
from .models import Company, CompanyMembership

User = get_user_model()

class CompanyMembershipSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = CompanyMembership
        fields = ['id', 'user', 'username', 'email', 'role']
        read_only_fields = ['id']

class CompanyCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ['id', 'name', 'created_at']
        read_only_fields = ['id', 'created_at']

    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user
       
        with transaction.atomic():
            company = Company.objects.create(**validated_data)
            CompanyMembership.objects.create(
                user=user,
                company=company,
                role=CompanyMembership.Role.MANAGER
            )
        return company

class AddOrUpdateMemberSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    role = serializers.ChoiceField(choices=CompanyMembership.Role.choices)

    def validate_user_id(self, value):
        if not User.objects.filter(id=value).exists():
            raise serializers.ValidationError("المستخدم غير موجود.")
        return value