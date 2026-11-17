from django.contrib import admin
from .models import Member, MemberDocument

class MemberDocumentInline(admin.TabularInline):
    model = MemberDocument
    extra = 1

@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ('membership_number', 'full_name', 'national_id', 'phone_number', 'category', 'status', 'application_date')
    list_filter = ('status', 'category', 'county')
    search_fields = ('membership_number', 'first_name', 'last_name', 'national_id', 'phone_number', 'email')
    ordering = ('-created_at',)
    inlines = [MemberDocumentInline]
    readonly_fields = ('membership_number', 'application_date', 'approval_date', 'approved_by')

    fieldsets = (
        ('Membership Identification', {'fields': ('membership_number', 'user', 'status', 'category')}),
        ('Personal Details', {'fields': ('first_name', 'middle_name', 'last_name', 'national_id', 'phone_number', 'email', 'postal_address', 'county')}),
        ('Next of Kin', {'fields': ('next_of_kin_name', 'next_of_kin_relation', 'next_of_kin_phone')}),
        ('Secretariat Approval', {'fields': ('approved_by', 'approval_date', 'approval_notes', 'application_date')}),
    )

    actions = ['approve_selected_members', 'suspend_selected_members']

    @admin.action(description='Approve selected membership applications')
    def approve_selected_members(self, request, queryset):
        for member in queryset.filter(status='PENDING'):
            member.approve(request.user, notes='Bulk approved via SACCO Admin.')
        self.message_user(request, "Selected pending members have been approved.")

    @admin.action(description='Suspend selected members')
    def suspend_selected_members(self, request, queryset):
        for member in queryset.filter(status='ACTIVE'):
            member.suspend(request.user, reason='Administrative suspension.')
        self.message_user(request, "Selected active members have been suspended.")
