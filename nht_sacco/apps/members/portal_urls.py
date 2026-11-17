from django.urls import path
from . import portal_views

app_name = 'portal'

urlpatterns = [
    path('', portal_views.portal_dashboard, name='dashboard'),
    
    # Vehicles & Cards
    path('vehicles/', portal_views.portal_vehicles, name='vehicles'),
    path('vehicles/register/', portal_views.portal_vehicle_register, name='vehicle_register'),
    path('vehicles/<uuid:vehicle_id>/', portal_views.portal_vehicle_detail, name='vehicle_detail'),
    path('vehicles/<uuid:vehicle_id>/card/', portal_views.portal_vehicle_card, name='vehicle_card'),
    
    # Billing & Financials
    path('invoices/', portal_views.portal_invoices, name='invoices'),
    path('invoices/<uuid:invoice_id>/', portal_views.portal_invoice_detail, name='invoice_detail'),
    path('invoices/<uuid:invoice_id>/pay/', portal_views.portal_invoice_pay_stk, name='invoice_pay_stk'),
    path('receipts/', portal_views.portal_receipts, name='receipts'),
    path('statement/', portal_views.portal_statement, name='statement'),
    
    # Renewals
    path('renewals/', portal_views.portal_renewals, name='renewals'),
    path('renewals/apply/', portal_views.portal_renewal_apply, name='renewal_apply'),
    
    # Notifications & Preferences
    path('notifications/', portal_views.portal_notifications, name='notifications'),
    path('notifications/<uuid:notif_id>/read/', portal_views.portal_notification_mark_read, name='notification_read'),
    path('preferences/', portal_views.portal_preferences, name='preferences'),
    
    # Grievances & Inquiries
    path('complaints/', portal_views.portal_complaints, name='complaints'),
    path('complaints/submit/', portal_views.portal_complaint_submit, name='complaint_submit'),
]
