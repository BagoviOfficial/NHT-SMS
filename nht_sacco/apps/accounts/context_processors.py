from nht_sacco.config.mui import get_active_branding_payload


def brand_context(request):
    """
    Exposes Northern Highways Transporters brand identity and role flags.
    Delegates branding lookup to `get_active_branding_payload` to avoid duplication.
    """
    user = request.user if hasattr(request, 'user') else None
    branding = get_active_branding_payload()
    logo_url = f"{branding['logo_url']}?v={branding['branding_version']}" if branding['logo_url'] else ''
    authed = bool(user and user.is_authenticated)

    return {
        'BRAND_NAME': branding['sacco_name'],
        'BRAND_LEGAL_NAME': branding['legal_name'],
        'BRAND_SHORT': branding['short_name'],
        'BRAND_NAVY': branding['primary_color'],
        'BRAND_BLUE': branding['brand_blue'],
        'BRAND_ORANGE': branding['secondary_color'],
        'BRAND_LOGO_URL': logo_url,
        'BRAND_FOOTER': branding['footer_text'],
        'BRAND_WHITE': '#FFFFFF',
        'DEFAULT_CURRENCY': branding['currency'],
        'is_management': authed and user.is_management_staff,
        'is_secretary': authed and getattr(user, 'is_secretary', False),
        'is_chairman': authed and getattr(user, 'is_chairman', False),
        'is_field_officer': authed and getattr(user, 'is_field_officer', False),
        'is_finance': authed and user.is_financial_staff,
        'is_compliance': authed and user.is_compliance_staff,
        'is_renewal': authed and user.is_renewal_staff,
        'is_auditor': authed and user.is_auditor,
        'is_member': authed and user.is_member,
        'is_driver': authed and getattr(user, 'is_driver', False),
        'is_system_admin': authed and (user.is_superuser or getattr(user, 'role', '') == 'SUPER_ADMIN'),
        'dashboard_url': getattr(user, 'dashboard_url', '/accounts/login/') if authed else '/accounts/login/',
    }
