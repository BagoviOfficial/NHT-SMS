from django.contrib import admin
from .models import MaintenanceProvider, SparePart, MaintenanceRecord, MaintenancePartUsage


class MaintenancePartUsageInline(admin.TabularInline):
    model = MaintenancePartUsage
    extra = 1


@admin.register(MaintenanceProvider)
class MaintenanceProviderAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_person', 'phone_number', 'physical_address', 'is_approved')
    list_filter = ('is_approved',)
    search_fields = ('name', 'contact_person', 'phone_number', 'physical_address')


@admin.register(SparePart)
class SparePartAdmin(admin.ModelAdmin):
    list_display = ('name', 'part_number', 'category', 'unit_cost', 'quantity_in_stock', 'minimum_reorder_level')
    list_filter = ('category',)
    search_fields = ('name', 'part_number')


@admin.register(MaintenanceRecord)
class MaintenanceRecordAdmin(admin.ModelAdmin):
    list_display = (
        'work_order_number',
        'vehicle',
        'maintenance_type',
        'provider',
        'status',
        'scheduled_date',
        'downtime_hours',
        'total_cost'
    )
    list_filter = ('maintenance_type', 'status', 'scheduled_date')
    search_fields = ('work_order_number', 'vehicle__registration_number', 'description')
    readonly_fields = ('work_order_number', 'total_cost', 'created_at', 'updated_at')
    inlines = [MaintenancePartUsageInline]
