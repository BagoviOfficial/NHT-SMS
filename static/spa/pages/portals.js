import { React, MUI, html, apiFetch, extractList, formatCurrency } from '../api.js';
import { MaterialIcon, PageHeader, ResponsiveDataGrid, ResponsiveDialog, StatCard, StatusChip } from '../components.js';
import { DEFAULT_COMMERCIAL_CATEGORIES, DEFAULT_FUEL_TYPES, VehicleFieldsSection, blankVehicleEntry } from './fleet.js';

const PORTAL_SECTION_TAB = {
    'dashboard': 0,
    'vehicles': 0,
    'vehicle-detail': 0,
    'vehicle-card': 0,
    'vehicle-register': 0,
    'invoices': 1,
    'invoice-detail': 1,
    'receipts': 1,
    'statement': 2,
    'renewals': 3,
    'renewal-apply': 3,
    'preferences': 4,
    'notifications': 5,
    'complaints': 6,
    'complaint-submit': 6,
};

export function MemberPortalPage({ notify }) {
    const bootPortal = window.__NHT_BOOTSTRAP__?.page_data?.portal || {};
    const bootSection = bootPortal.section || 'dashboard';
    const [tab, setTab] = React.useState(PORTAL_SECTION_TAB[bootSection] ?? 0);
    const [detailCard, setDetailCard] = React.useState(() => {
        if (bootSection === 'vehicle-card' && bootPortal.vehicle_card) return { type: 'vehicle-card', data: bootPortal.vehicle_card };
        if (bootSection === 'vehicle-detail' && bootPortal.vehicle) return { type: 'vehicle-detail', data: bootPortal.vehicle, documents: bootPortal.documents || [] };
        if (bootSection === 'invoice-detail' && bootPortal.invoice) return { type: 'invoice-detail', data: bootPortal.invoice };
        return null;
    });
    const [vehicles, setVehicles] = React.useState([]);
    const [invoices, setInvoices] = React.useState([]);
    const [receipts, setReceipts] = React.useState([]);
    const [renewals, setRenewals] = React.useState([]);
    const [docTypes, setDocTypes] = React.useState([]);
    const [notifications, setNotifications] = React.useState([]);
    const [complaints, setComplaints] = React.useState([]);
    const [categories, setCategories] = React.useState(DEFAULT_COMMERCIAL_CATEGORIES);
    const [fuelTypes, setFuelTypes] = React.useState(DEFAULT_FUEL_TYPES);
    const [statement, setStatement] = React.useState(null);
    const [prefs, setPrefs] = React.useState(null);
    const [loading, setLoading] = React.useState(true);
    const [stkTarget, setStkTarget] = React.useState(null);
    const [stkPhone, setStkPhone] = React.useState('');
    const [rnwOpen, setRnwOpen] = React.useState(bootSection === 'renewal-apply');
    const [rnwForm, setRnwForm] = React.useState({ vehicle: '', document_type: '', notes: '' });
    const [vehOpen, setVehOpen] = React.useState(bootSection === 'vehicle-register');
    const [vehForm, setVehForm] = React.useState(blankVehicleEntry);
    const [ticketOpen, setTicketOpen] = React.useState(bootSection === 'complaint-submit');
    const [ticketForm, setTicketForm] = React.useState({
        incident_type: 'COMPLAINT',
        severity: 'MEDIUM',
        vehicle: '',
        location: '',
        title: '',
        description: '',
    });

    const load = React.useCallback(async () => {
        setLoading(true);
        try {
            const [vRes, iRes, rRes, rnRes, dtRes, stRes, prRes, nRes, cRes, catRes] = await Promise.all([
                apiFetch('/api/v1/vehicles/'),
                apiFetch('/api/v1/invoices/'),
                apiFetch('/api/v1/receipts/'),
                apiFetch('/api/v1/renewals/'),
                apiFetch('/api/v1/document-types/'),
                apiFetch('/api/v1/billing/statement/'),
                apiFetch('/api/v1/notifications/preferences/').catch(() => null),
                apiFetch('/api/v1/notifications/').catch(() => []),
                apiFetch('/api/v1/incidents/').catch(() => []),
                apiFetch('/api/v1/vehicles/categories/').catch(() => null),
            ]);
            setVehicles(extractList(vRes));
            setInvoices(extractList(iRes));
            setReceipts(extractList(rRes));
            setRenewals(extractList(rnRes));
            setDocTypes(extractList(dtRes));
            setStatement(stRes);
            setPrefs(prRes);
            setNotifications(extractList(nRes));
            setComplaints(extractList(cRes));
            if (catRes) {
                setCategories(catRes.categories || []);
                setFuelTypes(catRes.fuel_types || []);
            }
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

    const handleRegisterVehicle = async () => {
        try {
            await apiFetch('/api/v1/vehicles/', {
                method: 'POST',
                body: { ...vehForm, engine_number: vehForm.engine_number?.trim() || null },
            });
            notify('Vehicle submitted for Secretariat verification.', 'success');
            setVehOpen(false);
            setVehForm(blankVehicleEntry());
            load();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const handleSubmitTicket = async () => {
        try {
            await apiFetch('/api/v1/incidents/', { method: 'POST', body: ticketForm });
            notify('Support / complaint ticket submitted.', 'success');
            setTicketOpen(false);
            setTicketForm({ incident_type: 'COMPLAINT', severity: 'MEDIUM', vehicle: '', location: '', title: '', description: '' });
            load();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const handleMarkRead = async (id) => {
        try {
            await apiFetch(`/api/v1/notifications/${id}/mark_read/`, { method: 'POST' });
            notify('Notification marked as read.', 'info');
            load();
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
                    <${MUI.Stack} direction="row" spacing=${1} flexWrap="wrap">
                        <${MUI.Button} variant="outlined" startIcon=${html`<${MaterialIcon} name="local_shipping" />`} onClick=${() => setVehOpen(true)}>
                            Register Vehicle
                        </${MUI.Button}>
                        <${MUI.Button} variant="outlined" startIcon=${html`<${MaterialIcon} name="report_problem" />`} onClick=${() => setTicketOpen(true)}>
                            Submit Ticket
                        </${MUI.Button}>
                        <${MUI.Button} variant="contained" startIcon=${html`<${MaterialIcon} name="autorenew" />`} onClick=${() => setRnwOpen(true)}>
                            Apply for Renewal
                        </${MUI.Button}>
                    </${MUI.Stack}>
                `}
            />

            <${MUI.Grid} container spacing=${2} sx=${{ mb: 3 }}>
                <${MUI.Grid} size=${{ xs: 12, sm: 4 }}>
                    <${StatCard} title="My Fleet" value=${vehicles.length} subtitle="Registered Trucks & Trailers" icon="local_shipping" color="primary" />
                </${MUI.Grid}>
                <${MUI.Grid} size=${{ xs: 12, sm: 4 }}>
                    <${StatCard} title="Balance Due" value=${formatCurrency(outstanding)} subtitle="${invoices.filter((i) => !i.is_fully_paid).length} open invoices" icon="receipt_long" color="warning" />
                </${MUI.Grid}>
                <${MUI.Grid} size=${{ xs: 12, sm: 4 }}>
                    <${StatCard} title="Renewals" value=${renewals.length} subtitle="Permit & inspection requests" icon="autorenew" color="info" />
                </${MUI.Grid}>
            </${MUI.Grid}>

            <${MUI.Tabs} value=${tab} onChange=${(_, v) => setTab(v)} variant="scrollable" scrollButtons="auto" sx=${{ mb: 2 }}>
                <${MUI.Tab} label="My Fleet" />
                <${MUI.Tab} label="Bills & Receipts" />
                <${MUI.Tab} label="Statement" />
                <${MUI.Tab} label="Renewals" />
                <${MUI.Tab} label="Preferences" />
                <${MUI.Tab} label="Notifications (${notifications.length})" />
                <${MUI.Tab} label="Tickets (${complaints.length})" />
            </${MUI.Tabs}>

            ${detailCard && html`
                <${MUI.Card} variant="outlined" sx=${{ p: 2.5, mb: 3 }}>
                    <${MUI.Stack} direction="row" justifyContent="space-between" alignItems="center" sx=${{ mb: 1.5 }}>
                        <${MUI.Typography} variant="h6" color="primary.main">
                            ${detailCard.type === 'vehicle-card' ? `Compliance Card: ${detailCard.data.registration_number}` :
                              detailCard.type === 'vehicle-detail' ? `Vehicle Record: ${detailCard.data.registration_number}` :
                              `Invoice ${detailCard.data.invoice_number}`}
                        </${MUI.Typography}>
                        <${MUI.Button} size="small" onClick=${() => setDetailCard(null)}>Close</${MUI.Button}>
                    </${MUI.Stack}>
                    ${detailCard.type === 'vehicle-card' && html`
                        <${MUI.Stack} direction=${{ xs: 'column', sm: 'row' }} spacing=${2} alignItems="center">
                            ${detailCard.data.qr_data_uri && html`
                                <img src=${detailCard.data.qr_data_uri} alt="QR Code" style=${{ width: 140, height: 140, borderRadius: 8, border: '1px solid #CBD5E1', padding: 4 }} />
                            `}
                            <${MUI.Stack} spacing=${1}>
                                <${StatusChip} value=${detailCard.data.compliance} />
                                ${detailCard.data.certificate_number && html`<${MUI.Typography} variant="body2">Certificate #: <strong className="nht-mono">${detailCard.data.certificate_number}</strong></${MUI.Typography}>`}
                                <${MUI.Button} size="small" variant="outlined" href=${detailCard.data.verify_url} target="_blank">Open Public Verification</${MUI.Button}>
                            </${MUI.Stack}>
                        </${MUI.Stack}>
                    `}
                    ${detailCard.type === 'vehicle-detail' && html`
                        <${MUI.Box}>
                            <${MUI.Typography} variant="body2" sx=${{ mb: 1.5 }}>
                                ${detailCard.data.make} ${detailCard.data.model} • <${StatusChip} value=${detailCard.data.compliance} />
                            </${MUI.Typography}>
                            <${ResponsiveDataGrid}
                                rows=${detailCard.documents}
                                emptyText="No documents uploaded for this vehicle."
                                columns=${[
                                    { key: 'type', label: 'Document Type' },
                                    { key: 'reference_number', label: 'Ref #' },
                                    { key: 'expiry_date', label: 'Expiry' },
                                    { key: 'status', label: 'Status', render: (d) => html`<${StatusChip} value=${d.status} />` },
                                ]}
                            />
                        </${MUI.Box}>
                    `}
                    ${detailCard.type === 'invoice-detail' && html`
                        <${MUI.Box}>
                            <${MUI.Typography} variant="body2" sx=${{ mb: 1.5 }}>
                                Total: <strong>${formatCurrency(detailCard.data.total_amount)}</strong> • Balance Due: <strong>${formatCurrency(detailCard.data.balance_due)}</strong> • <${StatusChip} value=${detailCard.data.status} />
                            </${MUI.Typography}>
                            <${ResponsiveDataGrid}
                                rows=${(detailCard.data.items || []).map((it, i) => ({ ...it, id: i }))}
                                columns=${[
                                    { key: 'service_name', label: 'Service' },
                                    { key: 'description', label: 'Description' },
                                    { key: 'quantity', label: 'Qty' },
                                    { key: 'unit_price', label: 'Unit Price', align: 'right', render: (it) => formatCurrency(it.unit_price) },
                                    { key: 'line_total', label: 'Total', align: 'right', render: (it) => formatCurrency(it.line_total) },
                                ]}
                            />
                        </${MUI.Box}>
                    `}
                </${MUI.Card}>
            `}

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
                            render: (r) => html`
                                <${MUI.Stack} direction="row" spacing=${0.5} justifyContent="flex-end">
                                    <${MUI.Button} size="small" href="/portal/vehicles/${r.id}/card/">Card</${MUI.Button}>
                                    <${MUI.Button} size="small" href="/verify/vehicle/${r.qr_token}/" target="_blank">Verify QR</${MUI.Button}>
                                </${MUI.Stack}>
                            `,
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

            ${tab === 5 && html`
                <${ResponsiveDataGrid}
                    loading=${loading}
                    rows=${notifications}
                    columns=${[
                        { key: 'title', label: 'Title' },
                        { key: 'message', label: 'Message' },
                        { key: 'status', label: 'Status', render: (r) => html`<${StatusChip} value=${r.status} />` },
                        {
                            key: 'actions',
                            label: 'Action',
                            align: 'right',
                            render: (r) => r.status !== 'READ' && html`
                                <${MUI.Button} size="small" onClick=${() => handleMarkRead(r.id)}>Mark Read</${MUI.Button}>
                            `,
                        },
                    ]}
                />
            `}

            ${tab === 6 && html`
                <${ResponsiveDataGrid}
                    loading=${loading}
                    rows=${complaints}
                    columns=${[
                        { key: 'ticket_number', label: 'Ticket #' },
                        { key: 'title', label: 'Subject' },
                        { key: 'severity', label: 'Severity', render: (r) => html`<${StatusChip} value=${r.severity} />` },
                        { key: 'status', label: 'Status', render: (r) => html`<${StatusChip} value=${r.status} />` },
                    ]}
                />
            `}

            <${ResponsiveDialog}
                open=${vehOpen}
                onClose=${() => setVehOpen(false)}
                title="Register Commercial Truck or Trailer"
                maxWidth="md"
                actions=${html`
                    <${MUI.Button} onClick=${() => setVehOpen(false)}>Cancel</${MUI.Button}>
                    <${MUI.Button} variant="contained" onClick=${handleRegisterVehicle}>Submit Vehicle</${MUI.Button}>
                `}
            >
                <${MUI.Box} sx=${{ pt: 1 }}>
                    <${VehicleFieldsSection}
                        value=${vehForm}
                        categories=${categories}
                        fuelTypes=${fuelTypes}
                        onChange=${setVehForm}
                    />
                </${MUI.Box}>
            </${ResponsiveDialog}>

            <${ResponsiveDialog}
                open=${ticketOpen}
                onClose=${() => setTicketOpen(false)}
                title="Submit Grievance or Support Ticket"
                actions=${html`
                    <${MUI.Button} onClick=${() => setTicketOpen(false)}>Cancel</${MUI.Button}>
                    <${MUI.Button} variant="contained" onClick=${handleSubmitTicket}>Submit Ticket</${MUI.Button}>
                `}
            >
                <${MUI.Stack} spacing=${2} sx=${{ pt: 1 }}>
                    <${MUI.TextField} label="Title" fullWidth value=${ticketForm.title} onChange=${(e) => setTicketForm({ ...ticketForm, title: e.target.value })} />
                    <${MUI.TextField} label="Location" fullWidth value=${ticketForm.location} onChange=${(e) => setTicketForm({ ...ticketForm, location: e.target.value })} />
                    <${MUI.TextField} select label="Vehicle (optional)" fullWidth value=${ticketForm.vehicle} onChange=${(e) => setTicketForm({ ...ticketForm, vehicle: e.target.value })}>
                        <${MUI.MenuItem} value="">None</${MUI.MenuItem}>
                        ${vehicles.map((v) => html`<${MUI.MenuItem} key=${v.id} value=${v.id}>${v.registration_number}</${MUI.MenuItem}>`)}
                    </${MUI.TextField}>
                    <${MUI.TextField} label="Description" fullWidth multiline rows=${3} value=${ticketForm.description} onChange=${(e) => setTicketForm({ ...ticketForm, description: e.target.value })} />
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
                title="Commercial Driver Self-Service Portal"
                subtitle="Your driving licence validity, NTSA commercial endorsement status, and assigned truck/trailer compliance."
            />
            <${MUI.Grid} container spacing=${2} sx=${{ mb: 3 }}>
                <${MUI.Grid} size=${{ xs: 12, sm: 4 }}>
                    <${StatCard} title="Driver Status" value=${drv.status} subtitle="DL: ${drv.driving_license_number}${drv.dl_class ? ` (${drv.dl_class})` : ''}" icon="badge" color="primary" />
                </${MUI.Grid}>
                <${MUI.Grid} size=${{ xs: 12, sm: 4 }}>
                    <${StatCard} title="DL Validity" value="${data.dl_days_remaining ?? '—'} days" subtitle="Expires ${drv.dl_expiry_date}" icon="credit_card" color="success" />
                </${MUI.Grid}>
                <${MUI.Grid} size=${{ xs: 12, sm: 4 }}>
                    <${StatCard} title="NTSA Endorsement" value="${data.psv_days_remaining ?? '—'} days" subtitle="${drv.psv_badge_number || 'N/A'}" icon="verified" color="info" />
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
