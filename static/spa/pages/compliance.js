import { React, MUI, html, apiFetch, extractList } from '../api.js';
import { MaterialIcon, PageHeader, ResponsiveDataGrid, ResponsiveDialog, StatusChip } from '../components.js';

export function DocumentsPage({ notify }) {
    const [docs, setDocs] = React.useState([]);
    const [docTypes, setDocTypes] = React.useState([]);
    const [vehicles, setVehicles] = React.useState([]);
    const [loading, setLoading] = React.useState(true);
    const [uploadOpen, setUploadOpen] = React.useState(false);
    const [fileObj, setFileObj] = React.useState(null);
    const [form, setForm] = React.useState({
        document_type: '', vehicle: '', reference_number: '', issue_date: '', expiry_date: '',
    });

    const load = React.useCallback(async () => {
        setLoading(true);
        try {
            const [dRes, tRes, vRes] = await Promise.all([
                apiFetch('/api/v1/documents/'),
                apiFetch('/api/v1/document-types/'),
                apiFetch('/api/v1/vehicles/'),
            ]);
            setDocs(extractList(dRes));
            setDocTypes(extractList(tRes));
            setVehicles(extractList(vRes));
        } catch (err) {
            notify(err.message, 'error');
        } finally {
            setLoading(false);
        }
    }, [notify]);

    React.useEffect(() => { load(); }, [load]);

    const handleUpload = async () => {
        if (!fileObj) return notify('Select a document file first.', 'warning');
        const fd = new FormData();
        Object.entries(form).forEach(([k, v]) => { if (v) fd.append(k, v); });
        fd.append('file', fileObj);
        try {
            await apiFetch('/api/v1/documents/', { method: 'POST', body: fd });
            notify('Document uploaded securely to vault.', 'success');
            setUploadOpen(false);
            load();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const handleVerify = async (id, decision) => {
        try {
            await apiFetch(`/api/v1/documents/${id}/verify/`, { method: 'POST', body: { decision } });
            notify(`Document ${decision.toLowerCase()}.`, 'success');
            load();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    return html`
        <${MUI.Box}>
            <${PageHeader}
                title="Regulatory Document Vault"
                subtitle="Magic-byte validated certificates, version control, and Compliance Officer verification."
                action=${html`
                    <${MUI.Button} variant="contained" startIcon=${html`<${MaterialIcon} name="upload_file" />`} onClick=${() => setUploadOpen(true)}>
                        Upload Document
                    </${MUI.Button}>
                `}
            />
            <${ResponsiveDataGrid}
                loading=${loading}
                rows=${docs}
                columns=${[
                    { key: 'document_type_name', label: 'Type' },
                    { key: 'vehicle_plate', label: 'Vehicle / Subject', render: (r) => r.vehicle_plate || r.driver_name || r.member_name },
                    { key: 'reference_number', label: 'Ref #' },
                    { key: 'expiry_date', label: 'Expiry' },
                    { key: 'version', label: 'Ver', render: (r) => `v${r.version}` },
                    { key: 'status', label: 'Status', render: (r) => html`<${StatusChip} value=${r.status} />` },
                    {
                        key: 'actions',
                        label: 'Actions',
                        align: 'right',
                        render: (r) => html`
                            <${MUI.Stack} direction="row" spacing=${0.5} justifyContent="flex-end">
                                <${MUI.Button} size="small" href=${r.download_url} target="_blank">Download</${MUI.Button}>
                                ${r.status === 'PENDING' && html`
                                    <${MUI.Button} size="small" color="success" onClick=${() => handleVerify(r.id, 'APPROVED')}>Verify</${MUI.Button}>
                                    <${MUI.Button} size="small" color="error" onClick=${() => handleVerify(r.id, 'REJECTED')}>Reject</${MUI.Button}>
                                `}
                            </${MUI.Stack}>
                        `,
                    },
                ]}
            />

            <${ResponsiveDialog}
                open=${uploadOpen}
                onClose=${() => setUploadOpen(false)}
                title="Upload Regulatory Document"
                actions=${html`
                    <${MUI.Button} onClick=${() => setUploadOpen(false)}>Cancel</${MUI.Button}>
                    <${MUI.Button} variant="contained" onClick=${handleUpload}>Upload</${MUI.Button}>
                `}
            >
                <${MUI.Stack} spacing=${2} sx=${{ pt: 1 }}>
                    <${MUI.TextField} select label="Document Type" fullWidth value=${form.document_type} onChange=${(e) => setForm({ ...form, document_type: e.target.value })}>
                        ${docTypes.map((dt) => html`<${MUI.MenuItem} key=${dt.id} value=${dt.id}>${dt.name}</${MUI.MenuItem}>`)}
                    </${MUI.TextField}>
                    <${MUI.TextField} select label="Vehicle" fullWidth value=${form.vehicle} onChange=${(e) => setForm({ ...form, vehicle: e.target.value })}>
                        ${vehicles.map((v) => html`<${MUI.MenuItem} key=${v.id} value=${v.id}>${v.registration_number}</${MUI.MenuItem}>`)}
                    </${MUI.TextField}>
                    <${MUI.TextField} label="Certificate / Policy Number" fullWidth value=${form.reference_number} onChange=${(e) => setForm({ ...form, reference_number: e.target.value })} />
                    <${MUI.TextField} label="Issue Date" type="date" InputLabelProps=${{ shrink: true }} fullWidth value=${form.issue_date} onChange=${(e) => setForm({ ...form, issue_date: e.target.value })} />
                    <${MUI.TextField} label="Expiry Date" type="date" InputLabelProps=${{ shrink: true }} fullWidth value=${form.expiry_date} onChange=${(e) => setForm({ ...form, expiry_date: e.target.value })} />
                    <input type="file" accept=".pdf,.jpg,.jpeg,.png" onChange=${(e) => setFileObj(e.target.files?.[0] || null)} />
                </${MUI.Stack}>
            </${ResponsiveDialog}>
        </${MUI.Box}>
    `;
}

export function CompliancePage({ notify }) {
    const [alerts, setAlerts] = React.useState([]);
    const [loading, setLoading] = React.useState(true);

    const load = React.useCallback(async () => {
        setLoading(true);
        try {
            const res = await apiFetch('/api/v1/compliance-alerts/');
            setAlerts(extractList(res));
        } catch (err) {
            notify(err.message, 'error');
        } finally {
            setLoading(false);
        }
    }, [notify]);

    React.useEffect(() => { load(); }, [load]);

    const runScan = async () => {
        try {
            const res = await apiFetch('/api/v1/compliance/scan/', { method: 'POST' });
            notify(`Scan finished: ${res.total_vehicles_scanned} vehicles checked, ${res.alerts_created} new alerts.`, 'success');
            load();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const resolveAlert = async (id) => {
        try {
            await apiFetch(`/api/v1/compliance-alerts/${id}/resolve/`, { method: 'POST' });
            notify('Alert resolved.', 'success');
            load();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    return html`
        <${MUI.Box}>
            <${PageHeader}
                title="Compliance Monitoring & Alerts"
                subtitle="Automated 30/14/7/3/0-day expiry monitoring and regulatory escalation."
                action=${html`
                    <${MUI.Button} variant="contained" startIcon=${html`<${MaterialIcon} name="radar" />`} onClick=${runScan}>
                        Run Compliance Scan
                    </${MUI.Button}>
                `}
            />
            <${ResponsiveDataGrid}
                loading=${loading}
                rows=${alerts}
                columns=${[
                    { key: 'vehicle_plate', label: 'Vehicle', render: (r) => html`<strong>${r.vehicle_plate}</strong>` },
                    { key: 'alert_type_display', label: 'Alert Type' },
                    { key: 'days_remaining', label: 'Days' },
                    { key: 'message', label: 'Details' },
                    { key: 'is_resolved', label: 'Status', render: (r) => html`<${StatusChip} value=${r.is_resolved ? 'RESOLVED' : 'OPEN'} />` },
                    {
                        key: 'actions',
                        label: 'Action',
                        align: 'right',
                        render: (r) => !r.is_resolved && html`
                            <${MUI.Button} size="small" color="success" onClick=${() => resolveAlert(r.id)}>Resolve</${MUI.Button}>
                        `,
                    },
                ]}
            />
        </${MUI.Box}>
    `;
}

export function RenewalsPage({ notify }) {
    const [rows, setRows] = React.useState([]);
    const [loading, setLoading] = React.useState(true);
    const [invoiceTarget, setInvoiceTarget] = React.useState(null);
    const [fee, setFee] = React.useState('1500.00');

    const load = React.useCallback(async () => {
        setLoading(true);
        try {
            const res = await apiFetch('/api/v1/renewals/');
            setRows(extractList(res));
        } catch (err) {
            notify(err.message, 'error');
        } finally {
            setLoading(false);
        }
    }, [notify]);

    React.useEffect(() => { load(); }, [load]);

    const handleInvoice = async () => {
        try {
            await apiFetch(`/api/v1/renewals/${invoiceTarget.id}/review_invoice/`, {
                method: 'POST',
                body: { action: 'APPROVE_INVOICE', fee },
            });
            notify('Renewal approved and invoice issued.', 'success');
            setInvoiceTarget(null);
            load();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const doStep = async (id, endpoint) => {
        try {
            await apiFetch(`/api/v1/renewals/${id}/${endpoint}/`, { method: 'POST', body: {} });
            notify('Renewal workflow advanced.', 'success');
            load();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    return html`
        <${MUI.Box}>
            <${PageHeader}
                title="Document Renewal Workflow"
                subtitle="End-to-end lifecycle: Submitted -> Invoiced -> Paid -> Processing -> Completed."
            />
            <${ResponsiveDataGrid}
                loading=${loading}
                rows=${rows}
                columns=${[
                    { key: 'request_number', label: 'Request #', render: (r) => html`<span class="nht-mono">${r.request_number}</span>` },
                    { key: 'member_name', label: 'Member' },
                    { key: 'vehicle_plate', label: 'Vehicle' },
                    { key: 'document_type_name', label: 'Document' },
                    { key: 'invoice_number', label: 'Invoice #', render: (r) => r.invoice_number || '—' },
                    { key: 'status', label: 'Stage', render: (r) => html`<${StatusChip} value=${r.status} label=${r.status_display} />` },
                    {
                        key: 'actions',
                        label: 'Workflow Actions',
                        align: 'right',
                        render: (r) => html`
                            <${MUI.Stack} direction="row" spacing=${0.5} justifyContent="flex-end">
                                ${r.status === 'SUBMITTED' && html`<${MUI.Button} size="small" variant="outlined" onClick=${() => setInvoiceTarget(r)}>Review & Invoice</${MUI.Button}>`}
                                ${r.status === 'PAID' && html`<${MUI.Button} size="small" color="info" onClick=${() => doStep(r.id, 'mark_processing')}>Start Processing</${MUI.Button}>`}
                                ${(r.status === 'DOC_UPLOADED' || r.status === 'PROCESSING') && html`<${MUI.Button} size="small" color="success" onClick=${() => doStep(r.id, 'complete')}>Complete</${MUI.Button}>`}
                            </${MUI.Stack}>
                        `,
                    },
                ]}
            />

            <${ResponsiveDialog}
                open=${Boolean(invoiceTarget)}
                onClose=${() => setInvoiceTarget(null)}
                title=${`Approve & Invoice ${invoiceTarget?.request_number || ''}`}
                actions=${html`
                    <${MUI.Button} onClick=${() => setInvoiceTarget(null)}>Cancel</${MUI.Button}>
                    <${MUI.Button} variant="contained" onClick=${handleInvoice}>Generate Invoice</${MUI.Button}>
                `}
            >
                <${MUI.TextField}
                    label="Renewal Fee (KES)"
                    type="number"
                    fullWidth
                    sx=${{ mt: 1 }}
                    value=${fee}
                    onChange=${(e) => setFee(e.target.value)}
                />
            </${ResponsiveDialog}>
        </${MUI.Box}>
    `;
}
