from decimal import Decimal
from django.db import models, transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from .models import Account, AccountType, FinancialPeriod, JournalEntry, JournalLine, Expense
from nht_sacco.apps.audit.models import AuditLog, AuditAction, AuditOutcome
from nht_sacco.apps.billing.models import Invoice, InvoiceStatus
from nht_sacco.apps.payments.models import Payment, PaymentStatus, PaymentMethod, Receipt

class AccountingService:
    @classmethod
    def get_or_create_current_period(cls, date_val=None):
        target_date = date_val or timezone.now().date()
        period = FinancialPeriod.objects.filter(
            start_date__lte=target_date,
            end_date__gte=target_date,
            is_closed=False
        ).first()

        if not period:
            # Generate quarter name e.g. FY2026-Q4
            quarter = (target_date.month - 1) // 3 + 1
            name = f"FY{target_date.year}-Q{quarter}"
            # Define standard quarter bounds
            start_month = (quarter - 1) * 3 + 1
            from calendar import monthrange
            end_month = start_month + 2
            _, end_day = monthrange(target_date.year, end_month)

            start = timezone.datetime(target_date.year, start_month, 1).date()
            end = timezone.datetime(target_date.year, end_month, end_day).date()

            period, _ = FinancialPeriod.objects.get_or_create(
                name=name,
                defaults={'start_date': start, 'end_date': end, 'is_closed': False}
            )
        return period

    @classmethod
    @transaction.atomic
    def post_invoice_issuance(cls, invoice, user):
        """
        Posts double-entry journal for invoice issuance:
        Dr 1100 Accounts Receivable (Total)
        Cr 4020 SACCO Subscription / Service Revenue (Subtotal)
        Cr 2020 Statutory Pass-Through Payable (Statutory fees)
        """
        ar_account = Account.objects.get(code='1100')
        rev_account = Account.objects.get(code='4020')
        stat_account = Account.objects.get(code='2020')

        period = cls.get_or_create_current_period(invoice.issue_date)

        entry = JournalEntry.objects.create(
            entry_number=JournalEntry.generate_entry_number(),
            date=invoice.issue_date,
            period=period,
            reference=invoice.invoice_number,
            narration=f"Invoice issuance for {invoice.member.full_name} ({invoice.invoice_number})",
            posted_by=user
        )

        # Dr Accounts Receivable (Total)
        JournalLine.objects.create(
            journal_entry=entry,
            account=ar_account,
            debit=invoice.total_amount,
            credit=Decimal('0.00')
        )

        # Cr SACCO Revenue (Subtotal)
        if invoice.subtotal > Decimal('0.00'):
            JournalLine.objects.create(
                journal_entry=entry,
                account=rev_account,
                debit=Decimal('0.00'),
                credit=invoice.subtotal
            )

        # Cr Statutory Payable (Statutory Fees)
        if invoice.statutory_total > Decimal('0.00'):
            JournalLine.objects.create(
                journal_entry=entry,
                account=stat_account,
                debit=Decimal('0.00'),
                credit=invoice.statutory_total
            )

        entry.verify_balance()
        return entry

    @classmethod
    @transaction.atomic
    def post_payment_receipt(cls, payment, user=None):
        """
        Posts double-entry journal for payment receipt:
        Dr 1020 M-Pesa / 1030 Bank / 1010 Cash (Amount)
        Cr 1100 Accounts Receivable (Amount)
        Enforces idempotency: prevents creating duplicate journals for the same payment reference.
        """
        # Idempotency check: if journal already exists for this payment reference, return it
        existing_entry = JournalEntry.objects.filter(reference=payment.payment_reference).first()
        if existing_entry:
            return existing_entry

        if payment.method == 'MPESA':
            cash_code = '1020'
            cash_name = 'M-Pesa Collections'
        elif payment.method == 'BANK_TRANSFER':
            cash_code = '1030'
            cash_name = 'Bank Account'
        else:
            cash_code = '1010'
            cash_name = 'Cash Office'

        cash_account, _ = Account.objects.get_or_create(
            code=cash_code,
            defaults={'name': cash_name, 'type': AccountType.ASSET}
        )
        ar_account, _ = Account.objects.get_or_create(
            code='1100',
            defaults={'name': 'Accounts Receivable', 'type': AccountType.ASSET}
        )

        period = cls.get_or_create_current_period(payment.confirmed_at.date() if payment.confirmed_at else None)

        posting_user = user
        if posting_user is not None and not getattr(posting_user, 'is_authenticated', True):
            posting_user = None

        entry = JournalEntry.objects.create(
            entry_number=JournalEntry.generate_entry_number(),
            date=payment.confirmed_at.date() if payment.confirmed_at else timezone.now().date(),
            period=period,
            reference=payment.payment_reference,
            narration=f"Payment settlement for {payment.invoice.invoice_number} via {payment.get_method_display()}",
            posted_by=posting_user
        )

        # Dr Cash / M-Pesa
        JournalLine.objects.create(
            journal_entry=entry,
            account=cash_account,
            debit=payment.amount,
            credit=Decimal('0.00')
        )

        # Cr Accounts Receivable
        JournalLine.objects.create(
            journal_entry=entry,
            account=ar_account,
            debit=Decimal('0.00'),
            credit=payment.amount
        )

        entry.verify_balance()
        return entry

    @classmethod
    @transaction.atomic
    def record_payment_settlement(
        cls,
        payment,
        amount,
        provider_transaction_id=None,
        user=None,
        raw_callback=None,
        notes=''
    ):
        """
        Coordinates the complete, centralized, transactional payment settlement workflow:
        1. Select for update on Payment and Invoice (row-level locking).
        2. Validate payment state transition (must be INITIATED or PENDING).
        3. Validate amount and check provider reference idempotency.
        4. Confirm Payment (status=SUCCESS, confirmed_at).
        5. Allocate payment towards Invoice balance.
        6. Issue official Receipt (preventing duplicates).
        7. Post balanced Double-Entry General Ledger Journal Entry (preventing duplicates).
        8. Record immutable AuditLog entry.
        """
        # 1. Acquire row-level locks
        locked_payment = Payment.objects.select_for_update().get(pk=payment.pk)
        locked_invoice = Invoice.objects.select_for_update().get(pk=locked_payment.invoice.pk)

        # 2. Strict Idempotency & State Validation
        if locked_payment.status == PaymentStatus.SUCCESS:
            receipt = Receipt.objects.filter(payment=locked_payment).first()
            journal = JournalEntry.objects.filter(reference=locked_payment.payment_reference).first()
            return {
                'success': True,
                'status': 'ALREADY_PROCESSED',
                'payment': locked_payment,
                'receipt': receipt,
                'journal_entry': journal,
                'message': 'Payment already cleared and settled (Idempotent).'
            }

        if locked_payment.status not in (PaymentStatus.INITIATED, 'PENDING'):
            raise ValidationError(
                f"Invalid payment state transition: Cannot settle payment with status '{locked_payment.status}'."
            )

        amount_decimal = Decimal(str(amount))
        if amount_decimal <= Decimal('0.00'):
            raise ValidationError("Settlement amount must be strictly positive.")

        # Check provider reference uniqueness across the system
        if provider_transaction_id:
            duplicate = Payment.objects.filter(provider_transaction_id=provider_transaction_id).exclude(pk=locked_payment.pk).first()
            if duplicate:
                raise ValidationError(f"Provider transaction reference '{provider_transaction_id}' was already processed.")

        # 3. Update payment status to SUCCESS
        locked_payment.status = PaymentStatus.SUCCESS
        if provider_transaction_id:
            locked_payment.provider_transaction_id = provider_transaction_id
        locked_payment.amount = amount_decimal
        locked_payment.confirmed_at = timezone.now()
        if raw_callback:
            locked_payment.raw_callback = raw_callback
        locked_payment.save(update_fields=['status', 'provider_transaction_id', 'amount', 'confirmed_at', 'raw_callback'])

        # 4. Allocate payment to invoice
        locked_invoice.allocate_payment(amount_decimal)

        # 5. Issue official Receipt (ensure no duplicate)
        receipt = Receipt.objects.filter(payment=locked_payment).first()
        if not receipt:
            receipt = Receipt.objects.create(
                receipt_number=Receipt.generate_receipt_number(),
                payment=locked_payment,
                issued_by=user if (user and getattr(user, 'is_authenticated', False)) else None
            )

        # 6. Post double-entry journal entry
        journal_entry = cls.post_payment_receipt(locked_payment, user=user)

        # 7. Immutable Audit Trail
        actor_user = user if (user and getattr(user, 'is_authenticated', False)) else None
        AuditLog.objects.create(
            actor=actor_user,
            actor_username=actor_user.username if actor_user else 'PAYMENT_GATEWAY',
            action=AuditAction.PAYMENT,
            entity_type='Invoice',
            entity_id=locked_invoice.invoice_number,
            outcome=AuditOutcome.SUCCESS,
            change_details={
                'provider_reference': provider_transaction_id or locked_payment.provider_transaction_id,
                'payment_ref': locked_payment.payment_reference,
                'amount': str(amount_decimal),
                'receipt_no': receipt.receipt_number,
                'journal_entry_no': journal_entry.entry_number if journal_entry else None,
                'invoice_balance': str(locked_invoice.balance_due),
                'notes': notes
            }
        )

        return {
            'success': True,
            'status': 'SETTLED',
            'payment': locked_payment,
            'receipt': receipt,
            'journal_entry': journal_entry,
            'invoice': locked_invoice,
            'invoice_balance': locked_invoice.balance_due,
            'message': 'Payment successfully cleared and all accounting records committed.'
        }

    @classmethod
    @transaction.atomic
    def post_expense(cls, expense, user):
        """
        Posts double-entry journal for an approved expense:
        Dr Expense Category Account (Amount)
        Cr Cash / Bank Disbursement Account (Amount)
        """
        period = cls.get_or_create_current_period(expense.date)

        entry = JournalEntry.objects.create(
            entry_number=JournalEntry.generate_entry_number(),
            date=expense.date,
            period=period,
            reference=expense.expense_number,
            narration=f"Expense disbursement: {expense.payee} - {expense.description}",
            posted_by=user
        )

        # Dr Expense
        JournalLine.objects.create(
            journal_entry=entry,
            account=expense.category,
            debit=expense.amount,
            credit=Decimal('0.00')
        )

        # Cr Disbursement Account
        JournalLine.objects.create(
            journal_entry=entry,
            account=expense.payment_account,
            debit=Decimal('0.00'),
            credit=expense.amount
        )

        entry.verify_balance()
        expense.journal_entry = entry
        expense.status = 'APPROVED'
        expense.approved_by = user
        expense.approved_at = timezone.now()
        expense.save(update_fields=['journal_entry', 'status', 'approved_by', 'approved_at'])
        return entry

    @classmethod
    @transaction.atomic
    def reverse_journal_entry(cls, original_entry, user, reason):
        """
        Creates an immutable, balancing reversal journal entry.
        Inverts all debit and credit lines of the original entry.
        """
        period = cls.get_or_create_current_period(timezone.now().date())

        reversal = JournalEntry.objects.create(
            entry_number=JournalEntry.generate_entry_number(),
            date=timezone.now().date(),
            period=period,
            reference=f"REV-{original_entry.entry_number}",
            narration=f"Reversal of {original_entry.entry_number}: {reason}",
            posted_by=user,
            is_reversal=True,
            reverses_entry=original_entry
        )

        for line in original_entry.lines.all():
            JournalLine.objects.create(
                journal_entry=reversal,
                account=line.account,
                debit=line.credit,  # Invert!
                credit=line.debit   # Invert!
            )

        reversal.verify_balance()

        AuditLog.objects.create(
            actor=user,
            action=AuditAction.REVERSAL,
            entity_type='JournalEntry',
            entity_id=original_entry.entry_number,
            outcome=AuditOutcome.SUCCESS,
            change_details={'reversal_entry': reversal.entry_number, 'reason': reason}
        )
        return reversal

    @classmethod
    def get_trial_balance(cls):
        """
        Calculates trial balance across all accounts and asserts equilibrium.
        """
        accounts = Account.objects.filter(is_active=True).order_by('code')
        trial_lines = []
        total_dr = Decimal('0.00')
        total_cr = Decimal('0.00')

        for acc in accounts:
            debits = acc.journal_lines.aggregate(s=models.Sum('debit'))['s'] or Decimal('0.00')
            credits = acc.journal_lines.aggregate(s=models.Sum('credit'))['s'] or Decimal('0.00')

            total_dr += debits
            total_cr += credits

            trial_lines.append({
                'code': acc.code,
                'name': acc.name,
                'type': acc.get_type_display(),
                'debit': debits,
                'credit': credits,
                'balance': acc.current_balance,
            })

        return {
            'lines': trial_lines,
            'total_debits': total_dr,
            'total_credits': total_cr,
            'is_balanced': total_dr == total_cr,
        }
