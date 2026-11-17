from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import Payment, Receipt, ManualPaymentVoucher

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('payment_reference', 'provider_transaction_id', 'member', 'amount', 'method', 'status', 'created_at', 'receipt_link')
    list_filter = ('status', 'method', 'created_at')
    search_fields = ('payment_reference', 'provider_transaction_id', 'member__first_name', 'member__last_name', 'phone_number')
    ordering = ('-created_at',)
    readonly_fields = ('payment_reference', 'idempotency_key', 'raw_callback', 'created_at', 'confirmed_at')

    def receipt_link(self, obj):
        if hasattr(obj, 'receipt'):
            url = reverse('payments:receipt_detail', kwargs={'pk': obj.receipt.pk})
            return format_html('<a href="{}" class="button" target="_blank">View Receipt</a>', url)
        return "-"
    receipt_link.short_description = 'Receipt'

    def has_add_permission(self, request):
        return False  # Payments recorded via Daraja webhook or approved voucher

    def has_delete_permission(self, request, obj=None):
        return False  # Payments are immutable financial records

@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ('receipt_number', 'payment', 'issued_at', 'print_receipt')
    search_fields = ('receipt_number', 'payment__payment_reference', 'payment__provider_transaction_id')
    ordering = ('-issued_at',)
    readonly_fields = ('receipt_number', 'issued_at')

    def print_receipt(self, obj):
        url = reverse('payments:receipt_detail', kwargs={'pk': obj.pk})
        return format_html('<a href="{}" class="button" target="_blank">Print</a>', url)
    print_receipt.short_description = 'Print'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(ManualPaymentVoucher)
class ManualPaymentVoucherAdmin(admin.ModelAdmin):
    list_display = ('bank_slip_reference', 'member', 'amount', 'method', 'payment_date', 'status', 'entered_by', 'verified_by')
    list_filter = ('status', 'method', 'payment_date')
    search_fields = ('bank_slip_reference', 'member__first_name', 'member__last_name', 'bank_name')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'verified_at')

    def save_model(self, request, obj, form, change):
        if not change:
            obj.entered_by = request.user
        super().save_model(request, form, change)
