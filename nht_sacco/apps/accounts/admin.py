from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from .models import User, UserRole, LoginHistory


def _active_super_admins_excluding(user_pk):
    return User.objects.filter(is_active=True).filter(
        Q(role=UserRole.SUPER_ADMIN) | Q(is_superuser=True)
    ).exclude(pk=user_pk)


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

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj))
        if not (request.user.is_superuser or getattr(request.user, 'role', None) == UserRole.SUPER_ADMIN):
            ro.extend(['is_superuser', 'role', 'user_permissions', 'groups'])
        return ro

    def save_model(self, request, obj, form, change):
        actor_is_super = request.user.is_superuser or getattr(request.user, 'role', None) == UserRole.SUPER_ADMIN
        target_is_super = obj.role == UserRole.SUPER_ADMIN or obj.is_superuser
        if not actor_is_super:
            if target_is_super:
                raise PermissionDenied("Only an active Super Administrator may grant Super Admin privileges.")
            if change:
                orig = User.objects.filter(pk=obj.pk).first()
                if orig and (orig.role == UserRole.SUPER_ADMIN or orig.is_superuser):
                    raise PermissionDenied("Only a Super Administrator may modify a Super Admin account.")
        if change:
            orig = User.objects.filter(pk=obj.pk).first()
            was_active_super = orig and orig.is_active and (orig.role == UserRole.SUPER_ADMIN or orig.is_superuser)
            will_be_active_super = obj.is_active and (obj.role == UserRole.SUPER_ADMIN or obj.is_superuser)
            if was_active_super and not will_be_active_super and not _active_super_admins_excluding(obj.pk).exists():
                raise ValidationError("Cannot deactivate or demote the last active Super Administrator.")
        if obj.role != UserRole.SUPER_ADMIN and change:
            orig = User.objects.filter(pk=obj.pk).first()
            if orig and orig.role == UserRole.SUPER_ADMIN:
                obj.is_superuser = False
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        if (obj.role == UserRole.SUPER_ADMIN or obj.is_superuser) and not _active_super_admins_excluding(obj.pk).exists():
            messages.error(request, "Cannot delete the last active Super Administrator.", fail_silently=True)
            raise PermissionDenied("Cannot delete the last active Super Administrator.")
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        remaining = User.objects.filter(is_active=True).filter(
            Q(role=UserRole.SUPER_ADMIN) | Q(is_superuser=True)
        ).exclude(pk__in=queryset.values_list('pk', flat=True))
        if not remaining.exists():
            messages.error(request, "Cannot delete all remaining active Super Administrators.", fail_silently=True)
            raise PermissionDenied("Cannot delete all remaining active Super Administrators.")
        super().delete_queryset(request, queryset)

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
