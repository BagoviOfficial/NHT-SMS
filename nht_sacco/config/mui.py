"""
Centralized Material UI (MUI) single-template rendering and active branding helpers.
Every HTML route in NHT-SMS renders the single React 19 + Material UI v9 shell
at `templates/spa/index.html`.
"""

from django.middleware.csrf import get_token
from django.shortcuts import render


MUI_TEMPLATE_NAME = 'spa/index.html'
DEFAULT_SACCO_NAME = 'Northern Highways Transporters SACCO'
DEFAULT_LEGAL_NAME = 'Northern Highways Transporters SACCO Limited'
DEFAULT_PRIMARY_COLOR = '#10315C'
DEFAULT_SECONDARY_COLOR = '#FF8A00'


def get_active_branding_payload():
    """
    Returns the active SACCO branding metadata dictionary from CompanyProfile
    and ConfigurationService. Single source of truth across APIs, templates, and context.
    """
    from nht_sacco.apps.integrations.models import CompanyProfile
    from nht_sacco.apps.integrations.services import ConfigurationService

    sacco_cfg = ConfigurationService.get_str('business.sacco_name', '')
    app_cfg = ConfigurationService.get_str('app.name', '')
    if app_cfg and app_cfg != DEFAULT_SACCO_NAME:
        brand_name = app_cfg
    elif sacco_cfg and sacco_cfg != DEFAULT_SACCO_NAME:
        brand_name = sacco_cfg
    else:
        brand_name = sacco_cfg or app_cfg or DEFAULT_SACCO_NAME

    brand_short = ConfigurationService.get_str('app.short_name', 'NHT-SMS')

    primary_cfg = ConfigurationService.get_str('app.brand_primary_color', '')
    navy_cfg = ConfigurationService.get_str('app.brand_navy', '')
    if navy_cfg and navy_cfg != DEFAULT_PRIMARY_COLOR:
        primary_color = navy_cfg
    elif primary_cfg and primary_cfg != DEFAULT_PRIMARY_COLOR:
        primary_color = primary_cfg
    else:
        primary_color = primary_cfg or navy_cfg or DEFAULT_PRIMARY_COLOR

    secondary_cfg = ConfigurationService.get_str('app.brand_secondary_color', '')
    orange_cfg = ConfigurationService.get_str('app.brand_orange', '')
    if orange_cfg and orange_cfg != DEFAULT_SECONDARY_COLOR:
        secondary_color = orange_cfg
    elif secondary_cfg and secondary_cfg != DEFAULT_SECONDARY_COLOR:
        secondary_color = secondary_cfg
    else:
        secondary_color = secondary_cfg or orange_cfg or DEFAULT_SECONDARY_COLOR

    currency = ConfigurationService.get_str('business.currency', 'KES')
    legal_name = DEFAULT_LEGAL_NAME
    footer_text = ''
    logo_url = ''
    branding_version = 1

    try:
        profile = CompanyProfile.get_active()
        if profile:
            customized = profile.updated_by_id is not None
            if profile.trading_name and (customized or profile.trading_name != DEFAULT_SACCO_NAME):
                brand_name = profile.trading_name
            legal_name = profile.legal_name or legal_name
            brand_short = profile.short_name or brand_short
            if profile.primary_color and (customized or profile.primary_color != DEFAULT_PRIMARY_COLOR):
                primary_color = profile.primary_color
            if profile.secondary_color and (customized or profile.secondary_color != DEFAULT_SECONDARY_COLOR):
                secondary_color = profile.secondary_color
            footer_text = profile.footer_text or ''
            branding_version = profile.current_version or 1
            if profile.logo and profile.logo.name:
                logo_url = '/settings/api/v1/company-profile/logo-asset/'
    except Exception:
        pass

    return {
        'sacco_name': brand_name,
        'legal_name': legal_name,
        'short_name': brand_short,
        'primary_color': primary_color,
        'secondary_color': secondary_color,
        'brand_blue': ConfigurationService.get_str('app.brand_blue', '#1B4A8A'),
        'currency': currency,
        'logo_url': logo_url,
        'branding_version': branding_version,
        'footer_text': footer_text,
    }


def get_mui_context(
    request,
    *,
    initial_route='',
    is_admin_portal=False,
    page_data=None,
    page_title='',
    extra_context=None,
):
    """
    Builds the template context for the single MUI SPA shell (`templates/spa/index.html`).
    """
    get_token(request)
    branding = get_active_branding_payload()
    context = {
        'sacco_name': branding['sacco_name'],
        'primary_color': branding['primary_color'],
        'secondary_color': branding['secondary_color'],
        'currency': branding['currency'],
        'logo_url': branding['logo_url'],
        'is_admin_portal': bool(is_admin_portal),
        'initial_route': initial_route or '',
        'page_data': page_data if page_data is not None else {},
        'page_title': page_title or ('Admin Dashboard' if is_admin_portal else 'Workspace'),
    }
    if extra_context:
        context.update(extra_context)
    return context


def render_mui_app(
    request,
    *,
    initial_route='',
    is_admin_portal=False,
    page_data=None,
    page_title='',
    extra_context=None,
    status=200,
):
    """
    Renders the single Material UI v9 SPA template (`templates/spa/index.html`).
    """
    context = get_mui_context(
        request,
        initial_route=initial_route,
        is_admin_portal=is_admin_portal,
        page_data=page_data,
        page_title=page_title,
        extra_context=extra_context,
    )
    return render(request, MUI_TEMPLATE_NAME, context, status=status)
