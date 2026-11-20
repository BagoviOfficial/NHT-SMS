from nht_sacco.apps.integrations.services import ConfigurationService


def brand_context(request):
    """
    Exposes Northern Highways Transporters brand identity and role flags to all templates.
    Dynamically loads brand details, color palettes and operational flags from ConfigurationService.
    """
    user = request.user if hasattr(request, 'user') else None
    return {
        'BRAND_NAME': ConfigurationService.get_str('app.name', 'Northern Highways Transporters SACCO'),
        'BRAND_SHORT': ConfigurationService.get_str('app.short_name', 'NHT-SMS'),
        'BRAND_NAVY': ConfigurationService.get_str('app.brand_navy', '#10315C'),
        'BRAND_BLUE': ConfigurationService.get_str('app.brand_blue', '#1B4A8A'),
        'BRAND_ORANGE': ConfigurationService.get_str('app.brand_orange', '#FF8A00'),
        'BRAND_WHITE': '#FFFFFF',
        'DEFAULT_CURRENCY': ConfigurationService.get_str('business.currency', 'KES'),
        'is_management': user.is_authenticated and user.is_management_staff if user else False,
        'is_finance': user.is_authenticated and user.is_financial_staff if user else False,
        'is_compliance': user.is_authenticated and user.is_compliance_staff if user else False,
        'is_renewal': user.is_authenticated and user.is_renewal_staff if user else False,
        'is_auditor': user.is_authenticated and user.is_auditor if user else False,
        'is_member': user.is_authenticated and user.is_member if user else False,
        'is_system_admin': user.is_authenticated and (user.is_superuser or user.role == 'SUPER_ADMIN') if user else False,
    }
