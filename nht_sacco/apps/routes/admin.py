from django.contrib import admin
from .models import Route, VehicleRouteAssignment

class VehicleRouteAssignmentInline(admin.TabularInline):
    model = VehicleRouteAssignment
    extra = 1

@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ('route_code', 'name', 'origin', 'destination', 'distance_km', 'is_active')
    list_filter = ('is_active', 'origin', 'destination')
    search_fields = ('route_code', 'name', 'origin', 'destination')
    inlines = [VehicleRouteAssignmentInline]

@admin.register(VehicleRouteAssignment)
class VehicleRouteAssignmentAdmin(admin.ModelAdmin):
    list_display = ('vehicle', 'route', 'road_service_license', 'assigned_date', 'is_active')
    list_filter = ('is_active', 'route')
    search_fields = ('vehicle__registration_number', 'route__route_code', 'road_service_license')
