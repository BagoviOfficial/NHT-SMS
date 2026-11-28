from rest_framework import serializers
from .models import (
    SystemConfiguration,
    ConfigurationHistory,
    ConfigurationChangeRequest,
    IntegrationHealthLog,
    ConfigCategory,
    ConfigDataType,
    CompanyProfile,
    BrandingVersion,
    NumberSequence,
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


class ConfigurationChangeRequestSerializer(serializers.ModelSerializer):
    setting_key = serializers.CharField(source='setting.key', read_only=True)
    setting_title = serializers.CharField(source='setting.title', read_only=True)
    requested_by_username = serializers.CharField(source='requested_by.username', read_only=True)
    reviewed_by_username = serializers.CharField(source='reviewed_by.username', read_only=True, default='')
    proposed_display = serializers.SerializerMethodField()

    class Meta:
        model = ConfigurationChangeRequest
        fields = [
            'id',
            'setting',
            'setting_key',
            'setting_title',
            'current_value',
            'proposed_display',
            'status',
            'risk_level',
            'impact_assessment',
            'justification',
            'requested_by',
            'requested_by_username',
            'reviewed_by',
            'reviewed_by_username',
            'review_comments',
            'requested_at',
            'reviewed_at',
            'applied_at',
        ]
        read_only_fields = fields

    def get_proposed_display(self, obj):
        if obj.setting.is_secret:
            return CryptoService.mask_secret(obj.proposed_value)
        return obj.proposed_value


class ConfigurationChangeRequestCreateSerializer(serializers.Serializer):
    key = serializers.CharField(max_length=100)
    proposed_value = serializers.CharField(allow_blank=True)
    justification = serializers.CharField(max_length=500, required=False, allow_blank=True, default='')


class ConfigurationChangeReviewSerializer(serializers.Serializer):
    comments = serializers.CharField(max_length=500, required=False, allow_blank=True, default='')


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


class BrandingVersionSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, default='SYSTEM')
    has_logo = serializers.SerializerMethodField()
    logo_asset_url = serializers.SerializerMethodField()

    class Meta:
        model = BrandingVersion
        fields = [
            'id',
            'version_number',
            'profile_snapshot',
            'logo_sha256',
            'has_logo',
            'logo_asset_url',
            'change_notes',
            'created_by_username',
            'created_at',
        ]
        read_only_fields = fields

    def get_has_logo(self, obj):
        return bool(obj.logo_archive and obj.logo_archive.name)

    def get_logo_asset_url(self, obj):
        if obj.logo_archive and obj.logo_archive.name:
            return f"/settings/api/v1/company-profile/logo-asset/?version={obj.version_number}"
        return ''


class CompanyProfileSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()
    monochrome_logo_url = serializers.SerializerMethodField()
    updated_by_username = serializers.CharField(source='updated_by.username', read_only=True, default='SYSTEM')

    class Meta:
        model = CompanyProfile
        fields = [
            'id',
            'legal_name',
            'trading_name',
            'short_name',
            'registration_number',
            'tax_pin',
            'physical_address',
            'postal_address',
            'phone_numbers',
            'official_email',
            'website',
            'public_base_url',
            'footer_text',
            'primary_color',
            'secondary_color',
            'logo',
            'monochrome_logo',
            'logo_url',
            'monochrome_logo_url',
            'current_version',
            'updated_by_username',
            'updated_at',
        ]
        read_only_fields = ['id', 'current_version', 'logo_url', 'monochrome_logo_url', 'updated_by_username', 'updated_at']

    def get_logo_url(self, obj):
        if obj.logo and obj.logo.name:
            return f"/settings/api/v1/company-profile/logo-asset/?v={obj.current_version}"
        return ''

    def get_monochrome_logo_url(self, obj):
        if obj.monochrome_logo and obj.monochrome_logo.name:
            return f"/settings/api/v1/company-profile/logo-asset/?type=monochrome&v={obj.current_version}"
        return ''


class NumberSequenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NumberSequence
        fields = ['id', 'prefix', 'year', 'last_number', 'updated_at']
        read_only_fields = fields
