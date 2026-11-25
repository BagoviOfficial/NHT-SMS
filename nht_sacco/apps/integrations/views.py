import json
from django.shortcuts import render, redirect
from django.views import View
from django.views.generic import TemplateView
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.utils import timezone
from django.core.exceptions import ValidationError

from rest_framework import views, viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import (
    SystemConfiguration,
    ConfigurationHistory,
    ConfigurationChangeRequest,
    IntegrationHealthLog,
    ConfigCategory,
    ConfigDataType,
    CompanyProfile,
    BrandingVersion,
)
from .crypto import CryptoService
from .services import ConfigurationService
from .diagnostics import DiagnosticService
from .permissions import (
    IsSystemAdminUser,
    IsAuditorOrSystemAdmin,
    SystemAdminRequiredMixin,
    AuditorOrAdminRequiredMixin,
)
from .serializers import (
    SystemConfigurationSerializer,
    SystemConfigurationUpdateSerializer,
    ConfigurationRollbackSerializer,
    ConfigurationHistorySerializer,
    IntegrationHealthLogSerializer,
    ConnectionTestSerializer,
    ConfigurationImpactAssessmentSerializer,
    ConfigurationChangeRequestSerializer,
    ConfigurationChangeRequestCreateSerializer,
    ConfigurationChangeReviewSerializer,
    CompanyProfileSerializer,
    BrandingVersionSerializer,
)


# ==============================================================================
# Web Administration Portal Views
# ==============================================================================

class SystemSettingsView(AuditorOrAdminRequiredMixin, TemplateView):
    """
    Main Administration & Configuration Centre Web Portal.
    Presents categorized settings, secrets masking, rollback timeline, and live diagnostics.
    """
    template_name = 'admin/settings/settings_index.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        all_configs = SystemConfiguration.objects.all().order_by('category', 'key')
        
        # Prepare masked/display values for each item
        configs_by_cat = {
            ConfigCategory.INTEGRATIONS: [],
            ConfigCategory.BUSINESS: [],
            ConfigCategory.APPLICATION: [],
            ConfigCategory.SECURITY: [],
            ConfigCategory.SYSTEM: [],
        }

        for c in all_configs:
            if c.is_secret:
                c.display_val = CryptoService.mask_secret(c.raw_value)
            else:
                c.display_val = ConfigurationService._cast_value(c.raw_value, c.data_type, is_secret=False)
            
            cat_list = configs_by_cat.get(c.category)
            if cat_list is not None:
                cat_list.append(c)

        ctx['configs_by_cat'] = configs_by_cat
        ctx['categories'] = ConfigCategory.choices
        ctx['active_tab'] = self.request.GET.get('tab', 'INTEGRATIONS')
        ctx['history_logs'] = ConfigurationHistory.objects.all().select_related('setting').order_by('-timestamp')[:20]
        ctx['health_logs'] = IntegrationHealthLog.objects.all().order_by('-tested_at')[:10]
        ctx['is_auditor_only'] = getattr(self.request.user, 'role', None) == 'AUDITOR' and not self.request.user.is_superuser
        return ctx


class SystemSettingsUpdateView(SystemAdminRequiredMixin, View):
    """
    Handles bulk/single setting updates posted from the administration web tabs.
    """
    def post(self, request, *args, **kwargs):
        tab = request.POST.get('tab', 'INTEGRATIONS')
        ip_addr = request.META.get('REMOTE_ADDR')
        updated = 0
        errors = []

        # Find all keys submitted in the form
        for key, val in request.POST.items():
            if key in ('csrfmiddlewaretoken', 'tab', 'form_reason'):
                continue
            
            setting = SystemConfiguration.objects.filter(key=key).first()
            if not setting:
                continue

            # If user didn't change masked secret, leave unchanged
            if setting.is_secret and str(val).startswith('••••••••'):
                continue

            try:
                confirm_crit = request.POST.get('confirm_critical') in ('true', '1', 'on')
                ConfigurationService.set(
                    key=key,
                    value=val,
                    user=request.user,
                    reason=request.POST.get('form_reason', 'Settings Web Update'),
                    ip_address=ip_addr,
                    confirm_critical=confirm_crit
                )
                updated += 1
            except ValidationError as ve:
                errors.append(f"{setting.title}: {str(ve)}")
            except Exception as e:
                errors.append(f"{setting.title}: {str(e)}")

        if errors:
            messages.error(request, "Some settings could not be updated: " + " | ".join(errors))
        elif updated > 0:
            messages.success(request, f"Successfully updated {updated} configuration parameter(s).")
        else:
            messages.info(request, "No configuration changes detected.")

        return redirect(f"/settings/?tab={tab}")


