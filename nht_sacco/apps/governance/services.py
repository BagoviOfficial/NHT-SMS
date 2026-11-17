from django.utils import timezone
from django.db.models import Count, Q
from .models import Committee, Meeting, Resolution, ActionItem, ResolutionStatus, MeetingStatus


class GovernanceService:
    @staticmethod
    def record_vote(resolution: Resolution, votes_for: int, votes_against: int, votes_abstained: int = 0):
        """
        Calculates voting outcome and updates resolution status.
        """
        resolution.votes_for = votes_for
        resolution.votes_against = votes_against
        resolution.votes_abstained = votes_abstained
        if votes_for > votes_against:
            resolution.status = ResolutionStatus.PASSED
        else:
            resolution.status = ResolutionStatus.REJECTED
        resolution.save()
        return resolution

    @staticmethod
    def complete_action(action_item: ActionItem, notes: str = ""):
        """
        Marks an assigned resolution action as completed.
        """
        action_item.is_completed = True
        action_item.completion_notes = notes
        action_item.completed_at = timezone.now()
        action_item.save()
        return action_item

    @staticmethod
    def get_governance_summary():
        """
        Returns high-level governance statistics for executive dashboards.
        """
        return {
            'active_committees': Committee.objects.filter(is_active=True).count(),
            'total_meetings': Meeting.objects.count(),
            'completed_meetings': Meeting.objects.filter(status=MeetingStatus.MINUTES_PUBLISHED).count(),
            'passed_resolutions': Resolution.objects.filter(status__in=[ResolutionStatus.PASSED, ResolutionStatus.IMPLEMENTED]).count(),
            'pending_actions': ActionItem.objects.filter(is_completed=False).count(),
        }
