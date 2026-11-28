import { React, MUI, html, apiFetch, extractList, formatCurrency, formatDateTime } from '../api.js';
import { MaterialIcon, PageHeader, ResponsiveDataGrid, ResponsiveDialog, StatCard, StatusChip } from '../components.js';

const DOC_CATEGORIES = [
    ['INSPECTION', 'Vehicle Inspection Certificate'],
    ['INSURANCE', 'Motor Commercial Insurance Certificate'],
    ['KENHA_PERMIT', 'KeNHA Road Authority Permit'],
    ['NTSA_RSL', 'NTSA Road Service Licence'],
    ['COUNTY_PERMIT', 'County Transport Business Permit'],
    ['SPEED_GOVERNOR', 'Speed Governor Certificate'],
    ['POLICE_CLEARANCE', 'Police Clearance / Good Conduct'],
    ['DRIVER_LICENSE', 'Driving License Commercial Endorsement'],
    ['SACCO_DOC', 'SACCO Agreement / Bylaws'],
    ['OTHER', 'Other Approved Document'],
];

const SERVICE_CATEGORIES = [
    ['MEMBERSHIP', 'Membership Registration & Onboarding'],
    ['SUBSCRIPTION', 'Monthly / Annual SACCO Subscriptions'],
    ['RENEWAL', 'Document Renewal Processing Fee'],
    ['STATUTORY', 'Statutory Government Charges (Pass-through)'],
    ['LEVY', 'Welfare Levy & Development Contribution'],
    ['PENALTY', 'Late Payment Penalty'],
    ['OTHER', 'Other Transport Services'],
];

const NOTIF_CHANNELS = [
    ['SMS', "Africa's Talking SMS"],
    ['WHATSAPP', 'Meta WhatsApp'],
    ['EMAIL', 'Email (SMTP)'],
    ['IN_APP', 'In-App Notification'],
];

const PROVIDERS = [
    ['postgresql', 'PostgreSQL DB'],
    ['redis', 'Redis Cache'],
    ['celery', 'Celery Broker'],
    ['daraja', 'Safaricom Daraja'],
    ['africastalking', "Africa's Talking SMS"],
    ['whatsapp', 'Meta WhatsApp'],
    ['smtp', 'SMTP Email'],
];

