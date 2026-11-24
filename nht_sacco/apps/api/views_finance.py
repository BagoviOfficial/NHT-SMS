from decimal import Decimal
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from nht_sacco.apps.accounts.models import UserRole
from nht_sacco.apps.accounts.permissions import (
    FINANCE_CHECKER_ROLES,
    FINANCE_STAFF_ROLES,
    role_permission_factory,
)
from nht_sacco.apps.accounting.models import Account, Expense, FinancialPeriod, JournalEntry
from nht_sacco.apps.accounting.services import AccountingService
from nht_sacco.apps.audit.models import AuditAction, AuditLog, AuditOutcome
from nht_sacco.apps.billing.models import CreditNote, Invoice, InvoiceItem, InvoiceStatus, ServiceItem
from nht_sacco.apps.members.models import Member
from nht_sacco.apps.payments.daraja import DarajaClient
from nht_sacco.apps.payments.models import (
    ManualPaymentVoucher,
    Payment,
    PaymentMethod,
    PaymentStatus,
    Receipt,
    ReconciliationException,
    ReconciliationRun,
)
from nht_sacco.apps.payments.reconciliation import PaymentReconciliationService
from .serializers import (
    AccountSerializer,
    ExpenseSerializer,
    FinancialPeriodSerializer,
    InvoiceSerializer,
    JournalEntrySerializer,
    ManualPaymentVoucherSerializer,
    PaymentSerializer,
    ReceiptSerializer,
    ReconciliationExceptionSerializer,
    ReconciliationRunSerializer,
    ServiceItemSerializer,
)

FinanceWriteOrAuditorRead = role_permission_factory(FINANCE_STAFF_ROLES | {UserRole.CHAIRMAN}, allow_auditor_read=True)
FinanceOrMemberAccess = role_permission_factory(FINANCE_STAFF_ROLES | {UserRole.CHAIRMAN, UserRole.SECRETARY, UserRole.MEMBER}, allow_auditor_read=True)


class ServiceItemViewSet(viewsets.ModelViewSet):
    queryset = ServiceItem.objects.all().order_by('category', 'name')
    serializer_class = ServiceItemSerializer
    permission_classes = [role_permission_factory(FINANCE_STAFF_ROLES | {UserRole.CHAIRMAN}, allow_auditor_read=True)]
    filterset_fields = ['category', 'is_statutory', 'is_active']
    search_fields = ['code', 'name']

    def get_permissions(self):
        if self.request.method in ('GET', 'HEAD', 'OPTIONS'):
            return [IsAuthenticated()]
        return [FinanceWriteOrAuditorRead()]


