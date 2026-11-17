from django.contrib import admin
from django.utils.html import format_html
from .models import ServiceItem, ServicePrice, Invoice, InvoiceItem, CreditNote

class ServicePriceInline(admin.TabularInline):
    model = ServicePrice
    extra = 1

@admin.register(ServiceItem)
class ServiceItemAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'category', 'is_statutory', 'is_active')
    list_filter = ('category', 'is_statutory', 'is_active')
    search_fields = ('code', 'name')
    inlines = [ServicePriceInline]

class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'member', 'total_amount', 'amount_paid', 'balance_display', 'status', 'issue_date', 'due_date')
    list_filter = ('status', 'issue_date', 'due_date')
    search_fields = ('invoice_number', 'member__first_name', 'member__last_name', 'member__membership_number')
    ordering = ('-issue_date', '-created_at')
    inlines = [InvoiceItemInline]
    readonly_fields = ('invoice_number', 'subtotal', 'statutory_total', 'total_amount', 'amount_paid', 'created_at', 'updated_at')

    def balance_display(self, obj):
        bal = obj.balance_due
        color = 'red' if bal > 0 else 'green'
        return format_html('<span style="color: {}; font-weight: bold;">KES {}</span>', color, bal)
    balance_display.short_description = 'Balance Due'

@admin.register(CreditNote)
class CreditNoteAdmin(admin.ModelAdmin):
    list_display = ('credit_number', 'invoice', 'amount', 'authorized_by', 'created_at')
    search_fields = ('credit_number', 'invoice__invoice_number')
    readonly_fields = ('created_at',)
