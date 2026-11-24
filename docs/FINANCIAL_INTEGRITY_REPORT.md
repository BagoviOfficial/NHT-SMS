# Financial Integrity & Payment Reconciliation Report — NHT-SMS (Stage 12)

**System:** Northern Highways Transporters SACCO Management System (NHT-SMS)  
**Module Scope:** `payments`, `billing`, `accounting`, `renewals`, `integrations`  

---

## 1. Payment & Ledger Controls

1. **Row-Level Locking & Idempotency (`AccountingService.record_payment_settlement`):**
   - Acquires `select_for_update()` locks on `Payment` and `Invoice` before validating payment state (`INITIATED` / `PENDING`).
   - Enforces uniqueness of `provider_transaction_id` across payment records and idempotent `JournalEntry` posting keyed by `payment.payment_reference`.
   - Automatically transitions linked `RenewalRequest` records from `INVOICED` to `PAID` when `invoice.is_fully_paid` becomes `True`.
2. **Financial Period Enforcement (`AccountingService`):**
   - Rejects postings (`ValidationError`) targeting closed `FinancialPeriod` windows.
   - Provides audited `close_period()` and `reopen_period()` operations for authorized Finance officers.
3. **Maker-Checker Segregation of Duties:**
   - Enforced on `ManualPaymentVoucher` (`entered_by != verified_by`), `Expense` (`recorded_by != approved_by`), and `ConfigurationChangeRequest` (`requested_by != reviewed_by`).
4. **General Ledger Financial Statements:**
   - `get_trial_balance()`, `get_income_and_expenditure()`, and `get_balance_sheet()` compute all totals directly from posted `JournalLine` entries, preserving $\text{Assets} = \text{Liabilities} + \text{Equity} + \text{Net Surplus}$.

---

## 2. Automated Payment Reconciliation Engine (`PaymentReconciliationService`)

Executed via `POST /api/v1/reconciliation-runs/execute/` or `PaymentReconciliationService.run_reconciliation()`:
- Checks duplicate `provider_transaction_id` references across `Payment` rows.
- Flags stale `INITIATED` payments (with optional Daraja `query_transaction_status()` recovery) as `UNMATCHED_INITIATED` exceptions.
- Verifies every `SUCCESS` payment has both an issued `Receipt` (`MISSING_RECEIPT`) and a General Ledger `JournalEntry` (`MISSING_JOURNAL`).
- Reconciles confirmed payment sums against `Invoice.total_amount` and `Invoice.amount_paid` (`UNDERPAYMENT`, `OVERPAYMENT`, `AMOUNT_MISMATCH`).
- Preserves unmatched records and records structured `ReconciliationException` items for Finance review and audited resolution.
