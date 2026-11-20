import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

class AccountType(models.TextChoices):
    ASSET = 'ASSET', _('Asset (Cash, Bank, Accounts Receivable)')
    LIABILITY = 'LIABILITY', _('Liability (Prepayments, Accounts Payable)')
    EQUITY = 'EQUITY', _('Equity (Member Capital, Retained Surplus)')
    REVENUE = 'REVENUE', _('Revenue (Fees, Levies, Subscriptions)')
    EXPENSE = 'EXPENSE', _('Expense (Administrative, Regulatory, Welfare)')

class Account(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(_('Account Code'), max_length=20, unique=True, db_index=True)
    name = models.CharField(_('Account Name'), max_length=150)
    type = models.CharField(_('Account Type'), max_length=20, choices=AccountType.choices, db_index=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'accounting_account'
        verbose_name = _('General Ledger Account')
        verbose_name_plural = _('General Ledger Accounts')
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name} ({self.get_type_display()})"

    @property
    def current_balance(self):
        """
        Calculates balance based on normal account debit/credit conventions.
        Assets & Expenses: Balance = Debits - Credits
        Liabilities, Equity & Revenue: Balance = Credits - Debits
        """
        total_debits = self.journal_lines.aggregate(s=models.Sum('debit'))['s'] or Decimal('0.00')
        total_credits = self.journal_lines.aggregate(s=models.Sum('credit'))['s'] or Decimal('0.00')

        if self.type in [AccountType.ASSET, AccountType.EXPENSE]:
            return total_debits - total_credits
        else:
            return total_credits - total_debits


class FinancialPeriod(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_('Period Name'), max_length=50, unique=True, help_text=_('e.g. FY2026-Q4'))
    start_date = models.DateField(_('Start Date'))
    end_date = models.DateField(_('End Date'))
    is_closed = models.BooleanField(_('Is Closed / Locked'), default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'accounting_period'
        verbose_name = _('Financial Period')
        verbose_name_plural = _('Financial Periods')
        ordering = ['-start_date']

    def __str__(self):
        status = " [CLOSED]" if self.is_closed else " [OPEN]"
        return f"{self.name} ({self.start_date} to {self.end_date}){status}"


class JournalEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entry_number = models.CharField(
        _('Journal Entry Number'),
        max_length=50,
        unique=True,
        db_index=True,
        help_text=_('Format: NHT-JRN-YYYY-XXXX')
    )
    date = models.DateField(_('Posting Date'), default=timezone.now, db_index=True)
    period = models.ForeignKey(FinancialPeriod, on_delete=models.PROTECT, related_name='journal_entries')
    reference = models.CharField(_('Transaction Reference'), max_length=100, db_index=True)
    narration = models.TextField(_('Narration / Description'))
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='posted_journals',
        null=True,
        blank=True
    )
    is_posted = models.BooleanField(default=True)
    is_reversal = models.BooleanField(_('Is Reversal Entry'), default=False)
    reverses_entry = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reversal_entries'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'accounting_journal_entry'
        verbose_name = _('Journal Entry')
        verbose_name_plural = _('Journal Entries')
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.entry_number} [{self.date}] - {self.reference} ({self.narration[:40]})"

    @classmethod
    def generate_entry_number(cls):
        year = timezone.now().year
        count = cls.objects.filter(entry_number__startswith=f"NHT-JRN-{year}").count() + 1
        return f"NHT-JRN-{year}-{count:04d}"

    def clean(self):
        # Enforce financial period closed check
        if self.period and self.period.is_closed:
            raise ValidationError(_(f"Cannot post to closed financial period '{self.period.name}'."))

        # Enforce immutability of posted transactions
        if not self._state.adding and self.is_posted:
            orig = JournalEntry.objects.filter(pk=self.pk).first()
            if orig and orig.is_posted:
                # Disallow modifying date, period, or reference once posted
                if (orig.date != self.date or orig.period != self.period or orig.reference != self.reference):
                    raise ValidationError(_("Posted journal entries are immutable. Adjustments must use reversal entries."))

    def delete(self, *args, **kwargs):
        raise ValidationError(_("Posted journal entries cannot be deleted. Use a reversal entry to correct transactions."))

    def verify_balance(self):
        """
        Validates that total debits equal total credits for this journal entry.
        """
        total_debit = self.lines.aggregate(s=models.Sum('debit'))['s'] or Decimal('0.00')
        total_credit = self.lines.aggregate(s=models.Sum('credit'))['s'] or Decimal('0.00')

        if total_debit != total_credit:
            raise ValidationError(
                _(f"Unbalanced Journal Entry {self.entry_number}: Total Debits (KES {total_debit}) != Total Credits (KES {total_credit})")
            )
        return True


class JournalLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name='lines')
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='journal_lines')
    debit = models.DecimalField(_('Debit (KES)'), max_digits=12, decimal_places=2, default=Decimal('0.00'))
    credit = models.DecimalField(_('Credit (KES)'), max_digits=12, decimal_places=2, default=Decimal('0.00'))

    class Meta:
        db_table = 'accounting_journal_line'
        verbose_name = _('Journal Entry Line')
        verbose_name_plural = _('Journal Entry Lines')

    def __str__(self):
        return f"{self.account.code}: Dr KES {self.debit} | Cr KES {self.credit}"


class Expense(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    expense_number = models.CharField(
        _('Expense Voucher Number'),
        max_length=50,
        unique=True,
        db_index=True,
        help_text=_('Format: NHT-EXP-YYYY-XXXX')
    )
    category = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name='categorized_expenses',
        verbose_name=_('Expense Account (Dr)')
    )
    payment_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name='disbursed_expenses',
        verbose_name=_('Disbursement Account (Cr)')
    )
    amount = models.DecimalField(_('Amount (KES)'), max_digits=12, decimal_places=2)
    date = models.DateField(_('Expense Date'), default=timezone.now)
    payee = models.CharField(_('Payee / Beneficiary'), max_length=150)
    description = models.TextField(_('Purpose & Justification'))
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='recorded_expenses'
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='approved_expenses'
    )
    status = models.CharField(
        max_length=20,
        choices=[('PENDING', 'Pending Approval'), ('APPROVED', 'Approved & Posted'), ('REJECTED', 'Rejected')],
        default='PENDING',
        db_index=True
    )
    journal_entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='linked_expenses'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'accounting_expense'
        verbose_name = _('Operating Expense')
        verbose_name_plural = _('Operating Expenses')
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.expense_number}: {self.payee} - KES {self.amount} [{self.get_status_display()}]"

    @classmethod
    def generate_expense_number(cls):
        year = timezone.now().year
        count = cls.objects.filter(expense_number__startswith=f"NHT-EXP-{year}").count() + 1
        return f"NHT-EXP-{year}-{count:04d}"