class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.select_related('member', 'vehicle').prefetch_related('line_items__service_item').order_by('-issue_date', '-created_at')
    serializer_class = InvoiceSerializer
    permission_classes = [FinanceOrMemberAccess]
    filterset_fields = ['status', 'member', 'vehicle']
    search_fields = ['invoice_number', 'member__first_name', 'member__last_name', 'member__membership_number']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == UserRole.MEMBER and hasattr(user, 'member_profile'):
            return qs.filter(member=user.member_profile)
        return qs

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        if request.user.role in (UserRole.MEMBER, UserRole.DRIVER, UserRole.AUDITOR) and not request.user.is_superuser:
            return Response({'error': 'Insufficient privileges to create invoices.'}, status=status.HTTP_403_FORBIDDEN)

        member_id = request.data.get('member')
        vehicle_id = request.data.get('vehicle') or None
        due_date = request.data.get('due_date') or (timezone.localdate() + timezone.timedelta(days=14))
        notes = request.data.get('notes', '')
        items_payload = request.data.get('items', [])

        if not member_id or not items_payload:
            return Response({'error': 'Member and at least one service line item are required.'}, status=status.HTTP_400_BAD_REQUEST)

        member = Member.objects.filter(pk=member_id).first()
        if not member:
            return Response({'error': 'Selected member not found.'}, status=status.HTTP_404_NOT_FOUND)

        invoice = Invoice.objects.create(
            invoice_number=Invoice.generate_invoice_number(),
            member=member,
            vehicle_id=vehicle_id,
            issue_date=timezone.localdate(),
            due_date=due_date,
            notes=notes,
            created_by=request.user,
        )
        for item in items_payload:
            svc = ServiceItem.objects.get(pk=item['service_item'])
            qty = int(item.get('quantity', 1))
            tier = svc.price_tiers.order_by('-effective_from').first()
            fallback_amt = tier.amount if tier else Decimal('0.00')
            unit_price = Decimal(str(item.get('unit_price', fallback_amt)))
            InvoiceItem.objects.create(
                invoice=invoice,
                service_item=svc,
                description=item.get('description') or svc.name,
                unit_price=unit_price,
                quantity=qty,
            )
        invoice.recalculate_totals()
        try:
            AccountingService.post_invoice_issuance(invoice, user=request.user)
        except Exception:
            pass

        AuditLog.log_action(
            actor=request.user,
            action=AuditAction.CREATE,
            entity_type='Invoice',
            entity_id=invoice.invoice_number,
            outcome=AuditOutcome.SUCCESS,
            notes=f"Issued invoice {invoice.invoice_number} for KES {invoice.total_amount}",
        )
        return Response(InvoiceSerializer(invoice).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def pay_stk(self, request, pk=None):
        invoice = self.get_object()
        user = request.user
        if user.role == UserRole.MEMBER and hasattr(user, 'member_profile') and invoice.member != user.member_profile:
            return Response({'error': 'Access Denied: You do not own this invoice.'}, status=status.HTTP_403_FORBIDDEN)
        if invoice.is_fully_paid:
            return Response({'error': 'Invoice is already settled in full.'}, status=status.HTTP_400_BAD_REQUEST)

        phone = (request.data.get('phone_number') or invoice.member.phone_number or '').strip()
        if not phone:
            return Response({'error': 'Phone number is required for M-Pesa STK Push.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            res = DarajaClient().initiate_stk_push(
                phone_number=phone,
                amount=invoice.balance_due,
                invoice=invoice,
                account_reference=invoice.invoice_number,
                transaction_desc=f"NHT {invoice.invoice_number[-8:]}",
            )
            if str(res.get('ResponseCode')) == '0':
                return Response({'success': True, 'data': res}, status=status.HTTP_200_OK)
            return Response({'error': res.get('CustomerMessage') or res.get('ResponseDescription') or 'STK Push failed.'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def issue_credit_note(self, request, pk=None):
        if not (request.user.is_superuser or request.user.role in FINANCE_CHECKER_ROLES):
            return Response({'error': 'Finance Checker clearance required.'}, status=status.HTTP_403_FORBIDDEN)
        invoice = self.get_object()
        amount = Decimal(str(request.data.get('amount', '0.00')))
        reason = (request.data.get('reason') or '').strip()
        if amount <= Decimal('0.00') or not reason:
            return Response({'error': 'Positive credit amount and reason are required.'}, status=status.HTTP_400_BAD_REQUEST)
        cn = CreditNote.objects.create(
            credit_number=CreditNote.generate_credit_number(),
            invoice=invoice,
            amount=amount,
            reason=reason,
            authorized_by=request.user,
        )
        invoice.allocate_payment(amount)
        AuditLog.log_action(
            actor=request.user,
            action=AuditAction.CREATE,
            entity_type='CreditNote',
            entity_id=cn.credit_number,
            outcome=AuditOutcome.SUCCESS,
            notes=f"Credit note {cn.credit_number} (KES {amount}) applied to {invoice.invoice_number}",
        )
        return Response({'credit_number': cn.credit_number, 'invoice': InvoiceSerializer(invoice).data})


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Payment.objects.select_related('invoice', 'member', 'receipt').order_by('-created_at')
    serializer_class = PaymentSerializer
    permission_classes = [FinanceOrMemberAccess]
    filterset_fields = ['status', 'method', 'member']
    search_fields = ['payment_reference', 'provider_transaction_id', 'invoice__invoice_number']

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.role == UserRole.MEMBER and hasattr(self.request.user, 'member_profile'):
            return qs.filter(member=self.request.user.member_profile)
        return qs


class ReceiptViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Receipt.objects.select_related('payment', 'payment__invoice', 'payment__member').order_by('-issued_at')
    serializer_class = ReceiptSerializer
    permission_classes = [FinanceOrMemberAccess]
    search_fields = ['receipt_number', 'payment__payment_reference', 'payment__invoice__invoice_number']

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.role == UserRole.MEMBER and hasattr(self.request.user, 'member_profile'):
            return qs.filter(payment__member=self.request.user.member_profile)
        return qs


class ManualPaymentVoucherViewSet(viewsets.ModelViewSet):
    queryset = ManualPaymentVoucher.objects.select_related('invoice', 'member', 'entered_by', 'verified_by').order_by('-created_at')
    serializer_class = ManualPaymentVoucherSerializer
    permission_classes = [role_permission_factory(FINANCE_CHECKER_ROLES | {UserRole.SECRETARY, UserRole.FIELD_OFFICER}, allow_auditor_read=True)]
    filterset_fields = ['status', 'method']
    search_fields = ['bank_slip_reference', 'bank_name', 'invoice__invoice_number']

    def perform_create(self, serializer):
        invoice = serializer.validated_data['invoice']
        voucher = serializer.save(
            member=invoice.member,
            entered_by=self.request.user,
            status=ManualPaymentVoucher.Status.PENDING,
        )
        AuditLog.log_action(
            actor=self.request.user,
            action=AuditAction.CREATE,
            entity_type='ManualPaymentVoucher',
            entity_id=str(voucher.pk),
            outcome=AuditOutcome.SUCCESS,
            notes=f"Maker submitted voucher {voucher.bank_slip_reference} for KES {voucher.amount}",
        )

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def approve(self, request, pk=None):
        if not (request.user.is_superuser or request.user.role in FINANCE_CHECKER_ROLES):
            return Response({'error': 'Finance Checker clearance required.'}, status=status.HTTP_403_FORBIDDEN)
        voucher = self.get_object()
        if voucher.status != ManualPaymentVoucher.Status.PENDING:
            return Response({'error': f"Voucher is already {voucher.status}."}, status=status.HTTP_400_BAD_REQUEST)
        if voucher.entered_by_id == request.user.id:
            return Response({'error': 'Maker-Checker violation: You cannot approve a voucher you entered.'}, status=status.HTTP_403_FORBIDDEN)

        voucher.status = ManualPaymentVoucher.Status.VERIFIED
        voucher.verified_by = request.user
        voucher.verified_at = timezone.now()
        voucher.verification_notes = request.data.get('notes', '')
        voucher.save()

        payment = Payment.objects.create(
            payment_reference=Payment.generate_payment_reference(),
            invoice=voucher.invoice,
            member=voucher.member,
            method=PaymentMethod.BANK_TRANSFER if voucher.method == 'BANK_TRANSFER' else PaymentMethod.CASH,
            amount=voucher.amount,
            idempotency_key=f"MANUAL_{voucher.id}",
            status=PaymentStatus.INITIATED,
            phone_number=voucher.member.phone_number,
            confirmed_at=timezone.now(),
        )
        settlement = AccountingService.record_payment_settlement(
            payment=payment,
            amount=voucher.amount,
            provider_transaction_id=voucher.bank_slip_reference,
            user=request.user,
            notes=f"Manual voucher verified via SPA by {request.user.username}",
        )
        return Response({
            'voucher': ManualPaymentVoucherSerializer(voucher).data,
            'receipt_number': settlement['receipt'].receipt_number if settlement.get('receipt') else None,
        })

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        if not (request.user.is_superuser or request.user.role in FINANCE_CHECKER_ROLES):
            return Response({'error': 'Finance Checker clearance required.'}, status=status.HTTP_403_FORBIDDEN)
        voucher = self.get_object()
        if voucher.status != ManualPaymentVoucher.Status.PENDING:
            return Response({'error': f"Voucher is already {voucher.status}."}, status=status.HTTP_400_BAD_REQUEST)
        if voucher.entered_by_id == request.user.id:
            return Response({'error': 'Maker-Checker violation: You cannot reject a voucher you entered.'}, status=status.HTTP_403_FORBIDDEN)

        voucher.status = ManualPaymentVoucher.Status.REJECTED
        voucher.verified_by = request.user
        voucher.verified_at = timezone.now()
        voucher.verification_notes = request.data.get('notes', '')
        voucher.save()
        return Response(ManualPaymentVoucherSerializer(voucher).data)


class ReconciliationRunViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ReconciliationRun.objects.prefetch_related('exceptions').order_by('-created_at')
    serializer_class = ReconciliationRunSerializer
    permission_classes = [FinanceWriteOrAuditorRead]

    @action(detail=False, methods=['post'])
    def execute(self, request):
        if not (request.user.is_superuser or request.user.role in FINANCE_CHECKER_ROLES):
            return Response({'error': 'Finance staff clearance required to trigger reconciliation.'}, status=status.HTTP_403_FORBIDDEN)
        run = PaymentReconciliationService.run_reconciliation(
            user=request.user,
            period_start=request.data.get('period_start') or None,
            period_end=request.data.get('period_end') or None,
            auto_recover_daraja=bool(request.data.get('auto_recover_daraja', False)),
            notes=request.data.get('notes', ''),
        )
        return Response(ReconciliationRunSerializer(run).data, status=status.HTTP_201_CREATED)


class ReconciliationExceptionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ReconciliationException.objects.select_related('run', 'payment', 'invoice').order_by('-created_at')
    serializer_class = ReconciliationExceptionSerializer
    permission_classes = [FinanceWriteOrAuditorRead]
    filterset_fields = ['status', 'exception_type', 'severity']

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        if not (request.user.is_superuser or request.user.role in FINANCE_CHECKER_ROLES):
            return Response({'error': 'Finance staff clearance required.'}, status=status.HTTP_403_FORBIDDEN)
        exc = self.get_object()
        try:
            updated = PaymentReconciliationService.resolve_exception(
                exception_obj=exc,
                user=request.user,
                resolution_notes=request.data.get('resolution_notes', ''),
                status=request.data.get('status', ReconciliationException.Status.RESOLVED),
            )
            return Response(ReconciliationExceptionSerializer(updated).data)
        except DjangoValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class MemberStatementAPIView(APIView):
    permission_classes = [FinanceOrMemberAccess]

    def get(self, request):
        user = request.user
        member_id = request.query_params.get('member_id')
        if user.role == UserRole.MEMBER and hasattr(user, 'member_profile'):
            member = user.member_profile
        elif member_id:
            member = Member.objects.filter(pk=member_id).first()
            if not member:
                return Response({'error': 'Member not found.'}, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response({'error': 'member_id query parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)

        invoices = member.invoices.all().order_by('issue_date', 'created_at')
        payments = Payment.objects.filter(invoice__member=member, status=PaymentStatus.SUCCESS).select_related('invoice').order_by('confirmed_at', 'created_at')

        entries = []
        for inv in invoices:
            entries.append({
                'date': str(inv.issue_date),
                'timestamp': inv.created_at.isoformat(),
                'type': 'INVOICE',
                'reference': inv.invoice_number,
                'description': f"Invoice for {inv.vehicle.registration_number if inv.vehicle else 'SACCO Services'}",
                'debit': str(inv.total_amount),
                'credit': '0.00',
            })
        for p in payments:
            dt = p.confirmed_at.date() if p.confirmed_at else p.created_at.date()
            ts = p.confirmed_at or p.created_at
            entries.append({
                'date': str(dt),
                'timestamp': ts.isoformat(),
                'type': 'PAYMENT',
                'reference': p.provider_transaction_id or p.payment_reference,
                'description': f"Settlement towards {p.invoice.invoice_number} ({p.get_method_display()})",
                'debit': '0.00',
                'credit': str(p.amount),
            })

        entries.sort(key=lambda x: (x['date'], x['timestamp']))
        bal = Decimal('0.00')
        total_dr = Decimal('0.00')
        total_cr = Decimal('0.00')
        for e in entries:
            dr = Decimal(e['debit'])
            cr = Decimal(e['credit'])
            bal += (dr - cr)
            total_dr += dr
            total_cr += cr
            e['running_balance'] = str(bal)

        return Response({
            'member_name': member.full_name,
            'membership_number': member.membership_number,
            'entries': entries,
            'total_debits': str(total_dr),
            'total_credits': str(total_cr),
            'current_balance': str(bal),
        })


class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.all().order_by('code')
    serializer_class = AccountSerializer
    permission_classes = [FinanceWriteOrAuditorRead]
    filterset_fields = ['type', 'is_active']
    search_fields = ['code', 'name']


class FinancialPeriodViewSet(viewsets.ModelViewSet):
    queryset = FinancialPeriod.objects.all().order_by('-start_date')
    serializer_class = FinancialPeriodSerializer
    permission_classes = [FinanceWriteOrAuditorRead]

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        if not (request.user.is_superuser or request.user.role in FINANCE_CHECKER_ROLES):
            return Response({'error': 'Finance Checker clearance required.'}, status=status.HTTP_403_FORBIDDEN)
        period = AccountingService.close_period(self.get_object(), user=request.user)
        return Response(FinancialPeriodSerializer(period).data)

    @action(detail=True, methods=['post'])
    def reopen(self, request, pk=None):
        if not (request.user.is_superuser or request.user.role in (UserRole.SUPER_ADMIN, UserRole.CHAIRMAN, UserRole.TREASURER)):
            return Response({'error': 'Senior Finance / Chairman clearance required.'}, status=status.HTTP_403_FORBIDDEN)
        period = AccountingService.reopen_period(self.get_object(), user=request.user, reason=request.data.get('reason', ''))
        return Response(FinancialPeriodSerializer(period).data)


class JournalEntryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = JournalEntry.objects.select_related('period', 'posted_by').prefetch_related('lines__account').order_by('-date', '-created_at')
    serializer_class = JournalEntrySerializer
    permission_classes = [FinanceWriteOrAuditorRead]
    filterset_fields = ['period', 'is_reversal']
    search_fields = ['entry_number', 'reference', 'narration']

    def create(self, request, *args, **kwargs):
        if not (request.user.is_superuser or request.user.role in FINANCE_STAFF_ROLES):
            return Response({'error': 'Finance staff clearance required to post journals.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            entry = AccountingService.post_manual_journal(
                date_val=request.data.get('date') or None,
                reference=request.data.get('reference', ''),
                narration=request.data.get('narration', ''),
                lines_data=request.data.get('lines', []),
                user=request.user,
            )
            return Response(JournalEntrySerializer(entry).data, status=status.HTTP_201_CREATED)
        except (DjangoValidationError, Exception) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def reverse(self, request, pk=None):
        if not (request.user.is_superuser or request.user.role in FINANCE_CHECKER_ROLES):
            return Response({'error': 'Finance Checker clearance required to reverse entries.'}, status=status.HTTP_403_FORBIDDEN)
        reason = (request.data.get('reason') or '').strip()
        if not reason:
            return Response({'error': 'Reversal reason is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            rev = AccountingService.reverse_journal_entry(self.get_object(), user=request.user, reason=reason)
            return Response(JournalEntrySerializer(rev).data, status=status.HTTP_201_CREATED)
        except DjangoValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ExpenseViewSet(viewsets.ModelViewSet):
    queryset = Expense.objects.select_related('category', 'payment_account', 'recorded_by', 'approved_by').order_by('-date', '-created_at')
    serializer_class = ExpenseSerializer
    permission_classes = [FinanceWriteOrAuditorRead]
    filterset_fields = ['status']
    search_fields = ['expense_number', 'payee', 'description']

    def perform_create(self, serializer):
        expense = serializer.save(
            expense_number=Expense.generate_expense_number(),
            recorded_by=self.request.user,
            status='PENDING',
        )
        AuditLog.log_action(
            actor=self.request.user,
            action=AuditAction.CREATE,
            entity_type='Expense',
            entity_id=expense.expense_number,
            outcome=AuditOutcome.SUCCESS,
            notes=f"Recorded expense claim {expense.expense_number} for KES {expense.amount}",
        )

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        if not (request.user.is_superuser or request.user.role in FINANCE_CHECKER_ROLES):
            return Response({'error': 'Finance Checker clearance required.'}, status=status.HTTP_403_FORBIDDEN)
        expense = self.get_object()
        if expense.status != 'PENDING':
            return Response({'error': f"Expense is already {expense.status}."}, status=status.HTTP_400_BAD_REQUEST)
        if expense.recorded_by_id == request.user.id:
            return Response({'error': 'Maker-Checker violation: You cannot approve an expense you recorded.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            AccountingService.post_expense(expense, user=request.user)
            return Response(ExpenseSerializer(expense).data)
        except DjangoValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        if not (request.user.is_superuser or request.user.role in FINANCE_CHECKER_ROLES):
            return Response({'error': 'Finance Checker clearance required.'}, status=status.HTTP_403_FORBIDDEN)
        expense = self.get_object()
        if expense.status != 'PENDING':
            return Response({'error': f"Expense is already {expense.status}."}, status=status.HTTP_400_BAD_REQUEST)
        if expense.recorded_by_id == request.user.id:
            return Response({'error': 'Maker-Checker violation: You cannot reject your own expense.'}, status=status.HTTP_403_FORBIDDEN)
        expense.status = 'REJECTED'
        expense.approved_by = request.user
        expense.approved_at = timezone.now()
        expense.save(update_fields=['status', 'approved_by', 'approved_at'])
        return Response(ExpenseSerializer(expense).data)


class FinancialReportsAPIView(APIView):
    permission_classes = [FinanceWriteOrAuditorRead]

    def get(self, request):
        start_date = request.query_params.get('start_date') or None
        end_date = request.query_params.get('end_date') or None
        as_of_date = request.query_params.get('as_of_date') or None

        tb = AccountingService.get_trial_balance()
        ie = AccountingService.get_income_and_expenditure(start_date=start_date, end_date=end_date)
        bs = AccountingService.get_balance_sheet(as_of_date=as_of_date)

        def _fmt(obj):
            if isinstance(obj, Decimal):
                return str(obj)
            if isinstance(obj, list):
                return [_fmt(i) for i in obj]
            if isinstance(obj, dict):
                return {k: _fmt(v) for k, v in obj.items()}
            return obj

        return Response(_fmt({
            'trial_balance': tb,
            'income_and_expenditure': ie,
            'balance_sheet': bs,
        }))
