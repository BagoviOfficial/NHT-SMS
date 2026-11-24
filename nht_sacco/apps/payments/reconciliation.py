from decimal import Decimal
from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone
from django.core.exceptions import ValidationError

from .models import (
    Payment,
    PaymentStatus,
    Receipt,
    ReconciliationRun,
    ReconciliationException,
)
from nht_sacco.apps.billing.models import Invoice, InvoiceStatus
from nht_sacco.apps.accounting.models import JournalEntry
from nht_sacco.apps.audit.models import AuditLog, AuditAction, AuditOutcome


class PaymentReconciliationService:
    """
    Stage 12 Financial Integrity & Payment Reconciliation Engine.
    Cross-checks M-Pesa / Manual Payments, Receipts, Invoices, and GL Journal Entries.
    Never discards unmatched records; logs structured exceptions for Finance review.
    """

    @classmethod
    @transaction.atomic
    def run_reconciliation(
        cls,
        user=None,
        period_start=None,
        period_end=None,
        auto_recover_daraja=False,
        notes='',
    ):
        payments_qs = Payment.objects.select_related('invoice', 'member').all()
        if period_start:
            payments_qs = payments_qs.filter(created_at__date__gte=period_start)
        if period_end:
            payments_qs = payments_qs.filter(created_at__date__lte=period_end)

        run = ReconciliationRun.objects.create(
            run_reference=ReconciliationRun.generate_run_reference(),
            executed_by=user if (user and getattr(user, 'is_authenticated', False)) else None,
            period_start=period_start,
            period_end=period_end,
            notes=notes,
        )

        matched_count = 0
        total_matched_amount = Decimal('0.00')
        exceptions_created = []

        # 1. Check duplicate provider transaction references
        dup_refs = (
            payments_qs.exclude(provider_transaction_id__isnull=True)
            .exclude(provider_transaction_id='')
            .values('provider_transaction_id')
            .annotate(cnt=Count('id'))
            .filter(cnt__gt=1)
        )
        for dup in dup_refs:
            ref = dup['provider_transaction_id']
            exc = ReconciliationException.objects.create(
                run=run,
                exception_type=ReconciliationException.ExceptionType.DUPLICATE_PROVIDER_REF,
                severity='HIGH',
                description=f"Provider reference '{ref}' appears {dup['cnt']} times across payment records.",
            )
            exceptions_created.append(exc)

        # 2. Check each Payment against Receipt and GL JournalEntry
        for payment in payments_qs:
            if payment.status == PaymentStatus.INITIATED:
                recovered = False
                if auto_recover_daraja and payment.idempotency_key:
                    try:
                        from .daraja import DarajaClient
                        res = DarajaClient().query_transaction_status(payment.idempotency_key)
                        if str(res.get('ResultCode')) == '0':
                            recovered = True
                    except Exception:
                        recovered = False
                if not recovered:
                    exc = ReconciliationException.objects.create(
                        run=run,
                        payment=payment,
                        invoice=payment.invoice,
                        exception_type=ReconciliationException.ExceptionType.UNMATCHED_INITIATED,
                        severity='MEDIUM',
                        description=(
                            f"Payment {payment.payment_reference} (KES {payment.amount}) remains in INITIATED state "
                            f"for invoice {payment.invoice.invoice_number}."
                        ),
                    )
                    exceptions_created.append(exc)
                continue

            if payment.status == PaymentStatus.SUCCESS:
                has_receipt = Receipt.objects.filter(payment=payment).exists()
                has_journal = JournalEntry.objects.filter(reference=payment.payment_reference).exists()
                is_clean = True

                if not has_receipt:
                    is_clean = False
                    exceptions_created.append(
                        ReconciliationException.objects.create(
                            run=run,
                            payment=payment,
                            invoice=payment.invoice,
                            exception_type=ReconciliationException.ExceptionType.MISSING_RECEIPT,
                            severity='HIGH',
                            description=f"Settled payment {payment.payment_reference} has no issued Receipt.",
                        )
                    )
                if not has_journal:
                    is_clean = False
                    exceptions_created.append(
                        ReconciliationException.objects.create(
                            run=run,
                            payment=payment,
                            invoice=payment.invoice,
                            exception_type=ReconciliationException.ExceptionType.MISSING_JOURNAL,
                            severity='CRITICAL',
                            description=f"Settled payment {payment.payment_reference} has no matching General Ledger JournalEntry.",
                        )
                    )
                if is_clean:
                    matched_count += 1
                    total_matched_amount += payment.amount

        # 3. Check Invoice-level totals vs confirmed Payments (underpayment / overpayment / mismatch)
        invoices_qs = Invoice.objects.exclude(status=InvoiceStatus.CANCELLED)
        for inv in invoices_qs:
            settled_sum = (
                inv.payments.filter(status=PaymentStatus.SUCCESS).aggregate(s=Sum('amount'))['s']
                or Decimal('0.00')
            )
            if settled_sum > inv.total_amount and inv.total_amount > Decimal('0.00'):
                exceptions_created.append(
                    ReconciliationException.objects.create(
                        run=run,
                        invoice=inv,
                        exception_type=ReconciliationException.ExceptionType.OVERPAYMENT,
                        severity='HIGH',
                        description=(
                            f"Invoice {inv.invoice_number} total is KES {inv.total_amount} "
                            f"but confirmed payments total KES {settled_sum}."
                        ),
                    )
                )
            elif Decimal('0.00') < settled_sum < inv.total_amount:
                exceptions_created.append(
                    ReconciliationException.objects.create(
                        run=run,
                        invoice=inv,
                        exception_type=ReconciliationException.ExceptionType.UNDERPAYMENT,
                        severity='LOW',
                        description=(
                            f"Invoice {inv.invoice_number} has partial payments KES {settled_sum} "
                            f"against total KES {inv.total_amount} (Balance KES {inv.balance_due})."
                        ),
                    )
                )
            if settled_sum != inv.amount_paid:
                exceptions_created.append(
                    ReconciliationException.objects.create(
                        run=run,
                        invoice=inv,
                        exception_type=ReconciliationException.ExceptionType.AMOUNT_MISMATCH,
                        severity='CRITICAL',
                        description=(
                            f"Invoice {inv.invoice_number} amount_paid (KES {inv.amount_paid}) differs from "
                            f"confirmed payments sum (KES {settled_sum})."
                        ),
                    )
                )

        run.total_payments_checked = payments_qs.count()
        run.matched_count = matched_count
        run.exception_count = len(exceptions_created)
        run.total_matched_amount = total_matched_amount
        run.save(
            update_fields=[
                'total_payments_checked',
                'matched_count',
                'exception_count',
                'total_matched_amount',
            ]
        )

        AuditLog.log_action(
            actor=user if (user and getattr(user, 'is_authenticated', False)) else None,
            action=AuditAction.SYSTEM,
            entity_type='ReconciliationRun',
            entity_id=run.run_reference,
            outcome=AuditOutcome.SUCCESS,
            notes=f"Reconciliation completed: {matched_count} matched, {len(exceptions_created)} exceptions",
        )
        return run

    @classmethod
    @transaction.atomic
    def resolve_exception(cls, exception_obj: ReconciliationException, user, resolution_notes='', status='RESOLVED'):
        if status not in (ReconciliationException.Status.RESOLVED, ReconciliationException.Status.IGNORED):
            raise ValidationError("Invalid exception resolution status.")
        exception_obj.status = status
        exception_obj.resolution_notes = resolution_notes
        exception_obj.resolved_by = user
        exception_obj.resolved_at = timezone.now()
        exception_obj.save(update_fields=['status', 'resolution_notes', 'resolved_by', 'resolved_at'])

        AuditLog.log_action(
            actor=user,
            action=AuditAction.APPROVE,
            entity_type='ReconciliationException',
            entity_id=str(exception_obj.pk),
            outcome=AuditOutcome.SUCCESS,
            notes=f"Marked reconciliation exception {exception_obj.exception_type} as {status}: {resolution_notes}",
        )
        return exception_obj
