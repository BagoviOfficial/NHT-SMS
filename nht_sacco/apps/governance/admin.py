from django.contrib import admin
from .models import Committee, CommitteeMember, Meeting, MeetingAgenda, Resolution, ActionItem


class CommitteeMemberInline(admin.TabularInline):
    model = CommitteeMember
    extra = 1


class MeetingAgendaInline(admin.TabularInline):
    model = MeetingAgenda
    extra = 1


class ActionItemInline(admin.TabularInline):
    model = ActionItem
    extra = 1


@admin.register(Committee)
class CommitteeAdmin(admin.ModelAdmin):
    list_display = ('name', 'committee_type', 'chairperson', 'secretary', 'term_years', 'is_active')
    list_filter = ('committee_type', 'is_active')
    search_fields = ('name', 'description')
    inlines = [CommitteeMemberInline]


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ('meeting_number', 'title', 'committee', 'scheduled_date', 'location', 'status', 'quorum_reached')
    list_filter = ('status', 'committee', 'scheduled_date')
    search_fields = ('meeting_number', 'title', 'location')
    readonly_fields = ('meeting_number', 'created_at', 'updated_at')
    inlines = [MeetingAgendaInline]


@admin.register(Resolution)
class ResolutionAdmin(admin.ModelAdmin):
    list_display = ('resolution_number', 'title', 'meeting', 'status', 'votes_for', 'votes_against', 'effective_date')
    list_filter = ('status', 'effective_date')
    search_fields = ('resolution_number', 'title', 'description')
    readonly_fields = ('resolution_number', 'created_at')
    inlines = [ActionItemInline]


@admin.register(ActionItem)
class ActionItemAdmin(admin.ModelAdmin):
    list_display = ('description', 'resolution', 'assigned_to', 'due_date', 'is_completed')
    list_filter = ('is_completed', 'due_date')
    search_fields = ('description', 'assigned_to__username')
