from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, LoginHistory

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'phone_number', 'national_id', 'role', 'is_active', 'is_staff', 'date_joined')
    list_filter = ('role', 'is_active', 'is_staff', 'is_verified')
    search_fields = ('username', 'email', 'phone_number', 'national_id', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal Information'), {'fields': ('first_name', 'last_name', 'email', 'phone_number', 'national_id')}),
        (_('Role & Permissions'), {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Security & Compliance'), {'fields': ('is_verified', 'must_change_password', 'last_login_ip')}),
        (_('Important Dates'), {'fields': ('last_login', 'date_joined')}),
    )

    readonly_fields = ('date_joined', 'last_login', 'last_login_ip')

@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    list_display = ('username_attempted', 'user', 'status', 'ip_address', 'timestamp')
    list_filter = ('status', 'timestamp')
    search_fields = ('username_attempted', 'ip_address')
    ordering = ('-timestamp',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
