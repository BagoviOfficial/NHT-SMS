# User Acceptance Test (UAT) Report — NHT-SMS (Stage 15)

**System:** Northern Highways Transporters SACCO Management System (NHT-SMS)  

---

## 1. Role-Based Acceptance Matrix (All 11 Personas)

| Persona | Seeded Account | Primary SPA Route | Verified Scenarios | Status |
|---|---|---|---|---|
| `SUPER_ADMIN` | `admin` | `/app/#dashboard` | User provisioning, 11-role assignment, config change request creation, diagnostics | **VERIFIED** |
| `CHAIRMAN` | `chairman` | `/app/#dashboard` | Configuration change request approval (`Checker != Maker`), governance, financials | **VERIFIED** |
| `SECRETARY` | `secretary` | `/app/#dashboard` | Member approvals, vehicle transfers, drivers, routes, announcements | **VERIFIED** |
| `TREASURER` | `treasurer` | `/app/#dashboard` | Invoicing, reconciliation execution, period close/reopen, financial Excel export | **VERIFIED** |
| `ACCOUNTANT` | `accountant` | `/app/#dashboard` | Manual voucher Checker approval, GL journals, expenses, financial statements | **VERIFIED** |
| `COMPLIANCE_OFFICER` | `compliance` | `/app/#vehicles` | Compliance scan (`30/14/7/3/0` thresholds), document verification, renewal completion | **VERIFIED** |
| `RENEWAL_OFFICER` | `renewal_officer` | `/app/#dashboard` | Renewal review & fee invoicing; restricted from financial Excel export (`403`) | **VERIFIED** |
| `FIELD_OFFICER` | `field_officer` | `/app/#dashboard` | Fleet & route registry, maintenance & incidents; denied financial Excel (`403`) | **VERIFIED** |
| `AUDITOR` | `auditor` | `/app/#dashboard` | Read-only access to audit logs, accounting reports, settings; mutations denied (`403`) | **VERIFIED** |
| `MEMBER` | `alihassan` | `/app/#member-portal` | Fleet view, invoice detail, M-Pesa STK trigger, statement, sequential renewals, anti-IDOR | **VERIFIED** |
| `DRIVER` | `yusufjama` | `/app/#driver-portal` | Driver portal (`DL`/`PSV` validity, assigned vehicles/routes); management APIs denied (`403`) | **VERIFIED** |
