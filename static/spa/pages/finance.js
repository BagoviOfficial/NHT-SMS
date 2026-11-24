import { React, MUI, html, apiFetch, extractList, formatCurrency, formatDateTime } from '../api.js';
import { MaterialIcon, PageHeader, ResponsiveDataGrid, ResponsiveDialog, StatusChip } from '../components.js';

export function InvoicesPage({ notify }) {
    const [invoices, setInvoices] = React.useState([]);
    const [members, setMembers] = React.useState([]);
    const [services, setServices] = React.useState([]);
    const [loading, setLoading] = React.useState(true);
    const [createOpen, setCreateOpen] = React.useState(false);
    const [stkTarget, setStkTarget] = React.useState(null);
    const [stkPhone, setStkPhone] = React.useState('');
    const [form, setForm] = React.useState({ member: '', service_item: '', quantity: 1, notes: '' });

    const load = React.useCallback(async () => {
        setLoading(true);
        try {
            const [iRes, mRes, sRes] = await Promise.all([
                apiFetch('/api/v1/invoices/'),
                apiFetch('/api/v1/members/'),
                apiFetch('/api/v1/service-items/'),
            ]);
            setInvoices(extractList(iRes));
            setMembers(extractList(mRes));
            setServices(extractList(sRes));
        } catch (err) {
            notify(err.message, 'error');
        } finally {
            setLoading(false);
        }
    }, [notify]);

    React.useEffect(() => { load(); }, [load]);

    const handleCreate = async () => {
        try {
            const svc = services.find((s) => s.id === form.service_item);
            await apiFetch('/api/v1/invoices/', {
                method: 'POST',
                body: {
                    member: form.member,
                    notes: form.notes,
                    items: [{
                        service_item: form.service_item,
                        quantity: Number(form.quantity || 1),
                        unit_price: svc ? svc.default_amount : '1000.00',
                    }],
                },
            });
            notify('Invoice created and posted to ledger.', 'success');
            setCreateOpen(false);
            load();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const handleStk = async () => {
        try {
            await apiFetch(`/api/v1/invoices/${stkTarget.id}/pay_stk/`, {
                method: 'POST',
                body: { phone_number: stkPhone },
            });
            notify(`STK Push sent to ${stkPhone}.`, 'success');
            setStkTarget(null);
            load();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    return html`
        <${MUI.Box}>
            <${PageHeader}
                title="Billing & Invoices"
                subtitle="Statutory & SACCO fee invoicing, balances, and M-Pesa STK Push initiation."
                action=${html`
                    <${MUI.Button} variant="contained" startIcon=${html`<${MaterialIcon} name="add" />`} onClick=${() => setCreateOpen(true)}>
                        Issue Invoice
                    </${MUI.Button}>
                `}
            />
            <${ResponsiveDataGrid}
                loading=${loading}
                rows=${invoices}
                columns=${[
                    { key: 'invoice_number', label: 'Invoice #', render: (r) => html`<span class="nht-mono">${r.invoice_number}</span>` },
                    { key: 'member_name', label: 'Member' },
                    { key: 'total_amount', label: 'Total', align: 'right', render: (r) => formatCurrency(r.total_amount) },
                    { key: 'amount_paid', label: 'Paid', align: 'right', render: (r) => formatCurrency(r.amount_paid) },
                    { key: 'balance_due', label: 'Balance', align: 'right', render: (r) => html`<strong>${formatCurrency(r.balance_due)}</strong>` },
                    { key: 'status', label: 'Status', render: (r) => html`<${StatusChip} value=${r.status} />` },
                    {
                        key: 'actions',
                        label: 'Action',
                        align: 'right',
                        render: (r) => !r.is_fully_paid && html`
                            <${MUI.Button} size="small" color="success" onClick=${() => { setStkTarget(r); setStkPhone(''); }}>
                                STK Push
                            </${MUI.Button}>
                        `,
                    },
                ]}
            />

            <${ResponsiveDialog}
                open=${createOpen}
                onClose=${() => setCreateOpen(false)}
                title="Issue New SACCO Invoice"
                actions=${html`
                    <${MUI.Button} onClick=${() => setCreateOpen(false)}>Cancel</${MUI.Button}>
                    <${MUI.Button} variant="contained" onClick=${handleCreate}>Issue Invoice</${MUI.Button}>
                `}
            >
                <${MUI.Stack} spacing=${2} sx=${{ pt: 1 }}>
                    <${MUI.TextField} select label="Member" fullWidth value=${form.member} onChange=${(e) => setForm({ ...form, member: e.target.value })}>
                        ${members.map((m) => html`<${MUI.MenuItem} key=${m.id} value=${m.id}>${m.full_name} (${m.membership_number})</${MUI.MenuItem}>`)}
                    </${MUI.TextField}>
                    <${MUI.TextField} select label="Service Item" fullWidth value=${form.service_item} onChange=${(e) => setForm({ ...form, service_item: e.target.value })}>
                        ${services.map((s) => html`<${MUI.MenuItem} key=${s.id} value=${s.id}>${s.name} — ${formatCurrency(s.default_amount)}</${MUI.MenuItem}>`)}
                    </${MUI.TextField}>
                    <${MUI.TextField} label="Quantity" type="number" fullWidth value=${form.quantity} onChange=${(e) => setForm({ ...form, quantity: e.target.value })} />
                    <${MUI.TextField} label="Notes" fullWidth value=${form.notes} onChange=${(e) => setForm({ ...form, notes: e.target.value })} />
                </${MUI.Stack}>
            </${ResponsiveDialog}>

            <${ResponsiveDialog}
                open=${Boolean(stkTarget)}
                onClose=${() => setStkTarget(null)}
                title=${`M-Pesa STK Push: ${stkTarget?.invoice_number || ''}`}
                actions=${html`
                    <${MUI.Button} onClick=${() => setStkTarget(null)}>Cancel</${MUI.Button}>
                    <${MUI.Button} variant="contained" color="success" onClick=${handleStk}>Send STK Prompt</${MUI.Button}>
                `}
            >
                <${MUI.Stack} spacing=${2} sx=${{ pt: 1 }}>
                    <${MUI.Alert} severity="info">Amount Due: <strong>${formatCurrency(stkTarget?.balance_due)}</strong></${MUI.Alert}>
                    <${MUI.TextField} label="Safaricom Phone (+2547...)" fullWidth value=${stkPhone} onChange=${(e) => setStkPhone(e.target.value)} />
                </${MUI.Stack}>
            </${ResponsiveDialog}>
        </${MUI.Box}>
    `;
}

export function PaymentsVouchersPage({ notify }) {
    const [tab, setTab] = React.useState(0);
    const [payments, setPayments] = React.useState([]);
    const [vouchers, setVouchers] = React.useState([]);
    const [receipts, setReceipts] = React.useState([]);
    const [invoices, setInvoices] = React.useState([]);
    const [loading, setLoading] = React.useState(true);
    const [voucherOpen, setVoucherOpen] = React.useState(false);
    const [vForm, setVForm] = React.useState({
        invoice: '', method: 'BANK_TRANSFER', bank_slip_reference: '', bank_name: 'KCB Bank', amount: '', payment_date: '',
    });

    const load = React.useCallback(async () => {
        setLoading(true);
        try {
            const [pRes, vRes, rRes, iRes] = await Promise.all([
                apiFetch('/api/v1/payments/'),
                apiFetch('/api/v1/vouchers/'),
                apiFetch('/api/v1/receipts/'),
                apiFetch('/api/v1/invoices/'),
            ]);
            setPayments(extractList(pRes));
            setVouchers(extractList(vRes));
            setReceipts(extractList(rRes));
            setInvoices(extractList(iRes).filter((inv) => !inv.is_fully_paid));
        } catch (err) {
            notify(err.message, 'error');
        } finally {
            setLoading(false);
        }
    }, [notify]);

    React.useEffect(() => { load(); }, [load]);

    const handleCreateVoucher = async () => {
        try {
            await apiFetch('/api/v1/vouchers/', { method: 'POST', body: vForm });
            notify('Manual voucher recorded (Pending Checker approval).', 'success');
            setVoucherOpen(false);
            load();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const handleVoucherAction = async (id, act) => {
        try {
            await apiFetch(`/api/v1/vouchers/${id}/${act}/`, { method: 'POST', body: {} });
            notify(`Voucher ${act}d cleanly.`, 'success');
            load();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    return html`
        <${MUI.Box}>
            <${PageHeader}
                title="Payments, Receipts & Manual Vouchers"
                subtitle="M-Pesa settlements, official receipts, and Maker-Checker bank deposit verification."
                action=${html`
                    <${MUI.Button} variant="contained" startIcon=${html`<${MaterialIcon} name="post_add" />`} onClick=${() => setVoucherOpen(true)}>
                        Record Manual Voucher (Maker)
                    </${MUI.Button}>
                `}
            />

            <${MUI.Tabs} value=${tab} onChange=${(_, v) => setTab(v)} sx=${{ mb: 2 }}>
                <${MUI.Tab} label="Manual Vouchers (${vouchers.length})" />
                <${MUI.Tab} label="Payments (${payments.length})" />
                <${MUI.Tab} label="Receipts (${receipts.length})" />
            </${MUI.Tabs}>

            ${tab === 0 ? html`
                <${ResponsiveDataGrid}
                    loading=${loading}
                    rows=${vouchers}
                    columns=${[
                        { key: 'bank_slip_reference', label: 'Slip Ref', render: (r) => html`<span class="nht-mono">${r.bank_slip_reference}</span>` },
                        { key: 'invoice_number', label: 'Invoice' },
                        { key: 'member_name', label: 'Member' },
                        { key: 'amount', label: 'Amount', align: 'right', render: (r) => formatCurrency(r.amount) },
                        { key: 'entered_by_username', label: 'Maker' },
                        { key: 'status', label: 'Status', render: (r) => html`<${StatusChip} value=${r.status} />` },
                        {
                            key: 'actions',
                            label: 'Checker Actions',
                            align: 'right',
                            render: (r) => r.status === 'PENDING' && html`
                                <${MUI.Stack} direction="row" spacing=${0.5} justifyContent="flex-end">
                                    <${MUI.Button} size="small" color="success" onClick=${() => handleVoucherAction(r.id, 'approve')}>Approve</${MUI.Button}>
                                    <${MUI.Button} size="small" color="error" onClick=${() => handleVoucherAction(r.id, 'reject')}>Reject</${MUI.Button}>
                                </${MUI.Stack}>
                            `,
                        },
                    ]}
                />
            ` : tab === 1 ? html`
                <${ResponsiveDataGrid}
                    loading=${loading}
                    rows=${payments}
                    columns=${[
                        { key: 'payment_reference', label: 'Ref #', render: (r) => html`<span class="nht-mono">${r.payment_reference}</span>` },
                        { key: 'provider_transaction_id', label: 'M-Pesa / Slip' },
                        { key: 'invoice_number', label: 'Invoice' },
                        { key: 'method_display', label: 'Method' },
                        { key: 'amount', label: 'Amount', align: 'right', render: (r) => formatCurrency(r.amount) },
                        { key: 'status', label: 'Status', render: (r) => html`<${StatusChip} value=${r.status} />` },
                    ]}
                />
            ` : html`
                <${ResponsiveDataGrid}
                    loading=${loading}
                    rows=${receipts}
                    columns=${[
                        { key: 'receipt_number', label: 'Receipt #', render: (r) => html`<span class="nht-mono">${r.receipt_number}</span>` },
                        { key: 'invoice_number', label: 'Invoice #' },
                        { key: 'member_name', label: 'Member' },
                        { key: 'amount', label: 'Amount', align: 'right', render: (r) => formatCurrency(r.amount) },
                        { key: 'issued_at', label: 'Issued At', render: (r) => formatDateTime(r.issued_at) },
                        {
                            key: 'print_url',
                            label: 'Print',
                            align: 'right',
                            render: (r) => html`<${MUI.Button} size="small" href=${r.print_url} target="_blank">View</${MUI.Button}>`,
                        },
                    ]}
                />
            `}

            <${ResponsiveDialog}
                open=${voucherOpen}
                onClose=${() => setVoucherOpen(false)}
                title="Record Bank / Cash Deposit Voucher"
                actions=${html`
                    <${MUI.Button} onClick=${() => setVoucherOpen(false)}>Cancel</${MUI.Button}>
                    <${MUI.Button} variant="contained" onClick=${handleCreateVoucher}>Submit Voucher</${MUI.Button}>
                `}
            >
                <${MUI.Stack} spacing=${2} sx=${{ pt: 1 }}>
                    <${MUI.TextField} select label="Invoice" fullWidth value=${vForm.invoice} onChange=${(e) => setVForm({ ...vForm, invoice: e.target.value })}>
                        ${invoices.map((i) => html`<${MUI.MenuItem} key=${i.id} value=${i.id}>${i.invoice_number} — Due ${formatCurrency(i.balance_due)}</${MUI.MenuItem}>`)}
                    </${MUI.TextField}>
                    <${MUI.TextField} select label="Method" fullWidth value=${vForm.method} onChange=${(e) => setVForm({ ...vForm, method: e.target.value })}>
                        <${MUI.MenuItem} value="BANK_TRANSFER">Bank Transfer / Deposit</${MUI.MenuItem}>
                        <${MUI.MenuItem} value="CASH">Cash Office</${MUI.MenuItem}>
                    </${MUI.TextField}>
                    <${MUI.TextField} label="Slip / Deposit Ref" fullWidth value=${vForm.bank_slip_reference} onChange=${(e) => setVForm({ ...vForm, bank_slip_reference: e.target.value })} />
                    <${MUI.TextField} label="Bank Name" fullWidth value=${vForm.bank_name} onChange=${(e) => setVForm({ ...vForm, bank_name: e.target.value })} />
                    <${MUI.TextField} label="Amount (KES)" type="number" fullWidth value=${vForm.amount} onChange=${(e) => setVForm({ ...vForm, amount: e.target.value })} />
                    <${MUI.TextField} label="Deposit Date" type="date" InputLabelProps=${{ shrink: true }} fullWidth value=${vForm.payment_date} onChange=${(e) => setVForm({ ...vForm, payment_date: e.target.value })} />
                </${MUI.Stack}>
            </${ResponsiveDialog}>
        </${MUI.Box}>
    `;
}

export function ReconciliationPage({ notify }) {
    const [runs, setRuns] = React.useState([]);
    const [exceptions, setExceptions] = React.useState([]);
    const [loading, setLoading] = React.useState(true);

    const load = React.useCallback(async () => {
        setLoading(true);
        try {
            const [rRes, eRes] = await Promise.all([
                apiFetch('/api/v1/reconciliation-runs/'),
                apiFetch('/api/v1/reconciliation-exceptions/'),
            ]);
            setRuns(extractList(rRes));
            setExceptions(extractList(eRes));
        } catch (err) {
            notify(err.message, 'error');
        } finally {
            setLoading(false);
        }
    }, [notify]);

    React.useEffect(() => { load(); }, [load]);

    const runNow = async () => {
        try {
            const run = await apiFetch('/api/v1/reconciliation-runs/execute/', { method: 'POST', body: {} });
            notify(`Run ${run.run_reference}: ${run.matched_count} matched, ${run.exception_count} exceptions.`, 'info');
            load();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const resolveExc = async (id) => {
        try {
            await apiFetch(`/api/v1/reconciliation-exceptions/${id}/resolve/`, {
                method: 'POST',
                body: { status: 'RESOLVED', resolution_notes: 'Reviewed and reconciled by Finance Officer.' },
            });
            notify('Exception resolved.', 'success');
            load();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    return html`
        <${MUI.Box}>
            <${PageHeader}
                title="Stage 12 Payment Reconciliation Workbench"
                subtitle="Cross-check M-Pesa callbacks, invoices, official receipts, and General Ledger journals."
                action=${html`
                    <${MUI.Button} variant="contained" startIcon=${html`<${MaterialIcon} name="sync" />`} onClick=${runNow}>
                        Run Reconciliation
                    </${MUI.Button}>
                `}
            />

            <${MUI.Typography} variant="h6" sx=${{ mb: 1.5 }}>Reconciliation Runs</${MUI.Typography}>
            <${ResponsiveDataGrid}
                loading=${loading}
                rows=${runs}
                columns=${[
                    { key: 'run_reference', label: 'Run Ref', render: (r) => html`<span class="nht-mono">${r.run_reference}</span>` },
                    { key: 'executed_by_username', label: 'Executed By' },
                    { key: 'total_payments_checked', label: 'Checked' },
                    { key: 'matched_count', label: 'Matched' },
                    { key: 'exception_count', label: 'Exceptions' },
                    { key: 'total_matched_amount', label: 'Matched Value', align: 'right', render: (r) => formatCurrency(r.total_matched_amount) },
                    { key: 'created_at', label: 'Date', render: (r) => formatDateTime(r.created_at) },
                ]}
            />

            <${MUI.Typography} variant="h6" sx=${{ mt: 3, mb: 1.5 }}>Reconciliation Exceptions</${MUI.Typography}>
            <${ResponsiveDataGrid}
                loading=${loading}
                rows=${exceptions}
                columns=${[
                    { key: 'exception_type_display', label: 'Type' },
                    { key: 'severity', label: 'Severity', render: (r) => html`<${StatusChip} value=${r.severity === 'HIGH' || r.severity === 'CRITICAL' ? 'REJECTED' : 'PENDING'} label=${r.severity} />` },
                    { key: 'description', label: 'Description' },
                    { key: 'status', label: 'Status', render: (r) => html`<${StatusChip} value=${r.status} />` },
                    {
                        key: 'actions',
                        label: 'Action',
                        align: 'right',
                        render: (r) => r.status === 'OPEN' && html`
                            <${MUI.Button} size="small" color="success" onClick=${() => resolveExc(r.id)}>Resolve</${MUI.Button}>
                        `,
                    },
                ]}
            />
        </${MUI.Box}>
    `;
}
