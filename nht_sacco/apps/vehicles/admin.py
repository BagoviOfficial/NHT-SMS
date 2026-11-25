from django.contrib import admin
from .models import Vehicle, VehicleOwnershipHistory, VehiclePhoto, VehicleComplianceCard

class VehiclePhotoInline(admin.TabularInline):
    model = VehiclePhoto
    extra = 1

class VehicleOwnershipHistoryInline(admin.TabularInline):
    model = VehicleOwnershipHistory
    extra = 0
    readonly_fields = ('previous_owner', 'new_owner', 'transfer_date', 'transfer_reason', 'authorized_by')

@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('registration_number', 'make', 'model', 'category', 'current_owner', 'carrying_capacity', 'status')
    list_filter = ('status', 'category', 'fuel_type')
    search_fields = ('registration_number', 'chassis_number', 'engine_number', 'current_owner__first_name', 'current_owner__last_name')
    ordering = ('registration_number',)
    inlines = [VehiclePhotoInline, VehicleOwnershipHistoryInline]
    readonly_fields = ('qr_token', 'registered_at', 'updated_at')

    fieldsets = (
        ('Vehicle Registration', {'fields': ('registration_number', 'category', 'status', 'current_owner')}),
        ('Technical Specifications', {'fields': ('make', 'model', 'year_of_manufacture', 'color', 'fuel_type', 'carrying_capacity')}),
        ('Engine & Chassis', {'fields': ('chassis_number', 'engine_number')}),
        ('Verification & QR', {'fields': ('qr_token', 'registered_at', 'updated_at')}),
    )

@admin.register(VehicleOwnershipHistory)
class VehicleOwnershipHistoryAdmin(admin.ModelAdmin):
    list_display = ('vehicle', 'previous_owner', 'new_owner', 'transfer_date', 'authorized_by')
    list_filter = ('transfer_date',)
    search_fields = ('vehicle__registration_number', 'previous_owner__first_name', 'new_owner__first_name')


@admin.register(VehicleComplianceCard)
class VehicleComplianceCardAdmin(admin.ModelAdmin):
    list_display = ('certificate_number', 'vehicle', 'status', 'issue_date', 'expiry_date', 'issued_by')
    list_filter = ('status', 'issue_date', 'expiry_date')
    search_fields = ('certificate_number', 'vehicle__registration_number', 'owner_display_name', 'token_hint')
    readonly_fields = ('certificate_number', 'token_hash', 'token_hint', 'encrypted_token', 'branding_version', 'created_at', 'updated_at')
