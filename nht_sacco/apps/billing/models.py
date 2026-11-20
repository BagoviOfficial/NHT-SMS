import uuid
from decimal import Decimal
from django.db import models, transaction
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from nht_sacco.apps.members.models import Member
from nht_sacco.apps.vehicles.models import Vehicle
from nht_sacco.apps.integrations.services import ConfigurationService

class ServiceCategory(models.TextChoices):
    MEMBERSHIP = 'MEMBERSHIP', _('Membership Registration & Onboarding')
    SUBSCRIPTION = 'SUBSCRIPTION', _('Monthly / Annual SACCO Subscriptions')
    RENEWAL = 'RENEWAL', _('Document Renewal Processing Fee')
    STATUTORY = 'STATUTORY', _('Statutory Government Charges (Pass-through)')
    LEVY = 'LEVY', _('Welfare Levy & Development Contribution')
    PENALTY = 'PENALTY', _('Late Payment Penalty')
    OTHER = 'OTHER', _('Other Transport Services')

class ServiceItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(_('Service Code'), max_length=50, unique=True, db_index=True)
    name = models.CharField(_('Service Name'), max_length=150)
    category = models.CharField(_('Category'), max_length=30, choices=ServiceCategory.choices)
    description = models.TextField(blank=True)
    is_statutory = models.BooleanField(
        _('Is Statutory Government Fee'),
        default=False,
        help_text=_('Designates KeNHA, NTSA or County pass-through charges kept separate from SACCO revenue')
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'billing_service_item'
        verbose_name = _('Service Item')
        verbose_name_plural = _('Service Items')
        ordering = ['code']

    def __str__(self):
        stat_label = " [Statutory]" if self.is_statutory else ""
        return f"{self.code}: {self.name}{stat_label}"


class ServicePrice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service_item = models.ForeignKey(ServiceItem, on_delete=models.CASCADE, related_name='price_tiers')
    amount = models.DecimalField(_('Amount (KES)'), max_digits=12, decimal_places=2)
    effective_from = models.DateField(_('Effective From Date'), default=timezone.now)
    effective_to = models.DateField(_('Effective To Date'), null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'billing_service_price'
        verbose_name = _('Service Price Schedule')
        verbose_name_plural = _('Service Price Schedules')
        ordering = ['-effective_from']

    def __str__(self):
        return f"{self.service_item.name} - KES {self.amount} (From {self.effective_from})"


class InvoiceStatus(models.TextChoices):
    DRAFT = 'DRAFT', _('Draft')
    ISSUED = 'ISSUED', _('Issued / Unpaid')
    PARTIALLY_PAID = 'PARTIALLY_PAID', _('Partially Paid')
    PAID = 'PAID', _('Fully Paid')
    CANCELLED = 'CANCELLED', _('Cancelled')

class Invoice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice_number = models.CharField(
        _('Invoice Number'),
        max_length=50,
        unique=True,
        db_index=True,
        help_text=_('Format: NHT-INV-YYYY-XXXX')
    )
    member = models.ForeignKey(
        Member,
        on_delete=models.PROTECT,
        related_name='invoices',
        verbose_name=_('Billed Member')
    )
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices',
        verbose_name=_('Associated Vehicle')
    )
    issue_date = models.DateField(_('Issue Date'), default=timezone.now)
    due_date = models.DateField(_('Payment Due Date'))
    subtotal = models.DecimalField(_('SACCO Charges (KES)'), max_digits=12, decimal_places=2, default=Decimal('0.00'))
    statutory_total = models.DecimalField(_('Statutory Fees (KES)'), max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(_('Total Billed (KES)'), max_digits=12, decimal_places=2, default=Decimal('0.00'))
    amount_paid = models.DecimalField(_('Amount Paid (KES)'), max_digits=12, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(
        _('Invoice Status'),
        max_length=20,
        choices=InvoiceStatus.choices,
        default=InvoiceStatus.ISSUED,
        db_index=True
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='generated_invoices'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'billing_invoice'
        verbose_name = _('Invoice')
        verbose_name_plural = _('Invoices')
        ordering = ['-issue_date', '-created_at']

    def __str__(self):
        return f"{self.invoice_number} - {self.member.full_name} (KES {self.total_amount}) [{self.get_status_display()}]"

    @property
    def balance_due(self):
        return max(Decimal('0.00'), self.total_amount - self.amount_paid)

    @property
    def is_fully_paid(self):
        """
        Returns True if the invoice has been settled in full or has zero balance remaining.
        """
        return self.status == InvoiceStatus.PAID or self.balance_due <= Decimal('0.00')

    @property
    def is_overdue(self):
        return self.status != InvoiceStatus.PAID and self.due_date < timezone.now().date()

    @classmethod
    def generate_invoice_number(cls):
        year = timezone.now().year
        prefix = ConfigurationService.get_str('business.invoice_prefix', 'NHT-INV')
        count = cls.objects.filter(invoice_number__startswith=f"{prefix}-{year}").count() + 1
        return f"{prefix}-{year}-{count:04d}"

    def recalculate_totals(self):
        """
        Recalculates SACCO subtotal, statutory pass-through fees, and grand total.
        Uses pure Decimal arithmetic.
        """
        subtotal = Decimal('0.00')
        statutory = Decimal('0.00')
        for item in self.line_items.all():
            if item.service_item.is_statutory:
                statutory += item.total_price
            else:
                subtotal += item.total_price
        self.subtotal = subtotal
        self.statutory_total = statutory
        self.total_amount = subtotal + statutory

        # Update status based on payments
        if self.amount_paid >= self.total_amount and self.total_amount > Decimal('0.00'):
            self.status = InvoiceStatus.PAID
        elif self.amount_paid > Decimal('0.00'):
            self.status = InvoiceStatus.PARTIALLY_PAID
        elif self.status != InvoiceStatus.CANCELLED:
            self.status = InvoiceStatus.ISSUED

        self.save(update_fields=['subtotal', 'statutory_total', 'total_amount', 'status', 'updated_at'])

    @transaction.atomic
    def allocate_payment(self, payment_amount):
        """
        Allocates incoming payment amount to the invoice balance transactionally.
        """
        self.amount_paid += Decimal(str(payment_amount))
        if self.amount_paid >= self.total_amount:
            self.status = InvoiceStatus.PAID
        else:
            self.status = InvoiceStatus.PARTIALLY_PAID
        self.save(update_fields=['amount_paid', 'status', 'updated_at'])


class InvoiceItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='line_items')
    service_item = models.ForeignKey(ServiceItem, on_delete=models.PROTECT, related_name='invoice_items')
    description = models.CharField(_('Line Description'), max_length=255)
    unit_price = models.DecimalField(_('Unit Price (KES)'), max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField(_('Quantity'), default=1)
    total_price = models.DecimalField(_('Total Price (KES)'), max_digits=12, decimal_places=2)

    class Meta:
        db_table = 'billing_invoice_item'
        verbose_name = _('Invoice Line Item')
        verbose_name_plural = _('Invoice Line Items')

    def save(self, *args, **kwargs):
        self.total_price = self.unit_price * Decimal(str(self.quantity))
        super().save(*args, **kwargs)


class CreditNote(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    credit_number = models.CharField(max_length=50, unique=True, db_index=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='credit_notes')
    amount = models.DecimalField(_('Credit Amount (KES)'), max_digits=12, decimal_places=2)
    reason = models.TextField(_('Adjustment Reason'))
    authorized_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'billing_credit_note'
        verbose_name = _('Credit Note')
        verbose_name_plural = _('Credit Notes')
        ordering = ['-created_at']

    @classmethod
    def generate_credit_number(cls):
        year = timezone.now().year
        count = cls.objects.filter(credit_number__startswith=f"NHT-CRN-{year}").count() + 1
        return f"NHT-CRN-{year}-{count:04d}"
