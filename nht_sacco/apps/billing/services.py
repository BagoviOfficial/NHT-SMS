"""
Shared billing statement generation service used by both Member Portal and REST API.
"""

from decimal import Decimal
from nht_sacco.apps.payments.models import Payment, PaymentStatus


class BillingStatementService:
    @staticmethod
    def build_member_statement(member):
        """
        Builds a chronological ledger of invoices (debits) and confirmed payments
        (credits) with running balances for the given Member.
        """
        invoices = member.invoices.all().order_by('issue_date', 'created_at')
        payments = (
            Payment.objects.filter(invoice__member=member, status=PaymentStatus.SUCCESS)
            .select_related('invoice')
            .order_by('confirmed_at', 'created_at')
        )

        entries = []
        for inv in invoices:
            entries.append({
                'date': inv.issue_date,
                'date_iso': str(inv.issue_date),
                'timestamp': inv.created_at,
                'timestamp_iso': inv.created_at.isoformat(),
                'type': 'INVOICE',
                'reference': inv.invoice_number,
                'description': f"Invoice for {inv.vehicle.registration_number if inv.vehicle else 'SACCO Services'}",
                'debit': inv.total_amount,
                'credit': Decimal('0.00'),
            })

        for pay in payments:
            dt = pay.confirmed_at.date() if pay.confirmed_at else pay.created_at.date()
            ts = pay.confirmed_at or pay.created_at
            entries.append({
                'date': dt,
                'date_iso': str(dt),
                'timestamp': ts,
                'timestamp_iso': ts.isoformat(),
                'type': 'PAYMENT',
                'reference': pay.provider_transaction_id or pay.payment_reference,
                'description': f"Settlement towards {pay.invoice.invoice_number} ({pay.get_method_display()})",
                'debit': Decimal('0.00'),
                'credit': pay.amount,
            })

        entries.sort(key=lambda x: (x['date'], x['timestamp']))

        running_bal = Decimal('0.00')
        total_debits = Decimal('0.00')
        total_credits = Decimal('0.00')

        for entry in entries:
            running_bal += entry['debit'] - entry['credit']
            total_debits += entry['debit']
            total_credits += entry['credit']
            entry['running_balance'] = running_bal

        return {
            'member_name': member.full_name,
            'membership_number': member.membership_number,
            'entries': entries,
            'total_debits': total_debits,
            'total_credits': total_credits,
            'current_balance': running_bal,
        }