export function SuperAdminConsolePage({ notify, onNavigate }) {
    const [tab, setTab] = React.useState(0);
    const [loading, setLoading] = React.useState(true);
    const [overview, setOverview] = React.useState(null);
    const [portalUsers, setPortalUsers] = React.useState([]);
    const [docTypes, setDocTypes] = React.useState([]);
    const [serviceItems, setServiceItems] = React.useState([]);
    const [templates, setTemplates] = React.useState([]);
    const [sequences, setSequences] = React.useState([]);
    const [healthLogs, setHealthLogs] = React.useState([]);

    const [docDialog, setDocDialog] = React.useState(null);
    const [svcDialog, setSvcDialog] = React.useState(null);
    const [priceTarget, setPriceTarget] = React.useState(null);
    const [priceAmount, setPriceAmount] = React.useState('');
    const [tplDialog, setTplDialog] = React.useState(null);

    const loadAll = React.useCallback(async () => {
        setLoading(true);
        try {
            const [ov, opUsers, dt, si, nt, sq, hl] = await Promise.all([
                apiFetch('/api/v1/superadmin/overview/'),
                apiFetch('/api/v1/users/?scope=operational'),
                apiFetch('/api/v1/document-types/'),
                apiFetch('/api/v1/service-items/'),
                apiFetch('/api/v1/notification-templates/'),
                apiFetch('/settings/api/v1/sequences/'),
                apiFetch('/settings/api/v1/health-logs/'),
            ]);
            setOverview(ov);
            setPortalUsers(extractList(opUsers));
            setDocTypes(extractList(dt));
            setServiceItems(extractList(si));
            setTemplates(extractList(nt));
            setSequences(extractList(sq));
            setHealthLogs(extractList(hl));
        } catch (err) {
            notify(err.message, 'error');
        } finally {
            setLoading(false);
        }
    }, [notify]);

    React.useEffect(() => { loadAll(); }, [loadAll]);

    const runAction = async (url, label, body = {}) => {
        try {
            const res = await apiFetch(url, { method: 'POST', body });
            notify(`${label} completed.`, 'success');
            loadAll();
            return res;
        } catch (err) {
            notify(err.message, 'error');
            return null;
        }
    };

    const saveDocType = async () => {
        try {
            const thresholds = String(docDialog.thresholds_text || '30,14,7,3,0')
                .split(',')
                .map((x) => parseInt(x.trim(), 10))
                .filter((n) => !Number.isNaN(n));
            const payload = {
                name: docDialog.name,
                category: docDialog.category,
                standard_validity_months: Number(docDialog.standard_validity_months || 12),
                reminder_thresholds: thresholds,
                is_mandatory_for_vehicle: Boolean(docDialog.is_mandatory_for_vehicle),
                is_mandatory_for_driver: Boolean(docDialog.is_mandatory_for_driver),
            };
            if (docDialog.id) {
                await apiFetch(`/api/v1/document-types/${docDialog.id}/`, { method: 'PATCH', body: payload });
                notify('Document type updated.', 'success');
            } else {
                await apiFetch('/api/v1/document-types/', { method: 'POST', body: payload });
                notify('Document type created.', 'success');
            }
            setDocDialog(null);
            loadAll();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const deleteDocType = async (id) => {
        try {
            await apiFetch(`/api/v1/document-types/${id}/`, { method: 'DELETE' });
            notify('Document type deleted.', 'info');
            loadAll();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const saveServiceItem = async () => {
        try {
            const payload = {
                code: svcDialog.code,
                name: svcDialog.name,
                category: svcDialog.category,
                description: svcDialog.description || '',
                is_statutory: Boolean(svcDialog.is_statutory),
                is_active: svcDialog.is_active !== false,
            };
            let saved = null;
            if (svcDialog.id) {
                saved = await apiFetch(`/api/v1/service-items/${svcDialog.id}/`, { method: 'PATCH', body: payload });
                notify('Service item updated.', 'success');
            } else {
                saved = await apiFetch('/api/v1/service-items/', { method: 'POST', body: payload });
                if (svcDialog.initial_price) {
                    await apiFetch(`/api/v1/service-items/${saved.id}/set_price/`, {
                        method: 'POST',
                        body: { amount: svcDialog.initial_price },
                    });
                }
                notify('Service item created.', 'success');
            }
            setSvcDialog(null);
            loadAll();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const savePriceTier = async () => {
        if (!priceTarget) return;
        await runAction(`/api/v1/service-items/${priceTarget.id}/set_price/`, `Price updated for ${priceTarget.code}`, { amount: priceAmount });
        setPriceTarget(null);
        setPriceAmount('');
    };

    const saveTemplate = async () => {
        try {
            const payload = {
                code: tplDialog.code,
                name: tplDialog.name,
                channel: tplDialog.channel,
                subject: tplDialog.subject || '',
                body_template: tplDialog.body_template,
                meta_template_name: tplDialog.meta_template_name || '',
                is_active: tplDialog.is_active !== false,
            };
            if (tplDialog.id) {
                await apiFetch(`/api/v1/notification-templates/${tplDialog.id}/`, { method: 'PATCH', body: payload });
                notify('Notification template updated.', 'success');
            } else {
                await apiFetch('/api/v1/notification-templates/', { method: 'POST', body: payload });
                notify('Notification template created.', 'success');
            }
            setTplDialog(null);
            loadAll();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const u = overview?.users || {};
    const sec = overview?.security || {};
    const reg = overview?.registries || {};

    return html`
        <${MUI.Box}>
            <${PageHeader}
                title="SuperAdmin Control Center"
                subtitle="Unified Material UI administration replacing Django Core Admin — full authority over security, master registries, branding, and system jobs."
                action=${html`
                    <${MUI.Stack} direction="row" spacing=${1} flexWrap="wrap">
                        <${MUI.Button} variant="outlined" startIcon=${html`<${MaterialIcon} name="manage_accounts" />`} onClick=${() => onNavigate('staff')}>
                            Staff & Roles
                        </${MUI.Button}>
                        <${MUI.Button} variant="outlined" startIcon=${html`<${MaterialIcon} name="tune" />`} onClick=${() => onNavigate('settings')}>
                            Config & Branding
                        </${MUI.Button}>
                        <${MUI.Button} variant="contained" startIcon=${html`<${MaterialIcon} name="refresh" />`} onClick=${loadAll}>
                            Refresh
                        </${MUI.Button}>
                    </${MUI.Stack}>
                `}
            />

            <${MUI.Grid} container spacing=${2} sx=${{ mb: 3 }}>
                <${MUI.Grid} size=${{ xs: 6, sm: 4, md: 2 }}>
                    <${StatCard} title="Staff Users" value="${u.staff_active ?? 0}/${u.staff_total ?? 0}" subtitle="${u.super_admins ?? 0} Super Admin" icon="admin_panel_settings" color="primary" />
                </${MUI.Grid}>
                <${MUI.Grid} size=${{ xs: 6, sm: 4, md: 2 }}>
                    <${StatCard} title="Portal Accounts" value="${u.operational_active ?? 0}/${u.operational_total ?? 0}" subtitle="Members & Drivers" icon="groups" color="info" />
                </${MUI.Grid}>
                <${MUI.Grid} size=${{ xs: 6, sm: 4, md: 2 }}>
                    <${StatCard} title="Active Sessions" value=${sec.active_sessions ?? 0} subtitle="${u.must_change_password ?? 0} pwd reset pending" icon="vpn_key" color="success" />
                </${MUI.Grid}>
                <${MUI.Grid} size=${{ xs: 6, sm: 4, md: 2 }}>
                    <${StatCard} title="Axes Lockouts" value=${sec.axes_attempts_count ?? 0} subtitle="Brute-force records" icon="security" color=${(sec.axes_attempts_count || 0) > 0 ? 'error' : 'success'} />
                </${MUI.Grid}>
                <${MUI.Grid} size=${{ xs: 6, sm: 4, md: 2 }}>
                    <${StatCard} title="Config Registry" value=${reg.system_configurations ?? 0} subtitle="${reg.pending_change_requests ?? 0} pending CRs" icon="settings_applications" color="warning" />
                </${MUI.Grid}>
                <${MUI.Grid} size=${{ xs: 6, sm: 4, md: 2 }}>
                    <${StatCard} title="Branding Ver" value="v${reg.branding_version ?? 1}" subtitle="${reg.branding_versions_total ?? 1} snapshots" icon="palette" color="secondary" />
                </${MUI.Grid}>
            </${MUI.Grid}>

            <${MUI.Card} sx=${{ p: 2, mb: 3 }}>
                <${MUI.Typography} variant="subtitle2" sx=${{ mb: 1.5, fontWeight: 700, textTransform: 'uppercase', color: 'text.secondary' }}>
                    System Operations & Maintenance Jobs
                </${MUI.Typography}>
                <${MUI.Stack} direction="row" spacing=${1.5} flexWrap="wrap" useFlexGap>
                    <${MUI.Button} variant="contained" size="small" startIcon=${html`<${MaterialIcon} name="verified_user" />`} onClick=${() => runAction('/api/v1/compliance/scan/', 'Daily compliance scan')}>
                        Run Compliance Scan
                    </${MUI.Button}>
                    <${MUI.Button} variant="contained" size="small" color="info" startIcon=${html`<${MaterialIcon} name="fact_check" />`} onClick=${() => runAction('/api/v1/reconciliation-runs/execute/', 'Payment reconciliation')}>
                        Run Reconciliation
                    </${MUI.Button}>
                    <${MUI.Button} variant="contained" size="small" color="warning" startIcon=${html`<${MaterialIcon} name="notifications_active" />`} onClick=${() => runAction('/api/v1/superadmin/run-invoice-reminders/', 'Overdue invoice reminders')}>
                        Send Overdue Reminders
                    </${MUI.Button}>
                    <${MUI.Button} variant="outlined" size="small" color="error" startIcon=${html`<${MaterialIcon} name="lock_open" />`} onClick=${() => runAction('/api/v1/superadmin/clear-lockouts/', 'Axes lockout clear')}>
                        Clear All Axes Lockouts
                    </${MUI.Button}>
                    <${MUI.Button} variant="outlined" size="small" color="error" startIcon=${html`<${MaterialIcon} name="logout" />`} onClick=${() => runAction('/api/v1/superadmin/terminate-sessions/', 'Other sessions termination')}>
                        Terminate Other Sessions
                    </${MUI.Button}>
                    <${MUI.Button} variant="outlined" size="small" startIcon=${html`<${MaterialIcon} name="fingerprint" />`} onClick=${() => onNavigate('audit')}>
                        Full Audit Trail (${sec.audit_logs_total ?? 0})
                    </${MUI.Button}>
                </${MUI.Stack}>
            </${MUI.Card}>

            <${MUI.Tabs} value=${tab} onChange=${(_, v) => setTab(v)} variant="scrollable" scrollButtons="auto" sx=${{ mb: 2 }}>
                <${MUI.Tab} label="Security & Portal Accounts" />
                <${MUI.Tab} label="Document Types (${docTypes.length})" />
                <${MUI.Tab} label="Billing Services (${serviceItems.length})" />
                <${MUI.Tab} label="Notification Templates (${templates.length})" />
                <${MUI.Tab} label="Sequences & Health Logs" />
            </${MUI.Tabs}>

            ${tab === 0 && html`
                <${MUI.Stack} spacing=${3}>
                    <${MUI.Box}>
                        <${MUI.Typography} variant="h6" sx=${{ mb: 1 }}>Axes Brute-Force Attempts & Lockouts</${MUI.Typography}>
                        <${ResponsiveDataGrid}
                            loading=${loading}
                            rows=${sec.lockouts || []}
                            emptyText="No Axes lockout or failed login attempt records."
                            columns=${[
                                { key: 'username', label: 'Username' },
                                { key: 'ip_address', label: 'IP Address', render: (r) => html`<span className="nht-mono">${r.ip_address}</span>` },
                                { key: 'failures', label: 'Failures' },
                                { key: 'attempt_time', label: 'Last Attempt', render: (r) => formatDateTime(r.attempt_time) },
                                {
                                    key: 'actions',
                                    label: 'Action',
                                    align: 'right',
                                    render: (r) => html`
                                        <${MUI.Button} size="small" color="success" onClick=${() => runAction('/api/v1/superadmin/clear-lockouts/', `Unlock ${r.username}`, { username: r.username !== '—' ? r.username : '', ip_address: r.ip_address !== '—' ? r.ip_address : '' })}>
                                            Unlock
                                        </${MUI.Button}>
                                    `,
                                },
                            ]}
                        />
                    </${MUI.Box}>

                    <${MUI.Box}>
                        <${MUI.Typography} variant="h6" sx=${{ mb: 1 }}>Member & Driver Operational Portal Accounts</${MUI.Typography}>
                        <${ResponsiveDataGrid}
                            loading=${loading}
                            rows=${portalUsers}
                            emptyText="No operational portal accounts found."
                            columns=${[
                                { key: 'username', label: 'Username', render: (r) => html`<strong>${r.username}</strong>` },
                                { key: 'full_name', label: 'Full Name' },
                                { key: 'email', label: 'Email' },
                                { key: 'role_display', label: 'Portal Role' },
                                { key: 'is_active', label: 'Status', render: (r) => html`<${StatusChip} value=${r.is_active ? 'ACTIVE' : 'SUSPENDED'} />` },
                                {
                                    key: 'actions',
                                    label: 'Controls',
                                    align: 'right',
                                    render: (r) => html`
                                        <${MUI.Stack} direction="row" spacing=${0.5} justifyContent="flex-end">
                                            <${MUI.Button} size="small" color="info" onClick=${() => runAction(`/api/v1/users/${r.id}/initiate_recovery/`, `Password recovery for ${r.username}`, { send_email: true })}>
                                                Reset Pwd
                                            </${MUI.Button}>
                                            <${MUI.Button} size="small" color=${r.is_active ? 'warning' : 'success'} onClick=${() => runAction(`/api/v1/users/${r.id}/toggle_active/`, `Status toggle for ${r.username}`)}>
                                                ${r.is_active ? 'Suspend' : 'Activate'}
                                            </${MUI.Button}>
                                        </${MUI.Stack}>
                                    `,
                                },
                            ]}
                        />
                    </${MUI.Box}>
                </${MUI.Stack}>
            `}

            ${tab === 1 && html`
                <${MUI.Box}>
                    <${MUI.Box} sx=${{ mb: 2, display: 'flex', justifyContent: 'flex-end' }}>
                        <${MUI.Button}
                            variant="contained"
                            startIcon=${html`<${MaterialIcon} name="add" />`}
                            onClick=${() => setDocDialog({ name: '', category: 'INSPECTION', standard_validity_months: 12, thresholds_text: '30,14,7,3,0', is_mandatory_for_vehicle: true, is_mandatory_for_driver: false })}
                        >
                            New Document Type
                        </${MUI.Button}>
                    </${MUI.Box}>
                    <${ResponsiveDataGrid}
                        loading=${loading}
                        rows=${docTypes}
                        columns=${[
                            { key: 'name', label: 'Document Type', render: (r) => html`<strong>${r.name}</strong>` },
                            { key: 'category_display', label: 'Category' },
                            { key: 'standard_validity_months', label: 'Validity (Mo)' },
                            { key: 'reminder_thresholds', label: 'Alert Days', render: (r) => (r.reminder_thresholds || []).join(', ') },
                            { key: 'is_mandatory_for_vehicle', label: 'Vehicle Req', render: (r) => r.is_mandatory_for_vehicle ? 'Yes' : 'No' },
                            { key: 'is_mandatory_for_driver', label: 'Driver Req', render: (r) => r.is_mandatory_for_driver ? 'Yes' : 'No' },
                            {
                                key: 'actions',
                                label: 'Actions',
                                align: 'right',
                                render: (r) => html`
                                    <${MUI.Stack} direction="row" spacing=${0.5} justifyContent="flex-end">
                                        <${MUI.Button} size="small" onClick=${() => setDocDialog({ ...r, thresholds_text: (r.reminder_thresholds || []).join(',') })}>Edit</${MUI.Button}>
                                        <${MUI.Button} size="small" color="error" onClick=${() => deleteDocType(r.id)}>Delete</${MUI.Button}>
                                    </${MUI.Stack}>
                                `,
                            },
                        ]}
                    />
                </${MUI.Box}>
            `}

            ${tab === 2 && html`
                <${MUI.Box}>
                    <${MUI.Box} sx=${{ mb: 2, display: 'flex', justifyContent: 'flex-end' }}>
                        <${MUI.Button}
                            variant="contained"
                            startIcon=${html`<${MaterialIcon} name="add" />`}
                            onClick=${() => setSvcDialog({ code: '', name: '', category: 'SUBSCRIPTION', description: '', is_statutory: false, is_active: true, initial_price: '1000.00' })}
                        >
                            New Billing Service
                        </${MUI.Button}>
                    </${MUI.Box}>
                    <${ResponsiveDataGrid}
                        loading=${loading}
                        rows=${serviceItems}
                        columns=${[
                            { key: 'code', label: 'Code', render: (r) => html`<span className="nht-mono"><strong>${r.code}</strong></span>` },
                            { key: 'name', label: 'Service Name' },
                            { key: 'category_display', label: 'Category' },
                            { key: 'is_statutory', label: 'Statutory', render: (r) => html`<${StatusChip} value=${r.is_statutory ? 'INFO' : 'ACTIVE'} label=${r.is_statutory ? 'Statutory Pass-Through' : 'SACCO Revenue'} />` },
                            { key: 'default_amount', label: 'Active Price', align: 'right', render: (r) => formatCurrency(r.default_amount) },
                            { key: 'is_active', label: 'Status', render: (r) => html`<${StatusChip} value=${r.is_active ? 'ACTIVE' : 'CLOSED'} />` },
                            {
                                key: 'actions',
                                label: 'Actions',
                                align: 'right',
                                render: (r) => html`
                                    <${MUI.Stack} direction="row" spacing=${0.5} justifyContent="flex-end">
                                        <${MUI.Button} size="small" onClick=${() => setSvcDialog({ ...r })}>Edit</${MUI.Button}>
                                        <${MUI.Button} size="small" color="success" onClick=${() => { setPriceTarget(r); setPriceAmount(r.default_amount || '0.00'); }}>Set Price</${MUI.Button}>
                                    </${MUI.Stack}>
                                `,
                            },
                        ]}
                    />
                </${MUI.Box}>
            `}

            ${tab === 3 && html`
                <${MUI.Box}>
                    <${MUI.Box} sx=${{ mb: 2, display: 'flex', justifyContent: 'flex-end' }}>
                        <${MUI.Button}
                            variant="contained"
                            startIcon=${html`<${MaterialIcon} name="add" />`}
                            onClick=${() => setTplDialog({ code: '', name: '', channel: 'SMS', subject: '', body_template: '', meta_template_name: '', is_active: true })}
                        >
                            New Notification Template
                        </${MUI.Button}>
                    </${MUI.Box}>
                    <${ResponsiveDataGrid}
                        loading=${loading}
                        rows=${templates}
                        columns=${[
                            { key: 'code', label: 'Code', render: (r) => html`<span className="nht-mono"><strong>${r.code}</strong></span>` },
                            { key: 'name', label: 'Template Name' },
                            { key: 'channel_display', label: 'Channel' },
                            { key: 'subject', label: 'Subject' },
                            { key: 'is_active', label: 'Status', render: (r) => html`<${StatusChip} value=${r.is_active ? 'ACTIVE' : 'CLOSED'} />` },
                            {
                                key: 'actions',
                                label: 'Action',
                                align: 'right',
                                render: (r) => html`<${MUI.Button} size="small" onClick=${() => setTplDialog({ ...r })}>Edit</${MUI.Button}>`,
                            },
                        ]}
                    />
                </${MUI.Box}>
            `}

            ${tab === 4 && html`
                <${MUI.Stack} spacing=${3}>
                    <${MUI.Box}>
                        <${MUI.Typography} variant="h6" sx=${{ mb: 1 }}>Atomic Number Sequences</${MUI.Typography}>
                        <${ResponsiveDataGrid}
                            loading=${loading}
                            rows=${sequences}
                            columns=${[
                                { key: 'prefix', label: 'Prefix', render: (r) => html`<span className="nht-mono"><strong>${r.prefix}</strong></span>` },
                                { key: 'year', label: 'Fiscal Year' },
                                { key: 'last_number', label: 'Last Allocated Sequence' },
                                { key: 'updated_at', label: 'Last Updated', render: (r) => formatDateTime(r.updated_at) },
                            ]}
                        />
                    </${MUI.Box}>

                    <${MUI.Box}>
                        <${MUI.Typography} variant="h6" sx=${{ mb: 1 }}>Provider Connectivity Probes & Health Log</${MUI.Typography}>
                        <${MUI.Stack} direction="row" spacing=${1} flexWrap="wrap" useFlexGap sx=${{ mb: 2 }}>
                            ${PROVIDERS.map(([code, label]) => html`
                                <${MUI.Button}
                                    key=${code}
                                    size="small"
                                    variant="outlined"
                                    onClick=${() => runAction('/settings/api/v1/test-provider/', `Probe ${label}`, { provider: code })}
                                >
                                    Test ${label}
                                </${MUI.Button}>
                            `)}
                        </${MUI.Stack}>
                        <${ResponsiveDataGrid}
                            loading=${loading}
                            rows=${healthLogs}
                            columns=${[
                                { key: 'service_name', label: 'Service', render: (r) => html`<span className="nht-mono">${r.service_name}</span>` },
                                { key: 'status', label: 'Status', render: (r) => html`<${StatusChip} value=${r.status} />` },
                                { key: 'response_time_ms', label: 'Latency', render: (r) => `${Number(r.response_time_ms || 0).toFixed(1)} ms` },
                                { key: 'error_message', label: 'Message', render: (r) => r.error_message || 'OK' },
                                { key: 'tested_at', label: 'Tested At', render: (r) => formatDateTime(r.tested_at) },
                            ]}
                        />
                    </${MUI.Box}>
                </${MUI.Stack}>
            `}

            <${ResponsiveDialog}
                open=${Boolean(docDialog)}
                onClose=${() => setDocDialog(null)}
                title=${docDialog?.id ? `Edit Document Type: ${docDialog.name}` : 'Create Regulatory Document Type'}
                actions=${html`
                    <${MUI.Button} onClick=${() => setDocDialog(null)}>Cancel</${MUI.Button}>
                    <${MUI.Button} variant="contained" onClick=${saveDocType}>Save Document Type</${MUI.Button}>
                `}
            >
                ${docDialog && html`
                    <${MUI.Stack} spacing=${2} sx=${{ pt: 1 }}>
                        <${MUI.TextField} label="Name" fullWidth value=${docDialog.name || ''} onChange=${(e) => setDocDialog({ ...docDialog, name: e.target.value })} />
                        <${MUI.TextField} select label="Category" fullWidth value=${docDialog.category || 'INSPECTION'} onChange=${(e) => setDocDialog({ ...docDialog, category: e.target.value })}>
                            ${DOC_CATEGORIES.map(([v, l]) => html`<${MUI.MenuItem} key=${v} value=${v}>${l}</${MUI.MenuItem}>`)}
                        </${MUI.TextField}>
                        <${MUI.TextField} label="Standard Validity (Months)" type="number" fullWidth value=${docDialog.standard_validity_months ?? 12} onChange=${(e) => setDocDialog({ ...docDialog, standard_validity_months: e.target.value })} />
                        <${MUI.TextField} label="Reminder Thresholds (comma-separated days)" fullWidth value=${docDialog.thresholds_text || ''} onChange=${(e) => setDocDialog({ ...docDialog, thresholds_text: e.target.value })} />
                        <${MUI.FormControlLabel}
                            control=${html`<${MUI.Checkbox} checked=${Boolean(docDialog.is_mandatory_for_vehicle)} onChange=${(e) => setDocDialog({ ...docDialog, is_mandatory_for_vehicle: e.target.checked })} />`}
                            label="Mandatory for Vehicle Fleet Compliance"
                        />
                        <${MUI.FormControlLabel}
                            control=${html`<${MUI.Checkbox} checked=${Boolean(docDialog.is_mandatory_for_driver)} onChange=${(e) => setDocDialog({ ...docDialog, is_mandatory_for_driver: e.target.checked })} />`}
                            label="Mandatory for Driver Certification"
                        />
                    </${MUI.Stack}>
                `}
            </${ResponsiveDialog}>

            <${ResponsiveDialog}
                open=${Boolean(svcDialog)}
                onClose=${() => setSvcDialog(null)}
                title=${svcDialog?.id ? `Edit Service Item: ${svcDialog.code}` : 'Create Billing Service Item'}
                actions=${html`
                    <${MUI.Button} onClick=${() => setSvcDialog(null)}>Cancel</${MUI.Button}>
                    <${MUI.Button} variant="contained" onClick=${saveServiceItem}>Save Service</${MUI.Button}>
                `}
            >
                ${svcDialog && html`
                    <${MUI.Stack} spacing=${2} sx=${{ pt: 1 }}>
                        <${MUI.TextField} label="Service Code" fullWidth value=${svcDialog.code || ''} onChange=${(e) => setSvcDialog({ ...svcDialog, code: e.target.value })} />
                        <${MUI.TextField} label="Service Name" fullWidth value=${svcDialog.name || ''} onChange=${(e) => setSvcDialog({ ...svcDialog, name: e.target.value })} />
                        <${MUI.TextField} select label="Category" fullWidth value=${svcDialog.category || 'SUBSCRIPTION'} onChange=${(e) => setSvcDialog({ ...svcDialog, category: e.target.value })}>
                            ${SERVICE_CATEGORIES.map(([v, l]) => html`<${MUI.MenuItem} key=${v} value=${v}>${l}</${MUI.MenuItem}>`)}
                        </${MUI.TextField}>
                        ${!svcDialog.id && html`
                            <${MUI.TextField} label="Initial Fee Amount (KES)" type="number" fullWidth value=${svcDialog.initial_price || ''} onChange=${(e) => setSvcDialog({ ...svcDialog, initial_price: e.target.value })} />
                        `}
                        <${MUI.TextField} label="Description" fullWidth multiline rows=${2} value=${svcDialog.description || ''} onChange=${(e) => setSvcDialog({ ...svcDialog, description: e.target.value })} />
                        <${MUI.FormControlLabel}
                            control=${html`<${MUI.Checkbox} checked=${Boolean(svcDialog.is_statutory)} onChange=${(e) => setSvcDialog({ ...svcDialog, is_statutory: e.target.checked })} />`}
                            label="Statutory Government Pass-Through Fee"
                        />
                        <${MUI.FormControlLabel}
                            control=${html`<${MUI.Checkbox} checked=${svcDialog.is_active !== false} onChange=${(e) => setSvcDialog({ ...svcDialog, is_active: e.target.checked })} />`}
                            label="Active"
                        />
                    </${MUI.Stack}>
                `}
            </${ResponsiveDialog}>

            <${ResponsiveDialog}
                open=${Boolean(priceTarget)}
                onClose=${() => setPriceTarget(null)}
                title=${`Update Fee Schedule: ${priceTarget?.code || ''}`}
                actions=${html`
                    <${MUI.Button} onClick=${() => setPriceTarget(null)}>Cancel</${MUI.Button}>
                    <${MUI.Button} variant="contained" color="success" onClick=${savePriceTier}>Publish Fee (KES)</${MUI.Button}>
                `}
            >
                <${MUI.TextField} label="New Amount (KES)" type="number" fullWidth sx=${{ mt: 1 }} value=${priceAmount} onChange=${(e) => setPriceAmount(e.target.value)} />
            </${ResponsiveDialog}>

            <${ResponsiveDialog}
                open=${Boolean(tplDialog)}
                onClose=${() => setTplDialog(null)}
                title=${tplDialog?.id ? `Edit Template: ${tplDialog.code}` : 'Create Notification Template'}
                actions=${html`
                    <${MUI.Button} onClick=${() => setTplDialog(null)}>Cancel</${MUI.Button}>
                    <${MUI.Button} variant="contained" onClick=${saveTemplate}>Save Template</${MUI.Button}>
                `}
            >
                ${tplDialog && html`
                    <${MUI.Stack} spacing=${2} sx=${{ pt: 1 }}>
                        <${MUI.TextField} label="Template Code" fullWidth value=${tplDialog.code || ''} onChange=${(e) => setTplDialog({ ...tplDialog, code: e.target.value })} />
                        <${MUI.TextField} label="Name" fullWidth value=${tplDialog.name || ''} onChange=${(e) => setTplDialog({ ...tplDialog, name: e.target.value })} />
                        <${MUI.TextField} select label="Channel" fullWidth value=${tplDialog.channel || 'SMS'} onChange=${(e) => setTplDialog({ ...tplDialog, channel: e.target.value })}>
                            ${NOTIF_CHANNELS.map(([v, l]) => html`<${MUI.MenuItem} key=${v} value=${v}>${l}</${MUI.MenuItem}>`)}
                        </${MUI.TextField}>
                        <${MUI.TextField} label="Email Subject (if Email)" fullWidth value=${tplDialog.subject || ''} onChange=${(e) => setTplDialog({ ...tplDialog, subject: e.target.value })} />
                        <${MUI.TextField} label="Body Template ({placeholder} syntax)" fullWidth multiline rows=${4} value=${tplDialog.body_template || ''} onChange=${(e) => setTplDialog({ ...tplDialog, body_template: e.target.value })} />
                        <${MUI.TextField} label="Meta WhatsApp Template Name" fullWidth value=${tplDialog.meta_template_name || ''} onChange=${(e) => setTplDialog({ ...tplDialog, meta_template_name: e.target.value })} />
                        <${MUI.FormControlLabel}
                            control=${html`<${MUI.Checkbox} checked=${tplDialog.is_active !== false} onChange=${(e) => setTplDialog({ ...tplDialog, is_active: e.target.checked })} />`}
                            label="Active"
                        />
                    </${MUI.Stack}>
                `}
            </${ResponsiveDialog}>
        </${MUI.Box}>
    `;
}

export function SettingsCenterPage({ notify, onRefreshMe }) {
    const [tab, setTab] = React.useState(0);
    const [profile, setProfile] = React.useState(null);
    const [versions, setVersions] = React.useState([]);
    const [logoFile, setLogoFile] = React.useState(null);
    const [monoFile, setMonoFile] = React.useState(null);
    const [changeNotes, setChangeNotes] = React.useState('');
    const [configs, setConfigs] = React.useState([]);
    const [catFilter, setCatFilter] = React.useState('');
    const [changeRequests, setChangeRequests] = React.useState([]);
    const [health, setHealth] = React.useState(null);
    const [loading, setLoading] = React.useState(true);
    const [editTarget, setEditTarget] = React.useState(null);
    const [configHistory, setConfigHistory] = React.useState([]);
    const [newValue, setNewValue] = React.useState('');
    const [reason, setReason] = React.useState('');
    const [impact, setImpact] = React.useState(null);

    const load = React.useCallback(async () => {
        setLoading(true);
        try {
            const [pRes, vRes, cRes, crRes] = await Promise.all([
                apiFetch('/settings/api/v1/company-profile/'),
                apiFetch('/settings/api/v1/company-profile/versions/'),
                apiFetch('/settings/api/v1/configs/'),
                apiFetch('/settings/api/v1/change-requests/'),
            ]);
            setProfile(pRes);
            setVersions(extractList(vRes));
            setConfigs(extractList(cRes));
            setChangeRequests(extractList(crRes));
        } catch (err) {
            notify(err.message, 'error');
        } finally {
            setLoading(false);
        }
    }, [notify]);

    React.useEffect(() => { load(); }, [load]);

    const openConfigEditor = async (cfg) => {
        setEditTarget(cfg);
        setNewValue(cfg.is_secret ? '' : String(cfg.display_value ?? ''));
        setImpact(null);
        setReason('');
        setConfigHistory([]);
        try {
            const hRes = await apiFetch(`/settings/api/v1/configs/${cfg.id}/history/`);
            setConfigHistory(extractList(hRes));
        } catch (_) {}
    };

    const handleRollbackConfig = async (targetVer) => {
        try {
            await apiFetch('/settings/api/v1/rollback/', {
                method: 'POST',
                body: { key: editTarget.key, target_version: targetVer, reason: reason || `Rollback to v${targetVer} via MUI Admin` },
            });
            notify(`Rolled back ${editTarget.key} to v${targetVer}.`, 'success');
            setEditTarget(null);
            load();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const handleExportConfigs = async () => {
        try {
            const payload = await apiFetch('/settings/api/v1/export/');
            const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `nht_sms_config_${new Date().toISOString().slice(0, 10)}.json`;
            a.click();
            URL.revokeObjectURL(url);
            notify('Configuration JSON exported.', 'success');
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const handleImportConfigs = async (e) => {
        const f = e.target.files?.[0];
        if (!f) return;
        try {
            const txt = await f.text();
            const parsed = JSON.parse(txt);
            const res = await apiFetch('/settings/api/v1/import/', { method: 'POST', body: parsed });
            notify(`Config import complete: ${res.updated ?? 0} updated, ${res.skipped ?? 0} skipped.`, 'success');
            load();
        } catch (err) {
            notify(err.message, 'error');
        } finally {
            e.target.value = '';
        }
    };

    const handleSaveBranding = async () => {
        try {
            const fd = new FormData();
            const fields = [
                'legal_name', 'trading_name', 'short_name', 'registration_number', 'tax_pin',
                'physical_address', 'postal_address', 'phone_numbers', 'official_email',
                'website', 'public_base_url', 'footer_text', 'primary_color', 'secondary_color',
            ];
            fields.forEach((f) => {
                if (profile[f] !== undefined && profile[f] !== null) fd.append(f, profile[f]);
            });
            fd.append('change_notes', changeNotes || 'Updated company profile & branding via MUI Admin');
            if (logoFile) fd.append('logo', logoFile);
            if (monoFile) fd.append('monochrome_logo', monoFile);

            const updated = await apiFetch('/settings/api/v1/company-profile/', { method: 'PATCH', body: fd });
            setProfile(updated);
            setLogoFile(null);
            setMonoFile(null);
            setChangeNotes('');
            notify(`Company profile & branding saved (v${updated.current_version}).`, 'success');
            load();
            if (onRefreshMe) onRefreshMe();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const handleDeleteLogo = async (type = 'primary') => {
        try {
            const updated = await apiFetch(`/settings/api/v1/company-profile/logo/?type=${type}`, { method: 'DELETE' });
            setProfile(updated);
            notify(`Removed ${type} company logo.`, 'info');
            load();
            if (onRefreshMe) onRefreshMe();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const runHealth = async () => {
        try {
            const res = await apiFetch('/settings/api/v1/health/');
            setHealth(res);
            notify('System diagnostics refreshed.', 'info');
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const testSingleProvider = async (provider) => {
        try {
            const res = await apiFetch('/settings/api/v1/test-provider/', { method: 'POST', body: { provider } });
            notify(`${provider}: ${res.status || 'Checked'} — ${res.message || res.error || 'Done'}`, res.status === 'HEALTHY' ? 'success' : 'warning');
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const assessImpact = async () => {
        try {
            const res = await apiFetch('/settings/api/v1/assess-impact/', {
                method: 'POST',
                body: { key: editTarget.key, proposed_value: newValue },
            });
            setImpact(res);
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const applyUpdate = async () => {
        try {
            await apiFetch('/settings/api/v1/update/', {
                method: 'POST',
                body: {
                    key: editTarget.key,
                    value: newValue,
                    reason: reason || 'Updated via MUI Admin',
                    expected_version: editTarget.version,
                    confirm_critical: true,
                },
            });
            notify(`Configuration ${editTarget.key} updated.`, 'success');
            setEditTarget(null);
            load();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const submitChangeRequest = async () => {
        try {
            await apiFetch('/settings/api/v1/change-requests/', {
                method: 'POST',
                body: { key: editTarget.key, proposed_value: newValue, justification: reason },
            });
            notify('Maker-Checker configuration change request submitted.', 'info');
            setEditTarget(null);
            load();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const handleCrAction = async (id, act) => {
        try {
            await apiFetch(`/settings/api/v1/change-requests/${id}/${act}/`, { method: 'POST', body: {} });
            notify(`Change request ${act}d.`, 'success');
            load();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const filteredConfigs = catFilter ? configs.filter((c) => c.category === catFilter) : configs;

    return html`
        <${MUI.Box}>
            <${PageHeader}
                title="System Configuration, Company Profile & Branding"
                subtitle="Centralized SACCO identity, logo management, encrypted settings registry, rollback, JSON backup/import, and diagnostics."
            />

            <${MUI.Tabs} value=${tab} onChange=${(_, v) => setTab(v)} variant="scrollable" scrollButtons="auto" sx=${{ mb: 2 }}>
                <${MUI.Tab} label="Company Profile & Branding" />
                <${MUI.Tab} label="Configuration Registry (${configs.length})" />
                <${MUI.Tab} label="Change Requests (${changeRequests.length})" />
                <${MUI.Tab} label="System Diagnostics" />
            </${MUI.Tabs}>

            ${tab === 0 && profile && html`
                <${MUI.Stack} spacing=${3}>
                    <${MUI.Card} sx=${{ p: 3 }}>
                        <${MUI.Box} sx=${{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2, flexWrap: 'wrap', gap: 1 }}>
                            <${MUI.Typography} variant="h6">Company Profile & Official Document Metadata</${MUI.Typography}>
                            <${MUI.Chip} color="primary" label=${`Active Branding v${profile.current_version}`} />
                        </${MUI.Box}>
                        <${MUI.Grid} container spacing=${2}>
                            <${MUI.Grid} size=${{ xs: 12, sm: 6 }}><${MUI.TextField} label="Legal Name" fullWidth value=${profile.legal_name || ''} onChange=${(e) => setProfile({ ...profile, legal_name: e.target.value })} /></${MUI.Grid}>
                            <${MUI.Grid} size=${{ xs: 12, sm: 4 }}><${MUI.TextField} label="Trading Name" fullWidth value=${profile.trading_name || ''} onChange=${(e) => setProfile({ ...profile, trading_name: e.target.value })} /></${MUI.Grid}>
                            <${MUI.Grid} size=${{ xs: 12, sm: 2 }}><${MUI.TextField} label="Acronym" fullWidth value=${profile.short_name || ''} onChange=${(e) => setProfile({ ...profile, short_name: e.target.value })} /></${MUI.Grid}>
                            <${MUI.Grid} size=${{ xs: 12, sm: 6 }}><${MUI.TextField} label="SACCO Registration No" fullWidth value=${profile.registration_number || ''} onChange=${(e) => setProfile({ ...profile, registration_number: e.target.value })} /></${MUI.Grid}>
                            <${MUI.Grid} size=${{ xs: 12, sm: 6 }}><${MUI.TextField} label="KRA PIN / Tax ID" fullWidth value=${profile.tax_pin || ''} onChange=${(e) => setProfile({ ...profile, tax_pin: e.target.value })} /></${MUI.Grid}>
                            <${MUI.Grid} size=${{ xs: 12, sm: 6 }}><${MUI.TextField} label="Physical Address" fullWidth value=${profile.physical_address || ''} onChange=${(e) => setProfile({ ...profile, physical_address: e.target.value })} /></${MUI.Grid}>
                            <${MUI.Grid} size=${{ xs: 12, sm: 6 }}><${MUI.TextField} label="Postal Address" fullWidth value=${profile.postal_address || ''} onChange=${(e) => setProfile({ ...profile, postal_address: e.target.value })} /></${MUI.Grid}>
                            <${MUI.Grid} size=${{ xs: 12, sm: 4 }}><${MUI.TextField} label="Telephone Numbers" fullWidth value=${profile.phone_numbers || ''} onChange=${(e) => setProfile({ ...profile, phone_numbers: e.target.value })} /></${MUI.Grid}>
                            <${MUI.Grid} size=${{ xs: 12, sm: 4 }}><${MUI.TextField} label="Official Email" fullWidth value=${profile.official_email || ''} onChange=${(e) => setProfile({ ...profile, official_email: e.target.value })} /></${MUI.Grid}>
                            <${MUI.Grid} size=${{ xs: 12, sm: 4 }}><${MUI.TextField} label="Website" fullWidth value=${profile.website || ''} onChange=${(e) => setProfile({ ...profile, website: e.target.value })} /></${MUI.Grid}>
                            <${MUI.Grid} size=${{ xs: 12, sm: 6 }}><${MUI.TextField} label="Public QR Verification Base URL (Optional)" placeholder="Leave blank to use internal endpoint" fullWidth value=${profile.public_base_url || ''} onChange=${(e) => setProfile({ ...profile, public_base_url: e.target.value })} /></${MUI.Grid}>
                            <${MUI.Grid} size=${{ xs: 6, sm: 3 }}><${MUI.TextField} label="Primary Brand Color" fullWidth value=${profile.primary_color || '#10315C'} onChange=${(e) => setProfile({ ...profile, primary_color: e.target.value })} /></${MUI.Grid}>
                            <${MUI.Grid} size=${{ xs: 6, sm: 3 }}><${MUI.TextField} label="Secondary Accent Color" fullWidth value=${profile.secondary_color || '#FF8A00'} onChange=${(e) => setProfile({ ...profile, secondary_color: e.target.value })} /></${MUI.Grid}>
                            <${MUI.Grid} size=${{ xs: 12 }}><${MUI.TextField} label="Document Footer Text" fullWidth value=${profile.footer_text || ''} onChange=${(e) => setProfile({ ...profile, footer_text: e.target.value })} /></${MUI.Grid}>
                        </${MUI.Grid}>

                        <${MUI.Divider} sx=${{ my: 3 }} />
                        <${MUI.Typography} variant="subtitle1" sx=${{ fontWeight: 700, mb: 2 }}>Official Company Logo Assets (PNG/JPEG, max 2 MB)</${MUI.Typography}>
                        <${MUI.Grid} container spacing=${3}>
                            <${MUI.Grid} size=${{ xs: 12, md: 6 }}>
                                <${MUI.Paper} variant="outlined" sx=${{ p: 2 }}>
                                    <${MUI.Typography} variant="subtitle2" sx=${{ mb: 1 }}>Primary Logo</${MUI.Typography}>
                                    ${profile.logo_url ? html`
                                        <${MUI.Box} sx=${{ mb: 1.5, display: 'flex', alignItems: 'center', gap: 2 }}>
                                            <img src=${profile.logo_url} alt="Primary Logo" style=${{ maxHeight: 72, maxWidth: 180, objectFit: 'contain', border: '1px solid #E2E8F0', padding: 4, borderRadius: 8 }} />
                                            <${MUI.Button} size="small" color="error" variant="outlined" onClick=${() => handleDeleteLogo('primary')}>Remove Logo</${MUI.Button}>
                                        </${MUI.Box}>
                                    ` : html`<${MUI.Alert} severity="info" sx=${{ mb: 1.5 }}>No logo uploaded — text-based company header fallback is active.</${MUI.Alert}>`}
                                    <input type="file" accept=".png,.jpg,.jpeg" onChange=${(e) => setLogoFile(e.target.files?.[0] || null)} />
                                </${MUI.Paper}>
                            </${MUI.Grid}>
                            <${MUI.Grid} size=${{ xs: 12, md: 6 }}>
                                <${MUI.Paper} variant="outlined" sx=${{ p: 2 }}>
                                    <${MUI.Typography} variant="subtitle2" sx=${{ mb: 1 }}>Monochrome Logo (Optional)</${MUI.Typography}>
                                    ${profile.monochrome_logo_url ? html`
                                        <${MUI.Box} sx=${{ mb: 1.5, display: 'flex', alignItems: 'center', gap: 2 }}>
                                            <img src=${profile.monochrome_logo_url} alt="Monochrome Logo" style=${{ maxHeight: 72, maxWidth: 180, objectFit: 'contain', border: '1px solid #E2E8F0', padding: 4, borderRadius: 8 }} />
                                            <${MUI.Button} size="small" color="error" variant="outlined" onClick=${() => handleDeleteLogo('monochrome')}>Remove Monochrome</${MUI.Button}>
                                        </${MUI.Box}>
                                    ` : html`<${MUI.Typography} variant="caption" color="text.secondary" display="block" sx=${{ mb: 1.5 }}>Optional monochrome emblem for thermal or B&W prints.</${MUI.Typography}>`}
                                    <input type="file" accept=".png,.jpg,.jpeg" onChange=${(e) => setMonoFile(e.target.files?.[0] || null)} />
                                </${MUI.Paper}>
                            </${MUI.Grid}>
                        </${MUI.Grid}>

                        <${MUI.Stack} direction=${{ xs: 'column', sm: 'row' }} spacing=${2} sx=${{ mt: 3, alignItems: 'center' }}>
                            <${MUI.TextField} label="Branding Change Notes (Audit Trail)" fullWidth value=${changeNotes} onChange=${(e) => setChangeNotes(e.target.value)} />
                            <${MUI.Button} variant="contained" size="large" onClick=${handleSaveBranding} sx=${{ whiteSpace: 'nowrap' }}>
                                Save Profile & Publish Branding
                            </${MUI.Button}>
                        </${MUI.Stack}>
                    </${MUI.Card}>

                    <${MUI.Typography} variant="h6">Branding Version History (Immutable Document Snapshots)</${MUI.Typography}>
                    <${ResponsiveDataGrid}
                        rows=${versions}
                        columns=${[
                            { key: 'version_number', label: 'Version', render: (r) => html`<${MUI.Chip} size="small" label=${`v${r.version_number}`} />` },
                            { key: 'logo_sha256', label: 'Logo SHA-256', render: (r) => r.logo_sha256 ? html`<span className="nht-mono">${r.logo_sha256.slice(0, 14)}...</span>` : 'Text Fallback' },
                            { key: 'change_notes', label: 'Change Notes' },
                            { key: 'created_by_username', label: 'Updated By' },
                            { key: 'created_at', label: 'Published At', render: (r) => formatDateTime(r.created_at) },
                        ]}
                    />
                </${MUI.Stack}>
            `}

            ${tab === 1 && html`
                <${ResponsiveDataGrid}
                    loading=${loading}
                    rows=${filteredConfigs}
                    toolbarExtra=${html`
                        <${MUI.Stack} direction="row" spacing=${1} flexWrap="wrap">
                            <${MUI.TextField}
                                select
                                size="small"
                                label="Category"
                                value=${catFilter}
                                onChange=${(e) => setCatFilter(e.target.value)}
                                sx=${{ minWidth: 170 }}
                            >
                                <${MUI.MenuItem} value="">All Categories</${MUI.MenuItem}>
                                <${MUI.MenuItem} value="INTEGRATIONS">External Integrations</${MUI.MenuItem}>
                                <${MUI.MenuItem} value="BUSINESS">Business & Operations</${MUI.MenuItem}>
                                <${MUI.MenuItem} value="APPLICATION">Application Customisation</${MUI.MenuItem}>
                                <${MUI.MenuItem} value="SECURITY">Security Policies</${MUI.MenuItem}>
                                <${MUI.MenuItem} value="SYSTEM">System & Runtime</${MUI.MenuItem}>
                            </${MUI.TextField}>
                            <${MUI.Button} size="small" variant="outlined" startIcon=${html`<${MaterialIcon} name="download" />`} onClick=${handleExportConfigs}>
                                Export JSON
                            </${MUI.Button}>
                            <${MUI.Button} size="small" variant="outlined" component="label" startIcon=${html`<${MaterialIcon} name="upload" />`}>
                                Import JSON
                                <input type="file" hidden accept=".json" onChange=${handleImportConfigs} />
                            </${MUI.Button}>
                        </${MUI.Stack}>
                    `}
                    columns=${[
                        { key: 'key', label: 'Key', render: (r) => html`<span className="nht-mono">${r.key}</span>` },
                        { key: 'category_display', label: 'Category' },
                        { key: 'title', label: 'Setting' },
                        { key: 'display_value', label: 'Active Value', render: (r) => r.is_secret ? html`<${MUI.Chip} size="small" label=${String(r.display_value)} />` : String(r.display_value) },
                        { key: 'version', label: 'Ver', render: (r) => `v${r.version}` },
                        {
                            key: 'actions',
                            label: 'Modify',
                            align: 'right',
                            render: (r) => html`
                                <${MUI.Button} size="small" onClick=${() => openConfigEditor(r)}>
                                    Configure / Rollback
                                </${MUI.Button}>
                            `,
                        },
                    ]}
                />
            `}

            ${tab === 2 && html`
                <${ResponsiveDataGrid}
                    loading=${loading}
                    rows=${changeRequests}
                    columns=${[
                        { key: 'setting_key', label: 'Setting Key', render: (r) => html`<span className="nht-mono">${r.setting_key}</span>` },
                        { key: 'risk_level', label: 'Risk', render: (r) => html`<${StatusChip} value=${r.risk_level === 'HIGH' ? 'REJECTED' : 'PENDING'} label=${r.risk_level} />` },
                        { key: 'requested_by_username', label: 'Maker' },
                        { key: 'status', label: 'Status', render: (r) => html`<${StatusChip} value=${r.status} />` },
                        {
                            key: 'actions',
                            label: 'Checker Actions',
                            align: 'right',
                            render: (r) => r.status === 'PENDING' && html`
                                <${MUI.Stack} direction="row" spacing=${0.5} justifyContent="flex-end">
                                    <${MUI.Button} size="small" color="success" onClick=${() => handleCrAction(r.id, 'approve')}>Approve</${MUI.Button}>
                                    <${MUI.Button} size="small" color="error" onClick=${() => handleCrAction(r.id, 'reject')}>Reject</${MUI.Button}>
                                </${MUI.Stack}>
                            `,
                        },
                    ]}
                />
            `}

            ${tab === 3 && html`
                <${MUI.Box}>
                    <${MUI.Stack} direction="row" spacing=${1} flexWrap="wrap" useFlexGap sx=${{ mb: 2 }}>
                        <${MUI.Button} variant="contained" startIcon=${html`<${MaterialIcon} name="monitor_heart" />`} onClick=${runHealth}>
                            Run All Diagnostics Probes
                        </${MUI.Button}>
                        ${PROVIDERS.map(([code, label]) => html`
                            <${MUI.Button} key=${code} variant="outlined" size="small" onClick=${() => testSingleProvider(code)}>
                                Test ${label}
                            </${MUI.Button}>
                        `)}
                    </${MUI.Stack}>
                    ${health && html`
                        <${MUI.Grid} container spacing=${2}>
                            ${Object.entries(health.services || health).map(([svc, info]) => html`
                                <${MUI.Grid} size=${{ xs: 12, sm: 6, md: 4 }} key=${svc}>
                                    <${MUI.Card} sx=${{ p: 2 }}>
                                        <${MUI.Box} sx=${{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                            <${MUI.Typography} variant="subtitle2" sx=${{ textTransform: 'uppercase' }}>${svc}</${MUI.Typography}>
                                            <${StatusChip} value=${info?.status || 'UNKNOWN'} />
                                        </${MUI.Box}>
                                        <${MUI.Typography} variant="caption" color="text.secondary">
                                            ${info?.error || info?.message || 'Probe completed'}
                                        </${MUI.Typography}>
                                    </${MUI.Card}>
                                </${MUI.Grid}>
                            `)}
                        </${MUI.Grid}>
                    `}
                </${MUI.Box}>
            `}

            <${ResponsiveDialog}
                open=${Boolean(editTarget)}
                onClose=${() => setEditTarget(null)}
                title=${`Configure ${editTarget?.key || ''}`}
                maxWidth="md"
                actions=${html`
                    <${MUI.Button} onClick=${assessImpact}>Assess Impact</${MUI.Button}>
                    <${MUI.Button} variant="outlined" onClick=${submitChangeRequest}>Submit Change Request</${MUI.Button}>
                    <${MUI.Button} variant="contained" onClick=${applyUpdate}>Apply Now</${MUI.Button}>
                `}
            >
                <${MUI.Stack} spacing=${2} sx=${{ pt: 1 }}>
                    <${MUI.Typography} variant="body2" color="text.secondary">${editTarget?.description}</${MUI.Typography}>
                    <${MUI.TextField} label="New Value" type=${editTarget?.is_secret ? 'password' : 'text'} fullWidth value=${newValue} onChange=${(e) => setNewValue(e.target.value)} />
                    <${MUI.TextField} label="Reason / Justification" fullWidth value=${reason} onChange=${(e) => setReason(e.target.value)} />
                    ${impact && html`
                        <${MUI.Alert} severity=${impact.risk_level === 'HIGH' || impact.risk_level === 'CRITICAL' ? 'warning' : 'info'}>
                            Risk: <strong>${impact.risk_level}</strong> — ${(impact.warnings || []).join(' ') || 'Low operational impact.'}
                        </${MUI.Alert}>
                    `}
                    ${configHistory.length > 0 && html`
                        <${MUI.Box}>
                            <${MUI.Typography} variant="subtitle2" sx=${{ mb: 1 }}>Version History & Rollback</${MUI.Typography}>
                            <${ResponsiveDataGrid}
                                rows=${configHistory}
                                columns=${[
                                    { key: 'version', label: 'Ver', render: (h) => `v${h.version}` },
                                    { key: 'new_value', label: 'Value', render: (h) => editTarget?.is_secret ? '••••••••' : h.new_value },
                                    { key: 'changed_by_username', label: 'Changed By' },
                                    { key: 'reason', label: 'Reason' },
                                    { key: 'timestamp', label: 'Time', render: (h) => formatDateTime(h.timestamp) },
                                    {
                                        key: 'rollback',
                                        label: 'Rollback',
                                        align: 'right',
                                        render: (h) => html`
                                            <${MUI.Button} size="small" color="warning" onClick=${() => handleRollbackConfig(h.version)}>
                                                Restore v${h.version}
                                            </${MUI.Button}>
                                        `,
                                    },
                                ]}
                            />
                        </${MUI.Box}>
                    `}
                </${MUI.Stack}>
            </${ResponsiveDialog}>
        </${MUI.Box}>
    `;
}

export function AuditTrailPage({ notify }) {
    const [logs, setLogs] = React.useState([]);
    const [loading, setLoading] = React.useState(true);
    const [search, setSearch] = React.useState('');

    const load = React.useCallback(async () => {
        setLoading(true);
        try {
            const res = await apiFetch(`/api/v1/audit-logs/?search=${encodeURIComponent(search)}`);
            setLogs(extractList(res));
        } catch (err) {
            notify(err.message, 'error');
        } finally {
            setLoading(false);
        }
    }, [search, notify]);

    React.useEffect(() => { load(); }, [load]);

    return html`
        <${MUI.Box}>
            <${PageHeader} title="Immutable Security Audit Trail" subtitle="Append-only record of logins, approvals, financial postings, and blocked IDOR attempts." />
            <${ResponsiveDataGrid}
                loading=${loading}
                rows=${logs}
                search=${search}
                onSearchChange=${setSearch}
                searchPlaceholder="Search actor, entity..."
                columns=${[
                    { key: 'timestamp', label: 'Timestamp', render: (r) => formatDateTime(r.timestamp) },
                    { key: 'actor_username', label: 'Actor' },
                    { key: 'action', label: 'Action' },
                    { key: 'entity_type', label: 'Entity', render: (r) => `${r.entity_type} (${r.entity_id || '—'})` },
                    { key: 'ip_address', label: 'IP' },
                    { key: 'outcome', label: 'Outcome', render: (r) => html`<${StatusChip} value=${r.outcome} />` },
                ]}
            />
        </${MUI.Box}>
    `;
}

export function ReportsPage({ notify }) {
    const [summary, setSummary] = React.useState(null);

    React.useEffect(() => {
        apiFetch('/api/v1/reports/summary/')
            .then(setSummary)
            .catch((err) => notify(err.message, 'error'));
    }, [notify]);

    return html`
        <${MUI.Box}>
            <${PageHeader} title="Executive Reports & Official Exports" subtitle="Permission-controlled Branded PDF Compliance Audit and Financial Excel Workbooks." />
            ${summary && html`
                <${MUI.Grid} container spacing=${2.5}>
                    <${MUI.Grid} size=${{ xs: 12, sm: 6 }}>
                        <${MUI.Card} sx=${{ p: 3 }}>
                            <${MUI.Typography} variant="h6" sx=${{ mb: 1 }}>Fleet Compliance PDF Report</${MUI.Typography}>
                            <${MUI.Typography} variant="body2" color="text.secondary" sx=${{ mb: 2 }}>
                                Branded A4 PDF detailing every active vehicle, route assignment, and regulatory status (${summary.compliance_rate}% compliant).
                            </${MUI.Typography}>
                            <${MUI.Button} variant="contained" href=${summary.compliance_pdf_url} target="_blank" startIcon=${html`<${MaterialIcon} name="picture_as_pdf" />`}>
                                Download Compliance PDF
                            </${MUI.Button}>
                        </${MUI.Card}>
                    </${MUI.Grid}>
                    <${MUI.Grid} size=${{ xs: 12, sm: 6 }}>
                        <${MUI.Card} sx=${{ p: 3 }}>
                            <${MUI.Typography} variant="h6" sx=${{ mb: 1 }}>SACCO Financial Summary Excel</${MUI.Typography}>
                            <${MUI.Typography} variant="body2" color="text.secondary" sx=${{ mb: 2 }}>
                                Multi-sheet workbook with embedded company logo covering Invoices, Statutory Fees, and Confirmed Payments.
                            </${MUI.Typography}>
                            ${summary.can_export_finance ? html`
                                <${MUI.Button} variant="contained" color="success" href=${summary.financial_excel_url} target="_blank" startIcon=${html`<${MaterialIcon} name="table_view" />`}>
                                    Download Financial Excel
                                </${MUI.Button}>
                            ` : html`
                                <${MUI.Alert} severity="info">Restricted to Finance, Chairman, Auditor, and Super Admin roles.</${MUI.Alert}>
                            `}
                        </${MUI.Card}>
                    </${MUI.Grid}>
                </${MUI.Grid}>
            `}
        </${MUI.Box}>
    `;
}
