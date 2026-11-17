import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class CommitteeType(models.TextChoices):
    EXECUTIVE = 'EXECUTIVE', _('Executive / Board of Directors')
    SUPERVISORY = 'SUPERVISORY', _('Supervisory Committee')
    OPERATIONS = 'OPERATIONS', _('Fleet & Operations Committee')
    CREDIT_FINANCE = 'CREDIT_FINANCE', _('Finance & Credit Committee')
    DISCIPLINARY = 'DISCIPLINARY', _('Disciplinary & Ethics Committee')


class MeetingStatus(models.TextChoices):
    SCHEDULED = 'SCHEDULED', _('Scheduled')
    CONVENED = 'CONVENED', _('Convened / In Session')
    ADJOURNED = 'ADJOURNED', _('Adjourned')
    MINUTES_PUBLISHED = 'MINUTES_PUBLISHED', _('Minutes Confirmed & Published')
    CANCELLED = 'CANCELLED', _('Cancelled')


class ResolutionStatus(models.TextChoices):
    PROPOSED = 'PROPOSED', _('Proposed')
    PASSED = 'PASSED', _('Passed by Vote')
    REJECTED = 'REJECTED', _('Rejected')
    IMPLEMENTED = 'IMPLEMENTED', _('Fully Implemented')
    SUPERSEDED = 'SUPERSEDED', _('Superseded by Later Resolution')


class Committee(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_('Committee Name'), max_length=200, unique=True)
    committee_type = models.CharField(
        _('Type'),
        max_length=32,
        choices=CommitteeType.choices,
        default=CommitteeType.OPERATIONS
    )
    description = models.TextField(_('Mandate & Description'), blank=True, default='')
    term_years = models.PositiveIntegerField(_('Term of Office (Years)'), default=3)
    is_active = models.BooleanField(_('Active'), default=True)
    chairperson = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='chaired_committees',
        verbose_name=_('Chairperson')
    )
    secretary = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='secretaried_committees',
        verbose_name=_('Secretary')
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = _('Committee')
        verbose_name_plural = _('Committees')

    def __str__(self):
        return f"{self.name} ({self.get_committee_type_display()})"


class CommitteeMember(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    committee = models.ForeignKey(Committee, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='committee_memberships')
    role_title = models.CharField(_('Role / Designation'), max_length=150, default='Committee Member')
    date_appointed = models.DateField(_('Date Appointed'), default=timezone.now)
    date_retired = models.DateField(_('Date Retired'), null=True, blank=True)
    is_active = models.BooleanField(_('Currently Serving'), default=True)

    class Meta:
        ordering = ['-date_appointed']
        unique_together = ('committee', 'user')
        verbose_name = _('Committee Member')
        verbose_name_plural = _('Committee Members')

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.committee.name} ({self.role_title})"


class Meeting(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting_number = models.CharField(
        _('Meeting Number'),
        max_length=32,
        unique=True,
        db_index=True,
        help_text=_('Format: NHT-MTG-YYYY-XXXX')
    )
    committee = models.ForeignKey(Committee, on_delete=models.CASCADE, related_name='meetings')
    title = models.CharField(_('Meeting Title / Purpose'), max_length=255)
    scheduled_date = models.DateTimeField(_('Scheduled Date & Time'))
    location = models.CharField(_('Location / Venue'), max_length=255, default='SACCO Boardroom, Isiolo Head Office')
    status = models.CharField(_('Status'), max_length=32, choices=MeetingStatus.choices, default=MeetingStatus.SCHEDULED)
    quorum_reached = models.BooleanField(_('Quorum Verified'), default=True)
    convened_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    minutes_text = models.TextField(_('Meeting Minutes & Notes'), blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-scheduled_date']
        verbose_name = _('Meeting')
        verbose_name_plural = _('Meetings')

    def __str__(self):
        return f"{self.meeting_number}: {self.title} ({self.committee.name})"

    def save(self, *args, **kwargs):
        if not self.meeting_number:
            year = timezone.now().year
            last = Meeting.objects.filter(meeting_number__startswith=f"NHT-MTG-{year}-").order_by('-meeting_number').first()
            if last:
                try:
                    last_seq = int(last.meeting_number.split('-')[-1])
                    seq = last_seq + 1
                except Exception:
                    seq = 1
            else:
                seq = 1
            self.meeting_number = f"NHT-MTG-{year}-{seq:04d}"
        super().save(*args, **kwargs)


class MeetingAgenda(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='agendas')
    item_number = models.PositiveIntegerField(default=1)
    topic = models.CharField(_('Agenda Topic'), max_length=255)
    presenter = models.CharField(_('Presenter'), max_length=150, blank=True, default='')
    allocated_minutes = models.PositiveIntegerField(_('Allocated Time (Mins)'), default=15)

    class Meta:
        ordering = ['item_number']
        verbose_name = _('Agenda Item')
        verbose_name_plural = _('Agenda Items')

    def __str__(self):
        return f"Item {self.item_number}: {self.topic}"


class Resolution(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    resolution_number = models.CharField(
        _('Resolution Identifier'),
        max_length=32,
        unique=True,
        db_index=True,
        help_text=_('Format: NHT-RES-YYYY-XXXX')
    )
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='resolutions')
    title = models.CharField(_('Resolution Title'), max_length=255)
    description = models.TextField(_('Resolution Text & Directives'))
    votes_for = models.PositiveIntegerField(_('Votes In Favour'), default=0)
    votes_against = models.PositiveIntegerField(_('Votes Against'), default=0)
    votes_abstained = models.PositiveIntegerField(_('Abstentions'), default=0)
    status = models.CharField(_('Status'), max_length=32, choices=ResolutionStatus.choices, default=ResolutionStatus.PROPOSED)
    effective_date = models.DateField(_('Effective Date'), default=timezone.now)
    proposer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='proposed_resolutions'
    )
    seconder = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='seconded_resolutions'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Resolution')
        verbose_name_plural = _('Resolutions')

    def __str__(self):
        return f"{self.resolution_number}: {self.title} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if not self.resolution_number:
            year = timezone.now().year
            last = Resolution.objects.filter(resolution_number__startswith=f"NHT-RES-{year}-").order_by('-resolution_number').first()
            if last:
                try:
                    last_seq = int(last.resolution_number.split('-')[-1])
                    seq = last_seq + 1
                except Exception:
                    seq = 1
            else:
                seq = 1
            self.resolution_number = f"NHT-RES-{year}-{seq:04d}"
        super().save(*args, **kwargs)


class ActionItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    resolution = models.ForeignKey(Resolution, on_delete=models.CASCADE, related_name='action_items')
    description = models.CharField(_('Actionable Directive'), max_length=255)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_actions'
    )
    due_date = models.DateField(_('Due Date'))
    is_completed = models.BooleanField(_('Completed'), default=False)
    completion_notes = models.TextField(_('Implementation Notes'), blank=True, default='')
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['due_date']
        verbose_name = _('Action Item')
        verbose_name_plural = _('Action Items')

    def __str__(self):
        return f"{self.description} (Due: {self.due_date})"
