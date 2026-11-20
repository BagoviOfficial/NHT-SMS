from rest_framework import serializers
from .models import (
    SystemConfiguration,
    ConfigurationHistory,
    IntegrationHealthLog,
    ConfigCategory,
    ConfigDataType,
)
from .crypto import CryptoService
from .services import ConfigurationService


class SystemConfigurationSerializer(serializers.ModelSerializer):
    """
    Serializer for SystemConfiguration. Automatically masks secret values.
    """
    display_value = serializers.SerializerMethodField()
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    data_type_display = serializers.CharField(source='get_data_type_display', read_only=True)
    updated_by_username = serializers.CharField(source='updated_by.username', read_only=True, default='SYSTEM')

    class Meta:
        model = SystemConfiguration
        fields = [
            'id',
            'key',
            'category',
            'category_display',
            'data_type',
            'data_type_display',
            'display_value',
            'default_value',
            'is_secret',
            'is_system_locked',
            'requires_restart',
            'requires_approval',
            'title',
            'description',
            'validation_regex',
            'choices_json',
            'version',
            'updated_by_username',
            'updated_at',
        ]
        read_only_fields = ['id', 'version', 'updated_at']

    def get_display_value(self, obj):
        if obj.is_secret:
            return CryptoService.mask_secret(obj.raw_value)
        return ConfigurationService._cast_value(obj.raw_value, obj.data_type, is_secret=False)


class SystemConfigurationUpdateSerializer(serializers.Serializer):
    key = serializers.CharField(max_length=100)
    value = serializers.CharField(allow_blank=True)
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    expected_version = serializers.IntegerField(required=False, default=None, allow_null=True)
    confirm_critical = serializers.BooleanField(required=False, default=False)


class ConfigurationImpactAssessmentSerializer(serializers.Serializer):
    key = serializers.CharField(max_length=100)
    proposed_value = serializers.CharField(allow_blank=True, default='')


class ConfigurationRollbackSerializer(serializers.Serializer):
    key = serializers.CharField(max_length=100)
    target_version = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')


class ConnectionTestSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=[
        'daraja',
        'africastalking',
        'whatsapp',
        'smtp',
        'postgresql',
        'redis',
        'celery',
        'all'
    ])


class ConfigurationHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfigurationHistory
        fields = [
            'id',
            'version',
            'old_value',
            'new_value',
            'changed_by_username',
            'ip_address',
            'reason',
            'timestamp',
        ]
        read_only_fields = fields


class IntegrationHealthLogSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = IntegrationHealthLog
        fields = [
            'id',
            'service_name',
            'status',
            'status_display',
            'response_time_ms',
            'details',
            'error_message',
            'tested_at',
        ]
        read_only_fields = fields
