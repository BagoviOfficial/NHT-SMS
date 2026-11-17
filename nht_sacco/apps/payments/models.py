import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from nht_sacco.apps.members.models import Member
from nht_sacco.apps.billing.models import Invoice

class PaymentMethod(models.TextChoices):
    MPESA = 'MPESA', _('M-Pesa (Daraja STK / PayBill)')
    BANK_TRANSFER = 'BANK_TRANSFER', _('Direct Bank Deposit / RTGS')
    CASH = 'CASH', _('Cash Office Voucher')
    CHEQUE = 'CHEQUE', _('Banker Cheque')

class PaymentStatus(models.TextChoices):
    INITIATED = 'INITIATED', _('Initiated / Awaiting Callback')
    SUCCESS = 'SUCCESS', _('Confirmed & Cleared')
    FAILED = 'FAILED', _('Failed / Cancelled by User')
    REVERSED = 'REVERSED', _('Reversed / Refunded')

class Payment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment_reference = models.CharField(
        _('Payment Reference'),
        max_length=50,
        unique=True,
        db_index=True,
        help_text=_('Format: NHT-PAY-YYYY-XXXX')
    )
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        related_name='payments',
        verbose_name=_('Settled Invoice')
    )
    member = models.ForeignKey(
        Member,
        on_delete=models.PROTECT,
        related_name='payments',
        verbose_name=_('Paying Member')
    )
    method = models.CharField(
        _('Payment Method'),
        max_length=30,
        choices=PaymentMethod.choices,
        default=PaymentMethod.MPESA
    )
    amount = models.DecimalField(
        _('Amount Cleared (KES)'),
        max_digits=12,
        decimal_places=2
    )
    currency = models.CharField(max_length=10, default='KES')
    provider_transaction_id = models.CharField(
        _('Provider Reference (M-Pesa Code / Bank Slip)'),
        max_length=100,
        unique=True,
        null=True,
        blank=True,
        db_index=True
    )
    idempotency_key = models.CharField(
        _('Idempotency Token'),
        max_length=120,
        unique=True,
        db_index=True
    )
    status = models.CharField(
        _('Payment Status'),
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.INITIATED,
        db_index=True
    )
    phone_number = models.CharField(max_length=20, blank=True)
    raw_callback = models.JSONField(_('Raw Provider Callback Payload'), default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'payments_payment'
        verbose_name = _('Payment')
        verbose_name_plural = _('Payments')
        ordering = ['-created_at']

    def __str__(self):
        ref = self.provider_transaction_id or self.payment_reference
        return f"{ref} - KES {self.amount} ({self.get_status_display()})"

    def get_payment_method_display(self):
        return self.get_method_display()

    @classmethod
    def generate_payment_reference(cls):
        year = timezone.now().year
        count = cls.objects.filter(payment_reference__startswith=f"NHT-PAY-{year}").count() + 1
        return f"NHT-PAY-{year}-{count:04d}"


class Receipt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    receipt_number = models.CharField(
        _('Receipt Number'),
        max_length=50,
        unique=True,
        db_index=True,
        help_text=_('Format: NHT-REC-YYYY-XXXX')
    )
    payment = models.OneToOneField(
        Payment,
        on_delete=models.PROTECT,
        related_name='receipt',
        verbose_name=_('Cleared Payment')
    )
    issued_at = models.DateTimeField(auto_now_add=True)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='issued_receipts'
    )

    class Meta:
        db_table = 'payments_receipt'
        verbose_name = _('Official Receipt')
        verbose_name_plural = _('Official Receipts')
        ordering = ['-issued_at']

    def __str__(self):
        return f"{self.receipt_number} for {self.payment.payment_reference} (KES {self.payment.amount})"

    @classmethod
    def generate_receipt_number(cls):
        year = timezone.now().year
        count = cls.objects.filter(receipt_number__startswith=f"NHT-REC-{year}").count() + 1
        return f"NHT-REC-{year}-{count:04d}"


class ManualPaymentVoucher(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending Verification (Maker Stage)')
        VERIFIED = 'VERIFIED', _('Verified & Cleared (Checker Stage)')
        REJECTED = 'REJECTED', _('Rejected / Discrepancy Found')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name='payment_vouchers')
    member = models.ForeignKey(Member, on_delete=models.PROTECT, related_name='payment_vouchers')
    method = models.CharField(
        max_length=30,
        choices=[('BANK_TRANSFER', 'Bank Transfer / Deposit'), ('CASH', 'Cash Office Voucher')],
        default='BANK_TRANSFER'
    )
    bank_slip_reference = models.CharField(_('Bank Slip / Deposit Slip No.'), max_length=100)
    bank_name = models.CharField(_('Depository Bank'), max_length=100, blank=True)
    amount = models.DecimalField(_('Deposit Amount (KES)'), max_digits=12, decimal_places=2)
    payment_date = models.DateField(_('Actual Deposit Date'))
    supporting_document = models.FileField(upload_to='private/payment_vouchers/', null=True, blank=True)
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='entered_vouchers',
        verbose_name=_('Recording Clerk (Maker)')
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='verified_vouchers',
        verbose_name=_('Authorizing Officer (Checker)')
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True
    )
    verification_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'payments_manual_voucher'
        verbose_name = _('Manual Payment Voucher')
        verbose_name_plural = _('Manual Payment Vouchers')
        ordering = ['-created_at']

    def __str__(self):
        return f"Voucher {self.bank_slip_reference} - KES {self.amount} [{self.get_status_display()}]"
