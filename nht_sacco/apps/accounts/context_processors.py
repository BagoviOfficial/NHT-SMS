from nht_sacco.apps.integrations.services import ConfigurationService


def brand_context(request):
    """
    Exposes Northern Highways Transporters brand identity and role flags to all templates.
    Dynamically loads active CompanyProfile & ConfigurationService metadata.
    """
    user = request.user if hasattr(request, 'user') else None
    brand_name = ConfigurationService.get_str('app.name', 'Northern Highways Transporters SACCO')
    brand_short = ConfigurationService.get_str('app.short_name', 'NHT-SMS')
    primary_color = ConfigurationService.get_str('app.brand_navy', '#10315C')
    secondary_color = ConfigurationService.get_str('app.brand_orange', '#FF8A00')
    logo_url = ''
    legal_name = 'Northern Highways Transporters SACCO Limited'
    footer_text = ''
    try:
        from nht_sacco.apps.integrations.models import CompanyProfile
        profile = CompanyProfile.objects.filter(key='default').first()
        if profile:
            brand_name = profile.trading_name or brand_name
            brand_short = profile.short_name or brand_short
            primary_color = profile.primary_color or primary_color
            secondary_color = profile.secondary_color or secondary_color
            legal_name = profile.legal_name or legal_name
            footer_text = profile.footer_text or ''
            if profile.logo and profile.logo.name:
                logo_url = f'/settings/api/v1/company-profile/logo-asset/?v={profile.current_version}'
    except Exception:
        pass

    return {
        'BRAND_NAME': brand_name,
        'BRAND_LEGAL_NAME': legal_name,
        'BRAND_SHORT': brand_short,
        'BRAND_NAVY': primary_color,
        'BRAND_BLUE': ConfigurationService.get_str('app.brand_blue', '#1B4A8A'),
        'BRAND_ORANGE': secondary_color,
        'BRAND_LOGO_URL': logo_url,
        'BRAND_FOOTER': footer_text,
        'BRAND_WHITE': '#FFFFFF',
        'DEFAULT_CURRENCY': ConfigurationService.get_str('business.currency', 'KES'),
        'is_management': user.is_authenticated and user.is_management_staff if user else False,
        'is_secretary': user.is_authenticated and getattr(user, 'is_secretary', False) if user else False,
        'is_chairman': user.is_authenticated and getattr(user, 'is_chairman', False) if user else False,
        'is_field_officer': user.is_authenticated and getattr(user, 'is_field_officer', False) if user else False,
        'is_finance': user.is_authenticated and user.is_financial_staff if user else False,
        'is_compliance': user.is_authenticated and user.is_compliance_staff if user else False,
        'is_renewal': user.is_authenticated and user.is_renewal_staff if user else False,
        'is_auditor': user.is_authenticated and user.is_auditor if user else False,
        'is_member': user.is_authenticated and user.is_member if user else False,
        'is_driver': user.is_authenticated and getattr(user, 'is_driver', False) if user else False,
        'is_system_admin': user.is_authenticated and (user.is_superuser or getattr(user, 'role', '') == 'SUPER_ADMIN') if user else False,
        'user_role_badge': getattr(user, 'role_badge_color', 'secondary') if user and user.is_authenticated else 'secondary',
        'user_role_icon': getattr(user, 'role_icon', 'person') if user and user.is_authenticated else 'person',
        'dashboard_url': getattr(user, 'dashboard_url', '/accounts/login/') if user and user.is_authenticated else '/accounts/login/',
    }
