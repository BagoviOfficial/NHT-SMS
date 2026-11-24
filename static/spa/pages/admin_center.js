import { React, MUI, html, apiFetch, extractList, formatDateTime } from '../api.js';
import { MaterialIcon, PageHeader, ResponsiveDataGrid, ResponsiveDialog, StatusChip } from '../components.js';

export function SettingsCenterPage({ notify }) {
    const [tab, setTab] = React.useState(0);
    const [configs, setConfigs] = React.useState([]);
    const [changeRequests, setChangeRequests] = React.useState([]);
    const [health, setHealth] = React.useState(null);
    const [loading, setLoading] = React.useState(true);
    const [editTarget, setEditTarget] = React.useState(null);
    const [newValue, setNewValue] = React.useState('');
    const [reason, setReason] = React.useState('');
    const [impact, setImpact] = React.useState(null);

    const load = React.useCallback(async () => {
        setLoading(true);
        try {
            const [cRes, crRes] = await Promise.all([
                apiFetch('/settings/api/v1/configs/'),
                apiFetch('/settings/api/v1/change-requests/'),
            ]);
            setConfigs(extractList(cRes));
            setChangeRequests(extractList(crRes));
        } catch (err) {
            notify(err.message, 'error');
        } finally {
            setLoading(false);
        }
    }, [notify]);

    React.useEffect(() => { load(); }, [load]);

    const runHealth = async () => {
        try {
            const res = await apiFetch('/settings/api/v1/health/');
            setHealth(res);
            notify('System diagnostics refreshed.', 'info');
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
                    reason: reason || 'Updated via SPA',
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

    return html`
        <${MUI.Box}>
            <${PageHeader}
                title="Dynamic System Configuration & Health"
                subtitle="Encrypted integration settings, dependency impact analysis, Maker-Checker change approvals, and live diagnostics."
                action=${html`
                    <${MUI.Button} variant="outlined" href="/settings/" target="_blank">Classic Settings Portal</${MUI.Button}>
                `}
            />

            <${MUI.Tabs} value=${tab} onChange=${(_, v) => setTab(v)} sx=${{ mb: 2 }}>
                <${MUI.Tab} label="Configuration Registry (${configs.length})" />
                <${MUI.Tab} label="Change Requests (${changeRequests.length})" />
                <${MUI.Tab} label="System Diagnostics" />
            </${MUI.Tabs}>

            ${tab === 0 && html`
                <${ResponsiveDataGrid}
                    loading=${loading}
                    rows=${configs}
                    columns=${[
                        { key: 'key', label: 'Key', render: (r) => html`<span class="nht-mono">${r.key}</span>` },
                        { key: 'category_display', label: 'Category' },
                        { key: 'title', label: 'Setting' },
                        { key: 'display_value', label: 'Active Value', render: (r) => String(r.display_value) },
                        { key: 'version', label: 'Ver', render: (r) => `v${r.version}` },
                        {
                            key: 'actions',
                            label: 'Modify',
                            align: 'right',
                            render: (r) => html`
                                <${MUI.Button} size="small" onClick=${() => { setEditTarget(r); setNewValue(r.is_secret ? '' : String(r.display_value ?? '')); setImpact(null); setReason(''); }}>
                                    Configure
                                </${MUI.Button}>
                            `,
                        },
                    ]}
                />
            `}

            ${tab === 1 && html`
                <${ResponsiveDataGrid}
                    loading=${loading}
                    rows=${changeRequests}
                    columns=${[
                        { key: 'setting_key', label: 'Setting Key', render: (r) => html`<span class="nht-mono">${r.setting_key}</span>` },
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

            ${tab === 2 && html`
                <${MUI.Box}>
                    <${MUI.Button} variant="contained" startIcon=${html`<${MaterialIcon} name="monitor_heart" />`} onClick=${runHealth} sx=${{ mb: 2 }}>
                        Run Live Diagnostics Probe
                    </${MUI.Button}>
                    ${health && html`
                        <${MUI.Grid} container spacing=${2}>
                            ${Object.entries(health.services || health).map(([svc, info]) => html`
                                <${MUI.Grid} item xs=${12} sm=${6} md=${4} key=${svc}>
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
            <${PageHeader} title="Executive Reports & Official Exports" subtitle="Permission-controlled PDF Compliance Audit and Financial Excel Workbooks." />
            ${summary && html`
                <${MUI.Grid} container spacing=${2.5}>
                    <${MUI.Grid} item xs=${12} sm=${6}>
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
                    <${MUI.Grid} item xs=${12} sm=${6}>
                        <${MUI.Card} sx=${{ p: 3 }}>
                            <${MUI.Typography} variant="h6" sx=${{ mb: 1 }}>SACCO Financial Summary Excel</${MUI.Typography}>
                            <${MUI.Typography} variant="body2" color="text.secondary" sx=${{ mb: 2 }}>
                                Multi-sheet workbook covering all Invoices, Statutory Fees, and Confirmed Payments/Receipts.
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
