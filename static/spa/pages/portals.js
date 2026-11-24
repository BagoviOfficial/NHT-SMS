import { React, MUI, html, apiFetch, extractList, formatCurrency } from '../api.js';
import { MaterialIcon, PageHeader, ResponsiveDataGrid, ResponsiveDialog, StatCard, StatusChip } from '../components.js';

export function MemberPortalPage({ notify }) {
    const [tab, setTab] = React.useState(0);
    const [vehicles, setVehicles] = React.useState([]);
    const [invoices, setInvoices] = React.useState([]);
    const [receipts, setReceipts] = React.useState([]);
    const [renewals, setRenewals] = React.useState([]);
    const [docTypes, setDocTypes] = React.useState([]);
    const [statement, setStatement] = React.useState(null);
    const [prefs, setPrefs] = React.useState(null);
    const [loading, setLoading] = React.useState(true);
    const [stkTarget, setStkTarget] = React.useState(null);
    const [stkPhone, setStkPhone] = React.useState('');
    const [rnwOpen, setRnwOpen] = React.useState(false);
    const [rnwForm, setRnwForm] = React.useState({ vehicle: '', document_type: '', notes: '' });

    const load = React.useCallback(async () => {
        setLoading(true);
        try {
            const [vRes, iRes, rRes, rnRes, dtRes, stRes, prRes] = await Promise.all([
                apiFetch('/api/v1/vehicles/'),
                apiFetch('/api/v1/invoices/'),
                apiFetch('/api/v1/receipts/'),
                apiFetch('/api/v1/renewals/'),
                apiFetch('/api/v1/document-types/'),
                apiFetch('/api/v1/billing/statement/'),
                apiFetch('/api/v1/notifications/preferences/').catch(() => null),
            ]);
            setVehicles(extractList(vRes));
            setInvoices(extractList(iRes));
            setReceipts(extractList(rRes));
            setRenewals(extractList(rnRes));
            setDocTypes(extractList(dtRes));
            setStatement(stRes);
            setPrefs(prRes);
        } catch (err) {
            notify(err.message, 'error');
        } finally {
            setLoading(false);
        }
    }, [notify]);

    React.useEffect(() => { load(); }, [load]);

    const handlePayStk = async () => {
        try {
            await apiFetch(`/api/v1/invoices/${stkTarget.id}/pay_stk/`, {
                method: 'POST',
                body: { phone_number: stkPhone },
            });
            notify('M-Pesa STK Push sent to your phone.', 'success');
            setStkTarget(null);
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const handleSubmitRenewal = async () => {
        try {
            await apiFetch('/api/v1/renewals/', { method: 'POST', body: rnwForm });
            notify('Document renewal application submitted.', 'success');
            setRnwOpen(false);
            load();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const handleSavePrefs = async () => {
        try {
            await apiFetch('/api/v1/notifications/preferences/', { method: 'PUT', body: prefs });
            notify('Communication preferences saved.', 'success');
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const outstanding = invoices.reduce((acc, inv) => acc + Number(inv.balance_due || 0), 0);

    return html`
        <${MUI.Box}>
            <${PageHeader}
                title="Member Self-Service Portal"
                subtitle="Manage your registered fleet, pay invoices via M-Pesa, view statements, and apply for renewals."
                action=${html`
                    <${MUI.Button} variant="contained" startIcon=${html`<${MaterialIcon} name="autorenew" />`} onClick=${() => setRnwOpen(true)}>
                        Apply for Renewal
                    </${MUI.Button}>
                `}
            />

            <${MUI.Grid} container spacing=${2} sx=${{ mb: 3 }}>
                <${MUI.Grid} item xs=${12} sm=${4}>
                    <${StatCard} title="My Fleet" value=${vehicles.length} subtitle="Registered PSVs" icon="directions_bus" color="primary" />
                </${MUI.Grid}>
                <${MUI.Grid} item xs=${12} sm=${4}>
                    <${StatCard} title="Balance Due" value=${formatCurrency(outstanding)} subtitle="${invoices.filter((i) => !i.is_fully_paid).length} open invoices" icon="receipt_long" color="warning" />
                </${MUI.Grid}>
                <${MUI.Grid} item xs=${12} sm=${4}>
                    <${StatCard} title="Renewals" value=${renewals.length} subtitle="Permit & inspection requests" icon="autorenew" color="info" />
                </${MUI.Grid}>
            </${MUI.Grid}>

            <${MUI.Tabs} value=${tab} onChange=${(_, v) => setTab(v)} variant="scrollable" scrollButtons="auto" sx=${{ mb: 2 }}>
                <${MUI.Tab} label="My Fleet" />
                <${MUI.Tab} label="Bills & Receipts" />
                <${MUI.Tab} label="Statement" />
                <${MUI.Tab} label="Renewals" />
                <${MUI.Tab} label="Preferences" />
            </${MUI.Tabs}>

            ${tab === 0 && html`
                <${ResponsiveDataGrid}
                    loading=${loading}
                    rows=${vehicles}
                    columns=${[
                        { key: 'registration_number', label: 'Plate', render: (r) => html`<strong>${r.registration_number}</strong>` },
                        { key: 'make', label: 'Vehicle', render: (r) => `${r.make} ${r.model}` },
                        { key: 'category_display', label: 'Category' },
                        { key: 'compliance_status', label: 'Compliance', render: (r) => html`<${StatusChip} value=${r.compliance_status} />` },
                        {
                            key: 'qr_token',
                            label: 'QR Badge',
                            align: 'right',
                            render: (r) => html`<${MUI.Button} size="small" href="/verify/vehicle/${r.qr_token}/" target="_blank">Verify QR</${MUI.Button}>`,
                        },
                    ]}
                />
            `}

            ${tab === 1 && html`
                <${MUI.Stack} spacing=${2}>
                    <${ResponsiveDataGrid}
                        loading=${loading}
                        rows=${invoices}
                        columns=${[
                            { key: 'invoice_number', label: 'Invoice #' },
                            { key: 'total_amount', label: 'Total', align: 'right', render: (r) => formatCurrency(r.total_amount) },
                            { key: 'balance_due', label: 'Balance Due', align: 'right', render: (r) => formatCurrency(r.balance_due) },
                            { key: 'status', label: 'Status', render: (r) => html`<${StatusChip} value=${r.status} />` },
                            {
                                key: 'actions',
                                label: 'Pay',
                                align: 'right',
                                render: (r) => !r.is_fully_paid && html`
                                    <${MUI.Button} size="small" variant="contained" color="success" onClick=${() => { setStkTarget(r); setStkPhone(''); }}>
                                        Pay M-Pesa
                                    </${MUI.Button}>
                                `,
                            },
                        ]}
                    />
                    <${MUI.Typography} variant="h6">Official Receipts</${MUI.Typography}>
                    <${ResponsiveDataGrid}
                        rows=${receipts}
                        columns=${[
                            { key: 'receipt_number', label: 'Receipt #' },
                            { key: 'invoice_number', label: 'Invoice #' },
                            { key: 'amount', label: 'Amount', align: 'right', render: (r) => formatCurrency(r.amount) },
                            { key: 'print_url', label: 'PDF', align: 'right', render: (r) => html`<${MUI.Button} size="small" href=${r.print_url} target="_blank">Print</${MUI.Button}>` },
                        ]}
                    />
                </${MUI.Stack}>
            `}

            ${tab === 2 && statement && html`
                <${ResponsiveDataGrid}
                    rows=${(statement.entries || []).map((e, i) => ({ ...e, id: i }))}
                    columns=${[
                        { key: 'date', label: 'Date' },
                        { key: 'reference', label: 'Reference' },
                        { key: 'description', label: 'Description' },
                        { key: 'debit', label: 'Debit', align: 'right', render: (r) => formatCurrency(r.debit) },
                        { key: 'credit', label: 'Credit', align: 'right', render: (r) => formatCurrency(r.credit) },
                        { key: 'running_balance', label: 'Balance', align: 'right', render: (r) => html`<strong>${formatCurrency(r.running_balance)}</strong>` },
                    ]}
                />
            `}

            ${tab === 3 && html`
                <${ResponsiveDataGrid}
                    loading=${loading}
                    rows=${renewals}
                    columns=${[
                        { key: 'request_number', label: 'Request #' },
                        { key: 'vehicle_plate', label: 'Vehicle' },
                        { key: 'document_type_name', label: 'Document' },
                        { key: 'invoice_number', label: 'Invoice' },
                        { key: 'status', label: 'Status', render: (r) => html`<${StatusChip} value=${r.status} label=${r.status_display} />` },
                    ]}
                />
            `}

            ${tab === 4 && prefs && html`
                <${MUI.Card} sx=${{ p: 3, maxWidth: 520 }}>
                    <${MUI.Typography} variant="h6" sx=${{ mb: 2 }}>Notification Preferences</${MUI.Typography}>
                    <${MUI.Stack} spacing=${1}>
                        ${[
                            ['sms_enabled', 'SMS Alerts'],
                            ['whatsapp_enabled', 'WhatsApp Updates'],
                            ['email_enabled', 'Email Notices'],
                            ['compliance_alerts', 'Compliance Expiry Alerts'],
                            ['billing_alerts', 'Billing & Payment Alerts'],
                            ['renewal_alerts', 'Document Renewal Updates'],
                        ].map(([k, lbl]) => html`
                            <${MUI.FormControlLabel}
                                key=${k}
                                control=${html`<${MUI.Switch} checked=${Boolean(prefs[k])} onChange=${(e) => setPrefs({ ...prefs, [k]: e.target.checked })} />`}
                                label=${lbl}
                            />
                        `)}
                        <${MUI.Button} variant="contained" sx=${{ mt: 2, alignSelf: 'flex-start' }} onClick=${handleSavePrefs}>
                            Save Preferences
                        </${MUI.Button}>
                    </${MUI.Stack}>
                </${MUI.Card}>
            `}

            <${ResponsiveDialog}
                open=${Boolean(stkTarget)}
                onClose=${() => setStkTarget(null)}
                title="Pay Invoice via M-Pesa STK Push"
                actions=${html`
                    <${MUI.Button} onClick=${() => setStkTarget(null)}>Cancel</${MUI.Button}>
                    <${MUI.Button} variant="contained" color="success" onClick=${handlePayStk}>Prompt Handset</${MUI.Button}>
                `}
            >
                <${MUI.Stack} spacing=${2} sx=${{ pt: 1 }}>
                    <${MUI.Alert} severity="info">Invoice ${stkTarget?.invoice_number} — Balance: <strong>${formatCurrency(stkTarget?.balance_due)}</strong></${MUI.Alert}>
                    <${MUI.TextField} label="M-Pesa Phone Number" fullWidth value=${stkPhone} onChange=${(e) => setStkPhone(e.target.value)} />
                </${MUI.Stack}>
            </${ResponsiveDialog}>

            <${ResponsiveDialog}
                open=${rnwOpen}
                onClose=${() => setRnwOpen(false)}
                title="Apply for Regulatory Document Renewal"
                actions=${html`
                    <${MUI.Button} onClick=${() => setRnwOpen(false)}>Cancel</${MUI.Button}>
                    <${MUI.Button} variant="contained" onClick=${handleSubmitRenewal}>Submit Application</${MUI.Button}>
                `}
            >
                <${MUI.Stack} spacing=${2} sx=${{ pt: 1 }}>
                    <${MUI.TextField} select label="Vehicle" fullWidth value=${rnwForm.vehicle} onChange=${(e) => setRnwForm({ ...rnwForm, vehicle: e.target.value })}>
                        ${vehicles.map((v) => html`<${MUI.MenuItem} key=${v.id} value=${v.id}>${v.registration_number}</${MUI.MenuItem}>`)}
                    </${MUI.TextField}>
                    <${MUI.TextField} select label="Document Type" fullWidth value=${rnwForm.document_type} onChange=${(e) => setRnwForm({ ...rnwForm, document_type: e.target.value })}>
                        ${docTypes.map((dt) => html`<${MUI.MenuItem} key=${dt.id} value=${dt.id}>${dt.name}</${MUI.MenuItem}>`)}
                    </${MUI.TextField}>
                    <${MUI.TextField} label="Notes" fullWidth multiline rows=${2} value=${rnwForm.notes} onChange=${(e) => setRnwForm({ ...rnwForm, notes: e.target.value })} />
                </${MUI.Stack}>
            </${ResponsiveDialog}>
        </${MUI.Box}>
    `;
}

export function DriverPortalPage({ notify }) {
    const [data, setData] = React.useState(null);
    const [loading, setLoading] = React.useState(true);

    React.useEffect(() => {
        apiFetch('/api/v1/driver/portal/')
            .then(setData)
            .catch((err) => notify(err.message, 'error'))
            .finally(() => setLoading(false));
    }, [notify]);

    if (loading || !data) {
        return html`<${MUI.Box} sx=${{ p: 5, textAlign: 'center' }}><${MUI.CircularProgress} /></${MUI.Box}>`;
    }

    const drv = data.driver || {};

    return html`
        <${MUI.Box}>
            <${PageHeader}
                title="PSV Driver Self-Service Portal"
                subtitle="Your driving licence validity, NTSA PSV badge status, and assigned vehicle compliance."
            />
            <${MUI.Grid} container spacing=${2} sx=${{ mb: 3 }}>
                <${MUI.Grid} item xs=${12} sm=${4}>
                    <${StatCard} title="Driver Status" value=${drv.status} subtitle="DL: ${drv.driving_license_number}" icon="badge" color="primary" />
                </${MUI.Grid}>
                <${MUI.Grid} item xs=${12} sm=${4}>
                    <${StatCard} title="DL Validity" value="${data.dl_days_remaining ?? '—'} days" subtitle="Expires ${drv.dl_expiry_date}" icon="credit_card" color="success" />
                </${MUI.Grid}>
                <${MUI.Grid} item xs=${12} sm=${4}>
                    <${StatCard} title="PSV Badge" value="${data.psv_days_remaining ?? '—'} days" subtitle="${drv.psv_badge_number || 'N/A'}" icon="verified" color="info" />
                </${MUI.Grid}>
            </${MUI.Grid}>

            <${MUI.Typography} variant="h6" sx=${{ mb: 1.5 }}>Assigned Vehicles & Routes</${MUI.Typography}>
            <${ResponsiveDataGrid}
                rows=${(data.assigned_vehicles || []).map((v) => ({ ...v, id: v.vehicle_id }))}
                columns=${[
                    { key: 'registration_number', label: 'Plate', render: (r) => html`<strong>${r.registration_number}</strong>` },
                    { key: 'make_model', label: 'Vehicle' },
                    { key: 'route', label: 'Assigned Route' },
                    { key: 'owner_name', label: 'Owner' },
                    { key: 'compliance_status', label: 'Compliance', render: (r) => html`<${StatusChip} value=${r.compliance_status} />` },
                    { key: 'qr_verify_url', label: 'QR Seal', align: 'right', render: (r) => html`<${MUI.Button} size="small" href=${r.qr_verify_url} target="_blank">Verify</${MUI.Button}>` },
                ]}
            />
        </${MUI.Box}>
    `;
}