class SystemSettingsRollbackView(SystemAdminRequiredMixin, View):
    """
    Web endpoint to revert a configuration setting to a specified version.
    """
    def post(self, request, *args, **kwargs):
        key = request.POST.get('key')
        target_version = request.POST.get('target_version')
        reason = request.POST.get('reason', 'Administrative Rollback')
        ip_addr = request.META.get('REMOTE_ADDR')

        try:
            target_v = int(target_version)
            ConfigurationService.rollback(
                key=key,
                target_version=target_v,
                user=request.user,
                reason=reason,
                ip_address=ip_addr
            )
            messages.success(request, f"Setting '{key}' successfully rolled back to version {target_v}.")
        except Exception as e:
            messages.error(request, f"Failed to rollback '{key}': {str(e)}")

        return redirect('/settings/?tab=HISTORY')


class SystemSettingsExportView(AuditorOrAdminRequiredMixin, View):
    """
    Downloads validated JSON archive of non-secret configurations.
    """
    def get(self, request, *args, **kwargs):
        payload = ConfigurationService.export_configurations(include_secrets=False)
        ts = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f"nht_sms_config_export_{ts}.json"
        
        response = HttpResponse(
            json.dumps(payload, indent=2),
            content_type='application/json'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class SystemSettingsImportView(SystemAdminRequiredMixin, View):
    """
    Imports configuration JSON file uploaded by administrator.
    """
    def post(self, request, *args, **kwargs):
        config_file = request.FILES.get('config_file')
        if not config_file:
            messages.error(request, "Please choose a valid JSON configuration file to import.")
            return redirect('/settings/?tab=BACKUP')

        try:
            content = config_file.read().decode('utf-8')
            data = json.loads(content)
            result = ConfigurationService.import_configurations(
                payload=data,
                user=request.user,
                ip_address=request.META.get('REMOTE_ADDR')
            )
            messages.success(request, f"Import complete: {result['updated']} updated, {result['skipped']} skipped.")
        except Exception as e:
            messages.error(request, f"Failed to import configuration file: {str(e)}")

        return redirect('/settings/?tab=BACKUP')


class ProviderConnectionTestView(AuditorOrAdminRequiredMixin, View):
    """
    AJAX endpoint: tests connectivity to a specific external provider.
    """
    def post(self, request, *args, **kwargs):
        provider = request.POST.get('provider', '').lower()
        if provider == 'daraja':
            res = DiagnosticService.check_daraja()
        elif provider == 'africastalking':
            res = DiagnosticService.check_africastalking()
        elif provider == 'whatsapp':
            res = DiagnosticService.check_whatsapp()
        elif provider == 'smtp':
            res = DiagnosticService.check_smtp()
        elif provider == 'postgresql':
            res = DiagnosticService.check_database()
        elif provider == 'redis':
            res = DiagnosticService.check_redis()
        elif provider == 'celery':
            res = DiagnosticService.check_celery()
        elif provider == 'all':
            res = DiagnosticService.run_all_diagnostics(user=request.user)
        else:
            return JsonResponse({'status': 'error', 'message': f"Unknown provider '{provider}'"}, status=400)

        return JsonResponse(res)


# ==============================================================================
# REST API Endpoints (DRF)
# ==============================================================================

class ConfigurationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint: View system configurations (secrets automatically masked).
    """
    queryset = SystemConfiguration.objects.all().order_by('category', 'key')
    serializer_class = SystemConfigurationSerializer
    permission_classes = [IsAuditorOrSystemAdmin]
    filterset_fields = ['category', 'is_secret', 'data_type']
    search_fields = ['key', 'title', 'description']


class ConfigurationUpdateAPIView(views.APIView):
    """
    API endpoint: Update a single configuration item.
    Supports optimistic locking (expected_version) and critical change confirmation.
    """
    permission_classes = [IsSystemAdminUser]

    def post(self, request, *args, **kwargs):
        serializer = SystemConfigurationUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            config = ConfigurationService.set(
                key=data['key'],
                value=data['value'],
                user=request.user,
                reason=data.get('reason', 'API Update'),
                ip_address=request.META.get('REMOTE_ADDR'),
                expected_version=data.get('expected_version'),
                confirm_critical=data.get('confirm_critical', False),
                enforce_approval=True
            )
            return Response(SystemConfigurationSerializer(config).data, status=status.HTTP_200_OK)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': f"Internal update failure: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ConfigurationImpactAssessmentAPIView(views.APIView):
    """
    API endpoint: Assess operational dependency risk and consequences of a proposed configuration change.
    """
    permission_classes = [IsAuditorOrSystemAdmin]

    def post(self, request, *args, **kwargs):
        serializer = ConfigurationImpactAssessmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        key = serializer.validated_data['key']
        proposed_value = serializer.validated_data['proposed_value']

        from .dependencies import ConfigurationDependencyRegistry
        impact = ConfigurationDependencyRegistry.assess_impact(key, proposed_value)
        return Response(impact, status=status.HTTP_200_OK)


class ConfigurationRollbackAPIView(views.APIView):
    """
    API endpoint: Rollback a configuration setting to a specified version.
    """
    permission_classes = [IsSystemAdminUser]

    def post(self, request, *args, **kwargs):
        serializer = ConfigurationRollbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            config = ConfigurationService.rollback(
                key=data['key'],
                target_version=data['target_version'],
                user=request.user,
                reason=data.get('reason', 'API Rollback'),
                ip_address=request.META.get('REMOTE_ADDR')
            )
            return Response(SystemConfigurationSerializer(config).data, status=status.HTTP_200_OK)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ConfigurationExportAPIView(views.APIView):
    """
    API endpoint: Export non-secret configurations as JSON archive.
    """
    permission_classes = [IsAuditorOrSystemAdmin]

    def get(self, request, *args, **kwargs):
        category = request.query_params.get('category')
        payload = ConfigurationService.export_configurations(category=category, include_secrets=False)
        return Response(payload, status=status.HTTP_200_OK)


class ConfigurationImportAPIView(views.APIView):
    """
    API endpoint: Import configurations from JSON archive.
    """
    permission_classes = [IsSystemAdminUser]

    def post(self, request, *args, **kwargs):
        payload = request.data
        if not isinstance(payload, dict):
            return Response({'error': 'Payload must be a JSON object.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            res = ConfigurationService.import_configurations(
                payload=payload,
                user=request.user,
                ip_address=request.META.get('REMOTE_ADDR')
            )
            return Response(res, status=status.HTTP_200_OK)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SystemHealthAPIView(views.APIView):
    """
    API endpoint: Run and retrieve real-time diagnostic health check results.
    """
    permission_classes = [IsAuditorOrSystemAdmin]

    def get(self, request, *args, **kwargs):
        results = DiagnosticService.run_all_diagnostics(user=request.user)
        return Response(results, status=status.HTTP_200_OK)


class ProviderTestAPIView(views.APIView):
    """
    API endpoint: Test connectivity for a specific external integration provider.
    """
    permission_classes = [IsAuditorOrSystemAdmin]

    def post(self, request, *args, **kwargs):
        serializer = ConnectionTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        provider = serializer.validated_data['provider']

        if provider == 'daraja':
            res = DiagnosticService.check_daraja()
        elif provider == 'africastalking':
            res = DiagnosticService.check_africastalking()
        elif provider == 'whatsapp':
            res = DiagnosticService.check_whatsapp()
        elif provider == 'smtp':
            res = DiagnosticService.check_smtp()
        elif provider == 'postgresql':
            res = DiagnosticService.check_database()
        elif provider == 'redis':
            res = DiagnosticService.check_redis()
        elif provider == 'celery':
            res = DiagnosticService.check_celery()
        elif provider == 'all':
            res = DiagnosticService.run_all_diagnostics(user=request.user)

        return Response(res, status=status.HTTP_200_OK)


class ConfigurationChangeRequestViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Maker-Checker workflow API for high-risk ConfigurationChangeRequest records.
    """
    queryset = ConfigurationChangeRequest.objects.select_related(
        'setting', 'requested_by', 'reviewed_by'
    ).order_by('-requested_at')
    serializer_class = ConfigurationChangeRequestSerializer
    permission_classes = [IsAuditorOrSystemAdmin]
    filterset_fields = ['status', 'risk_level']

    def get_permissions(self):
        if self.request.method in ('GET', 'HEAD', 'OPTIONS'):
            return [IsAuditorOrSystemAdmin()]
        from rest_framework.permissions import IsAuthenticated
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        from nht_sacco.apps.accounts.models import UserRole
        if not (request.user.is_superuser or getattr(request.user, 'role', None) in (UserRole.SUPER_ADMIN, UserRole.CHAIRMAN)):
            return Response({'error': 'Only Super Admin or Chairman may submit configuration change requests.'}, status=status.HTTP_403_FORBIDDEN)
        ser = ConfigurationChangeRequestCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            cr = ConfigurationService.request_configuration_change(
                key=ser.validated_data['key'],
                proposed_value=ser.validated_data['proposed_value'],
                user=request.user,
                justification=ser.validated_data.get('justification', ''),
            )
            return Response(ConfigurationChangeRequestSerializer(cr).data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        from nht_sacco.apps.accounts.models import UserRole
        if not (request.user.is_superuser or getattr(request.user, 'role', None) in (UserRole.SUPER_ADMIN, UserRole.CHAIRMAN)):
            return Response({'error': 'Checker clearance (Super Admin or Chairman) required.'}, status=status.HTTP_403_FORBIDDEN)
        cr = self.get_object()
        ser = ConfigurationChangeReviewSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            updated = ConfigurationService.approve_configuration_change(
                change_request=cr,
                reviewer=request.user,
                comments=ser.validated_data.get('comments', ''),
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            return Response(ConfigurationChangeRequestSerializer(updated).data, status=status.HTTP_200_OK)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        from nht_sacco.apps.accounts.models import UserRole
        if not (request.user.is_superuser or getattr(request.user, 'role', None) in (UserRole.SUPER_ADMIN, UserRole.CHAIRMAN)):
            return Response({'error': 'Checker clearance (Super Admin or Chairman) required.'}, status=status.HTTP_403_FORBIDDEN)
        cr = self.get_object()
        ser = ConfigurationChangeReviewSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            updated = ConfigurationService.reject_configuration_change(
                change_request=cr,
                reviewer=request.user,
                comments=ser.validated_data.get('comments', ''),
            )
            return Response(ConfigurationChangeRequestSerializer(updated).data, status=status.HTTP_200_OK)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CompanyProfileAPIView(views.APIView):
    """
    Centralized Company Profile & Branding endpoint.
    Read: Super Admin, Chairman, Auditor.
    Write / Logo Upload / Replace: Super Admin only.
    """
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if self.request.method in ('GET', 'HEAD', 'OPTIONS'):
            return [IsAuditorOrSystemAdmin()]
        return [IsSystemAdminUser()]

    def get(self, request, *args, **kwargs):
        profile = CompanyProfile.get_active()
        return Response(CompanyProfileSerializer(profile).data, status=status.HTTP_200_OK)

    def _save_profile(self, request):
        from nht_sacco.apps.audit.models import AuditAction, AuditLog, AuditOutcome
        profile = CompanyProfile.get_active()
        notes = (request.data.get('change_notes') or 'Updated company profile & branding').strip()
        serializer = CompanyProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = serializer.save(updated_by=request.user)
        version_obj = updated.create_branding_version(user=request.user, notes=notes, bump_version=True)
        AuditLog.log_action(
            actor=request.user,
            action=AuditAction.UPDATE,
            entity_type='CompanyProfile',
            entity_id=f"v{version_obj.version_number}",
            outcome=AuditOutcome.SUCCESS,
            notes=f"Updated Company Profile & Branding to v{version_obj.version_number}: {notes}",
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        return Response(CompanyProfileSerializer(updated).data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        return self._save_profile(request)

    def put(self, request, *args, **kwargs):
        return self._save_profile(request)

    def patch(self, request, *args, **kwargs):
        return self._save_profile(request)


class CompanyProfileLogoDeleteAPIView(views.APIView):
    """
    Removes active company logo or monochrome logo and archives a new BrandingVersion.
    """
    permission_classes = [IsSystemAdminUser]

    def delete(self, request, *args, **kwargs):
        from nht_sacco.apps.audit.models import AuditAction, AuditLog, AuditOutcome
        profile = CompanyProfile.get_active()
        logo_type = (request.query_params.get('type') or 'primary').lower()
        if logo_type == 'monochrome':
            if profile.monochrome_logo and profile.monochrome_logo.name:
                profile.monochrome_logo.delete(save=False)
            profile.monochrome_logo = None
            profile.save(update_fields=['monochrome_logo', 'updated_at'])
            msg = 'Removed monochrome company logo'
        else:
            if profile.logo and profile.logo.name:
                profile.logo.delete(save=False)
            profile.logo = None
            profile.save(update_fields=['logo', 'updated_at'])
            msg = 'Removed primary company logo'

        version_obj = profile.create_branding_version(user=request.user, notes=msg, bump_version=True)
        AuditLog.log_action(
            actor=request.user,
            action=AuditAction.UPDATE,
            entity_type='CompanyProfile',
            entity_id=f"v{version_obj.version_number}",
            outcome=AuditOutcome.SUCCESS,
            notes=msg,
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        return Response(CompanyProfileSerializer(profile).data, status=status.HTTP_200_OK)


class CompanyProfileVersionsAPIView(views.APIView):
    permission_classes = [IsAuditorOrSystemAdmin]

    def get(self, request, *args, **kwargs):
        profile = CompanyProfile.get_active()
        versions = profile.versions.select_related('created_by').order_by('-version_number')[:50]
        return Response(BrandingVersionSerializer(versions, many=True).data, status=status.HTTP_200_OK)


class CompanyProfileLogoAssetView(views.APIView):
    """
    Streams validated PNG/JPEG logo bytes for active or versioned branding snapshots.
    """
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        from django.http import Http404
        profile = CompanyProfile.get_active()
        ver_param = request.query_params.get('version')
        logo_type = (request.query_params.get('type') or 'primary').lower()

        file_field = None
        if ver_param and ver_param.isdigit():
            ver_obj = BrandingVersion.objects.filter(company_profile=profile, version_number=int(ver_param)).first()
            if ver_obj:
                file_field = ver_obj.monochrome_logo_archive if logo_type == 'monochrome' else ver_obj.logo_archive
        else:
            file_field = profile.monochrome_logo if logo_type == 'monochrome' else profile.logo

        if not file_field or not file_field.name:
            raise Http404("No logo uploaded.")

        try:
            file_field.open('rb')
            data = file_field.read()
            file_field.close()
        except Exception:
            raise Http404("Logo file unavailable.")

        content_type = 'image/png' if file_field.name.lower().endswith('.png') else 'image/jpeg'
        resp = HttpResponse(data, content_type=content_type)
        resp['Cache-Control'] = 'public, max-age=300'
        resp['X-Content-Type-Options'] = 'nosniff'
        return resp
