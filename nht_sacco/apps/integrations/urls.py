from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'integrations'

router = DefaultRouter()
router.register(r'configs', views.ConfigurationViewSet, basename='config_item')

urlpatterns = [
    # Administration Web Portal
    path('', views.SystemSettingsView.as_view(), name='settings_index'),
    path('update/', views.SystemSettingsUpdateView.as_view(), name='settings_update'),
    path('rollback/', views.SystemSettingsRollbackView.as_view(), name='settings_rollback'),
    path('export/', views.SystemSettingsExportView.as_view(), name='settings_export'),
    path('import/', views.SystemSettingsImportView.as_view(), name='settings_import'),
    path('test-connection/', views.ProviderConnectionTestView.as_view(), name='settings_test_connection'),

    # REST API Endpoints
    path('api/v1/', include([
        path('', include(router.urls)),
        path('update/', views.ConfigurationUpdateAPIView.as_view(), name='api_config_update'),
        path('assess-impact/', views.ConfigurationImpactAssessmentAPIView.as_view(), name='api_assess_impact'),
        path('rollback/', views.ConfigurationRollbackAPIView.as_view(), name='api_config_rollback'),
        path('export/', views.ConfigurationExportAPIView.as_view(), name='api_config_export'),
        path('import/', views.ConfigurationImportAPIView.as_view(), name='api_config_import'),
        path('health/', views.SystemHealthAPIView.as_view(), name='api_system_health'),
        path('test-provider/', views.ProviderTestAPIView.as_view(), name='api_test_provider'),
    ])),
]
