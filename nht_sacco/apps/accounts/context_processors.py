def brand_context(request):
    """
    Exposes Northern Highways Transporters brand identity and role flags to all templates.
    """
    user = request.user if hasattr(request, 'user') else None
    return {
        'BRAND_NAME': 'Northern Highways Transporters SACCO',
        'BRAND_SHORT': 'NHT-SMS',
        'BRAND_NAVY': '#10315C',
        'BRAND_BLUE': '#1B4A8A',
        'BRAND_ORANGE': '#FF8A00',
        'BRAND_WHITE': '#FFFFFF',
        'is_management': user.is_authenticated and user.is_management_staff if user else False,
        'is_finance': user.is_authenticated and user.is_financial_staff if user else False,
        'is_compliance': user.is_authenticated and user.is_compliance_staff if user else False,
        'is_renewal': user.is_authenticated and user.is_renewal_staff if user else False,
        'is_auditor': user.is_authenticated and user.is_auditor if user else False,
        'is_member': user.is_authenticated and user.is_member if user else False,
    }
