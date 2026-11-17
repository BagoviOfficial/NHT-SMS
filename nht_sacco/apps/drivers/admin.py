from django.contrib import admin
from .models import Driver, DriverAssignment

class DriverAssignmentInline(admin.TabularInline):
    model = DriverAssignment
    extra = 1

@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'national_id', 'phone_number', 'driving_license_number', 'dl_expiry_date', 'status')
    list_filter = ('status', 'dl_expiry_date')
    search_fields = ('full_name', 'national_id', 'phone_number', 'driving_license_number')
    ordering = ('full_name',)
    inlines = [DriverAssignmentInline]

@admin.register(DriverAssignment)
class DriverAssignmentAdmin(admin.ModelAdmin):
    list_display = ('driver', 'vehicle', 'assigned_at', 'relieved_at', 'is_current')
    list_filter = ('is_current', 'assigned_at')
    search_fields = ('driver__full_name', 'vehicle__registration_number')
