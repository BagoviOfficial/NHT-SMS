from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import DocumentType, Document, DocumentVerification

@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'standard_validity_months', 'is_mandatory_for_vehicle', 'is_mandatory_for_driver')
    list_filter = ('category', 'is_mandatory_for_vehicle', 'is_mandatory_for_driver')
    search_fields = ('name',)

class DocumentVerificationInline(admin.TabularInline):
    model = DocumentVerification
    extra = 0
    readonly_fields = ('reviewed_by', 'decision', 'notes', 'timestamp')

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('reference_number', 'document_type', 'target_entity', 'issue_date', 'expiry_date', 'status', 'version', 'download_link')
    list_filter = ('status', 'document_type__category', 'expiry_date')
    search_fields = ('reference_number', 'vehicle__registration_number', 'member__first_name', 'member__last_name', 'driver__full_name')
    ordering = ('-created_at',)
    inlines = [DocumentVerificationInline]
    readonly_fields = ('file_hash', 'version', 'created_at', 'updated_at')

    def target_entity(self, obj):
        if obj.vehicle:
            return f"Vehicle: {obj.vehicle.registration_number}"
        if obj.driver:
            return f"Driver: {obj.driver.full_name}"
        if obj.member:
            return f"Member: {obj.member.full_name}"
        return "Unassigned"
    target_entity.short_description = 'Target Entity'

    def download_link(self, obj):
        if obj.file:
            url = reverse('documents:document_download', kwargs={'pk': obj.pk})
            return format_html('<a href="{}" class="button" target="_blank">Download Securely</a>', url)
        return "-"
    download_link.short_description = 'Private Vault'

    actions = ['verify_selected_documents', 'reject_selected_documents']

    @admin.action(description='Verify and approve selected documents')
    def verify_selected_documents(self, request, queryset):
        for doc in queryset:
            doc.status = 'VERIFIED'
            doc.verified_by = request.user
            doc.save()
            DocumentVerification.objects.create(
                document=doc,
                reviewed_by=request.user,
                decision='APPROVED',
                notes='Bulk verified by officer.'
            )
        self.message_user(request, "Selected documents marked as VERIFIED.")

    @admin.action(description='Reject selected documents')
    def reject_selected_documents(self, request, queryset):
        for doc in queryset:
            doc.status = 'REJECTED'
            doc.verified_by = request.user
            doc.save()
            DocumentVerification.objects.create(
                document=doc,
                reviewed_by=request.user,
                decision='REJECTED',
                notes='Rejected in administrative review.'
            )
        self.message_user(request, "Selected documents marked as REJECTED.")
