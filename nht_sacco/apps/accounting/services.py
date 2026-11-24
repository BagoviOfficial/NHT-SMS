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
        target_date = date_val or timezone.localdate()
        closed_period = FinancialPeriod.objects.filter(
            start_date__lte=target_date,
            end_date__gte=target_date,
            is_closed=True
        ).first()
        if closed_period:
            raise ValidationError(f"Cannot post to closed financial period '{closed_period.name}'.")

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
            if period.is_closed:
                raise ValidationError(f"Cannot post to closed financial period '{period.name}'.")
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
            date=payment.confirmed_at.date() if payment.confirmed_at else timezone.localdate(),
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

        # 6b. Sync linked RenewalRequests when invoice is fully paid
        if locked_invoice.is_fully_paid:
            from nht_sacco.apps.renewals.models import RenewalRequest, RenewalStatus
            for renewal in RenewalRequest.objects.filter(
                invoice=locked_invoice,
                status=RenewalStatus.INVOICED
            ):
                renewal.mark_paid()

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
        period = cls.get_or_create_current_period(timezone.localdate())

        reversal = JournalEntry.objects.create(
            entry_number=JournalEntry.generate_entry_number(),
            date=timezone.localdate(),
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

    @classmethod
    @transaction.atomic
    def post_manual_journal(cls, date_val, reference, narration, lines_data, user):
        """
        Posts a manual double-entry journal entry and verifies Debit == Credit equilibrium.
        """
        if not lines_data or len(lines_data) < 2:
            raise ValidationError("A manual journal entry requires at least two lines (debit and credit).")

        target_date = date_val or timezone.localdate()
        period = cls.get_or_create_current_period(target_date)

        total_dr = sum(Decimal(str(l.get('debit', '0.00'))) for l in lines_data)
        total_cr = sum(Decimal(str(l.get('credit', '0.00'))) for l in lines_data)
        if total_dr <= Decimal('0.00') or total_dr != total_cr:
            raise ValidationError(
                f"Journal entry must balance with positive totals (Debits={total_dr}, Credits={total_cr})."
            )

        entry = JournalEntry.objects.create(
            entry_number=JournalEntry.generate_entry_number(),
            date=target_date,
            period=period,
            reference=reference,
            narration=narration,
            posted_by=user,
        )
        for line in lines_data:
            account = Account.objects.get(pk=line['account_id'])
            JournalLine.objects.create(
                journal_entry=entry,
                account=account,
                debit=Decimal(str(line.get('debit', '0.00'))),
                credit=Decimal(str(line.get('credit', '0.00'))),
            )
        entry.verify_balance()

        AuditLog.log_action(
            actor=user,
            action=AuditAction.CREATE,
            entity_type='JournalEntry',
            entity_id=entry.entry_number,
            outcome=AuditOutcome.SUCCESS,
            notes=f"Manual balanced journal posted ({reference}): Dr/Cr KES {total_dr}",
        )
        return entry

    @classmethod
    @transaction.atomic
    def close_period(cls, period: FinancialPeriod, user):
        if period.is_closed:
            return period
        period.is_closed = True
        period.save(update_fields=['is_closed'])
        AuditLog.log_action(
            actor=user,
            action=AuditAction.UPDATE,
            entity_type='FinancialPeriod',
            entity_id=period.name,
            outcome=AuditOutcome.SUCCESS,
            notes=f"Closed financial period {period.name}",
        )
        return period

    @classmethod
    @transaction.atomic
    def reopen_period(cls, period: FinancialPeriod, user, reason=''):
        if not period.is_closed:
            return period
        period.is_closed = False
        period.save(update_fields=['is_closed'])
        AuditLog.log_action(
            actor=user,
            action=AuditAction.UPDATE,
            entity_type='FinancialPeriod',
            entity_id=period.name,
            outcome=AuditOutcome.SUCCESS,
            notes=f"Reopened financial period {period.name}. Reason: {reason or 'Administrative correction'}",
        )
        return period

    @classmethod
    def get_income_and_expenditure(cls, start_date=None, end_date=None):
        """
        Computes Income & Expenditure statement directly from posted JournalLines.
        """
        line_filter = models.Q()
        if start_date:
            line_filter &= models.Q(journal_entry__date__gte=start_date)
        if end_date:
            line_filter &= models.Q(journal_entry__date__lte=end_date)

        def _summarize(acc_type):
            rows = []
            total = Decimal('0.00')
            for acc in Account.objects.filter(type=acc_type, is_active=True).order_by('code'):
                qs = acc.journal_lines.filter(line_filter)
                dr = qs.aggregate(s=models.Sum('debit'))['s'] or Decimal('0.00')
                cr = qs.aggregate(s=models.Sum('credit'))['s'] or Decimal('0.00')
                bal = (cr - dr) if acc_type == AccountType.REVENUE else (dr - cr)
                total += bal
                rows.append({'code': acc.code, 'name': acc.name, 'amount': bal})
            return rows, total

        revenue_rows, total_revenue = _summarize(AccountType.REVENUE)
        expense_rows, total_expenses = _summarize(AccountType.EXPENSE)
        net_surplus = total_revenue - total_expenses
        return {
            'start_date': start_date,
            'end_date': end_date,
            'revenues': revenue_rows,
            'expenses': expense_rows,
            'total_revenue': total_revenue,
            'total_expenses': total_expenses,
            'net_surplus': net_surplus,
        }

    @classmethod
    def get_balance_sheet(cls, as_of_date=None):
        """
        Computes Balance Sheet directly from posted JournalLines up to `as_of_date`.
        Includes current-period Net Surplus inside Equity so Assets == Liabilities + Equity.
        """
        date_filter = models.Q(journal_entry__date__lte=as_of_date) if as_of_date else models.Q()

        def _summarize(acc_type):
            rows = []
            total = Decimal('0.00')
            for acc in Account.objects.filter(type=acc_type, is_active=True).order_by('code'):
                qs = acc.journal_lines.filter(date_filter)
                dr = qs.aggregate(s=models.Sum('debit'))['s'] or Decimal('0.00')
                cr = qs.aggregate(s=models.Sum('credit'))['s'] or Decimal('0.00')
                bal = (dr - cr) if acc_type == AccountType.ASSET else (cr - dr)
                total += bal
                rows.append({'code': acc.code, 'name': acc.name, 'balance': bal})
            return rows, total

        assets, total_assets = _summarize(AccountType.ASSET)
        liabilities, total_liabilities = _summarize(AccountType.LIABILITY)
        equity, total_equity_accounts = _summarize(AccountType.EQUITY)

        ie = cls.get_income_and_expenditure(end_date=as_of_date)
        net_surplus = ie['net_surplus']
        total_equity = total_equity_accounts + net_surplus
        total_liabilities_and_equity = total_liabilities + total_equity

        return {
            'as_of_date': as_of_date or timezone.localdate(),
            'assets': assets,
            'liabilities': liabilities,
            'equity': equity,
            'net_surplus': net_surplus,
            'total_assets': total_assets,
            'total_liabilities': total_liabilities,
            'total_equity': total_equity,
            'total_liabilities_and_equity': total_liabilities_and_equity,
            'is_balanced': total_assets == total_liabilities_and_equity,
        }
