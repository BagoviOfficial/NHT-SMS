from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('mpesa/callback/', views.MPesaCallbackView.as_view(), name='mpesa_callback'),
    path('vouchers/<uuid:pk>/review/', views.ManualPaymentVoucherReviewView.as_view(), name='voucher_review'),
    path('receipts/<uuid:pk>/', views.ReceiptDetailView.as_view(), name='receipt_detail'),
]
