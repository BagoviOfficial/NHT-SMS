from django.urls import path
from . import views

app_name = 'renewals'

urlpatterns = [
    path('<uuid:pk>/review/', views.RenewalRequestReviewView.as_view(), name='renewal_review'),
]
