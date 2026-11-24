# User Roles, Permissions & Segregation of Duties — NHT-SMS

**System:** Northern Highways Transporters SACCO Management System (NHT-SMS)  
**Security Standard:** Principle of Least Privilege & OWASP ASVS Level 2  
**Framework:** Django Group & Permission Engine with Hardened Object-Level RBAC  

---

## 1. System Role Hierarchy & Definitions

NHT-SMS enforces strict Role-Based Access Control (RBAC) spanning 11 discrete operational and self-service personas (`UserRole` in `nht_sacco/apps/accounts/models.py`, enforced via `nht_sacco/apps/accounts/permissions.py`):

| Role Identifier | Role Title | `is_staff` | Functional Scope |
|---|---|---|---|
| `SUPER_ADMIN` | Super Administrator | `True` | System configuration, backups, user provisioning, role allocation, security diagnostics. |
| `CHAIRMAN` | SACCO Chairman | `True` | Governance, executive dashboards, committee resolutions, configuration & finance checker approvals. |
| `SECRETARY` | SACCO Secretary | `True` | Member onboarding, vehicle/driver/route registry, meetings, incidents, announcements. |
| `TREASURER` | SACCO Treasurer | `True` | Invoicing, payment reconciliation, general ledger, period close/reopen, voucher & expense approval. |
| `ACCOUNTANT` | Accountant | `True` | Invoicing, general ledger journals, expenses, payment reconciliation, financial statements. |
| `COMPLIANCE_OFFICER` | Compliance Officer | `True` | Regulatory document verification, compliance scans, alerts, renewal final completion, incidents. |
| `RENEWAL_OFFICER` | Renewal Officer | `True` | Review renewal applications, generate renewal fee invoices, manage processing queue. |
| `FIELD_OFFICER` | Field Officer | `True` | Field fleet & route registry, driver assignments, maintenance & incident reporting. |
| `AUDITOR` | Auditor | `True` | Strict read-only inspection of audit logs, ledger/financial statements, compliance, and system settings. |
| `MEMBER` | SACCO Member | `False` | Self-service portal (`/portal/` and `/app/#member-portal`): own fleet, invoices, STK Push, statements, renewals. |
| `DRIVER` | PSV Driver | `False` | Self-service driver portal (`/app/#driver-portal`): own DL/PSV badge validity, assigned vehicles, routes, and compliance badges. |

---

## 2. Granular Permissions Matrix

| Functional Capability | `SUPER_ADMIN` | `CHAIRMAN` | `SECRETARY` | `TREASURER` | `ACCOUNTANT` | `COMPLIANCE_OFFICER` | `RENEWAL_OFFICER` | `FIELD_OFFICER` | `AUDITOR` | `MEMBER` | `DRIVER` |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Manage Users & Role Allocation** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Approve Config Change Requests** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ (RO) | ❌ | ❌ |
| **Inspect Immutable Audit Logs** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| **Register / Edit Fleet & Routes** | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| **Verify Regulatory Documents** | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Review & Invoice Renewals** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Issue Invoices & Reconciliation** | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ (RO) | ❌ | ❌ |
| **Approve Manual Vouchers / Expenses** | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **GL Journals & Period Locking** | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ (RO) | ❌ | ❌ |
| **Export Financial Excel Workbook** | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| **Member Portal (`/portal/`, `/app/#member-portal`)** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| **Driver Portal (`/app/#driver-portal`)** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |

---

## 3. Maker-Checker Segregation of Duties

To prevent fraud and accounting manipulation, sensitive operations require independent verification:

### 3.1 Manual Bank Deposit Settlement
1. **Maker (Registry Clerk):** Enters deposit slip number, bank branch, amount, and debtor invoice into `ManualPaymentVoucher` with status `PENDING_VERIFICATION`.
2. **Checker (Finance Officer / SACCO Admin):**
   - Independent verification against physical bank statements or mobile banking portals.
   - Authorizes voucher: changes status to `APPROVED`, atomically allocates payment to invoice balance, generates official receipt, and writes immutable audit log.
   - **Enforced Rule:** A clerk cannot approve their own submitted voucher:
     ```python
     if voucher.recorded_by == request.user:
         raise PermissionDenied("Maker-Checker violation: You cannot approve your own payment voucher.")
     ```

### 3.2 Operating Expense Disbursements
1. **Maker (Clerk / Accountant):** Records expense voucher specifying vendor, chart of accounts debit, and supporting invoice.
2. **Checker (Finance Officer / Treasurer):**
   - Reviews supporting documents.
   - Approves disbursement, triggering automated dual-entry general ledger posting (`Dr. Expense`, `Cr. Cash/Bank`).
   - Recording officer cannot approve own expense.

---

## 4. System-Wide Anti-IDOR Enforcement

NHT-SMS enforces strict object-level authorization across all customer-facing and back-office views:

1. **Member Object Isolation:**
   - A member authenticated via the portal can **only** inspect vehicles, invoices, renewal tickets, and receipts where `vehicle.current_owner == request.member` or `invoice.member == request.member`.
2. **Violation Handling:**
   - Any attempt to access a victim's record by tampering with URL UUIDs raises HTTP 403 `PermissionDenied`.
   - The security middleware traps the violation and creates a security audit event:
     ```python
     AuditLog.objects.create(
         actor=request.user,
         action='IDOR_ATTEMPT_BLOCKED',
         resource_type=target_model.__name__,
         resource_id=str(target_id),
         outcome=AuditOutcome.DENIED
     )
     ```
