# User Roles, Permissions & Segregation of Duties — NHT-SMS

**System:** Northern Highways Transporters SACCO Management System (NHT-SMS)  
**Security Standard:** Principle of Least Privilege & OWASP ASVS Level 2  
**Framework:** Django Group & Permission Engine with Hardened Object-Level RBAC  

---

## 1. System Role Hierarchy & Definitions

NHT-SMS enforces strict Role-Based Access Control (RBAC) spanning 8 discrete operational personas:

| Role Identifier | Role Title | Functional Scope |
|---|---|---|
| `SYSTEM_ADMIN` | System Administrator | IT configuration, backups, user account provisioning, security parameter tuning. No day-to-day financial posting permissions. |
| `SACCO_ADMIN` | SACCO Executive Director / Chairman | Governance, policy approval, executive dashboards, committee resolutions, final maker-checker authority on high-value expenses. |
| `FINANCE_OFFICER` | Finance Manager / Treasurer | Invoicing, payment reconciliation, general ledger management, financial period closing, manual voucher approval. |
| `REGISTRY_CLERK` | Registry / Accounts Clerk | Member onboarding, vehicle data entry, manual voucher entry (maker), document upload staging. |
| `COMPLIANCE_OFFICER` | Safety & Compliance Manager | Regulatory document verification, fleet grounding/clearing, NTSA/KeNHA compliance auditing, incident investigations. |
| `AUDITOR` | Internal / External Auditor | Read-only inspection of immutable audit logs, general ledger journals, bank reconciliations, and regulatory compliance reports. |
| `MEMBER` | SACCO Member / Vehicle Owner | Self-service portal access (`/portal/`), fleet viewing, payment triggers, statement viewing, renewal submissions. |
| `DRIVER` | Certified PSV Driver | Read-only view of assigned vehicle schedule and compliance badges. |

---

## 2. Granular Permissions Matrix

| Functional Capability | `SYS_ADMIN` | `SACCO_ADMIN` | `FINANCE` | `CLERK` | `COMPLIANCE` | `AUDITOR` | `MEMBER` | `DRIVER` |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Manage Users & MFA** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Inspect Immutable Audit Logs** | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| **Register / Edit Vehicles** | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Verify Regulatory Documents** | ❌ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| **Ground / Clear Vehicle Status** | ❌ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| **Issue Invoices & Debit Notes** | ❌ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Record Manual Bank Voucher (Maker)** | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Approve Manual Voucher (Checker)** | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Post General Ledger Journals** | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Reverse Posted Journals** | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Lock / Unlock Financial Periods** | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **View Executive Dashboards** | ❌ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ |
| **Access Member Portal (`/portal/`)** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| **View Self-Owned Fleets & Invoices** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| **Submit Online Document Renewals** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |

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
