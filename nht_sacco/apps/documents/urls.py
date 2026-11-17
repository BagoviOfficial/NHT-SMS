from django.urls import path
from . import views

app_name = 'documents'

urlpatterns = [
    path('<uuid:pk>/download/', views.DocumentDownloadView.as_view(), name='document_download'),
]
