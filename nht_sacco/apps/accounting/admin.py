from django.contrib import admin
from django.utils.html import format_html
from .models import Account, FinancialPeriod, JournalEntry, JournalLine, Expense

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'type', 'balance_display', 'is_active')
    list_filter = ('type', 'is_active')
    search_fields = ('code', 'name')
    ordering = ('code',)

    def balance_display(self, obj):
        bal = obj.current_balance
        color = 'green' if bal >= 0 else 'red'
        return format_html('<span style="color: {}; font-weight: bold;">KES {}</span>', color, bal)
    balance_display.short_description = 'Ledger Balance'

@admin.register(FinancialPeriod)
class FinancialPeriodAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'is_closed')
    list_filter = ('is_closed',)
    ordering = ('-start_date',)

class JournalLineInline(admin.TabularInline):
    model = JournalLine
    extra = 2

@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ('entry_number', 'date', 'period', 'reference', 'narration', 'posted_by', 'is_reversal')
    list_filter = ('is_reversal', 'period', 'date')
    search_fields = ('entry_number', 'reference', 'narration')
    ordering = ('-date', '-created_at')
    inlines = [JournalLineInline]
    readonly_fields = ('entry_number', 'created_at')

    def has_delete_permission(self, request, obj=None):
        return False  # Financial records are immutable

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('expense_number', 'payee', 'amount', 'category', 'date', 'status', 'recorded_by', 'approved_by')
    list_filter = ('status', 'category', 'date')
    search_fields = ('expense_number', 'payee', 'description')
    ordering = ('-date',)
    readonly_fields = ('expense_number', 'created_at', 'approved_at')

    def save_model(self, request, obj, form, change):
        if not change:
            obj.recorded_by = request.user
        super().save_model(request, form, change)
