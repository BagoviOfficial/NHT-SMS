from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('dashboard/', views.reports_dashboard, name='dashboard'),
    path('export/compliance/pdf/', views.export_compliance_pdf, name='export_compliance_pdf'),
    path('export/financial/excel/', views.export_financial_excel, name='export_financial_excel'),
]
