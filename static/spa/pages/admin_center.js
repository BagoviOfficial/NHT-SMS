import { React, MUI, html, apiFetch, extractList, formatDateTime } from '../api.js';
import { MaterialIcon, PageHeader, ResponsiveDataGrid, ResponsiveDialog, StatusChip } from '../components.js';

export function SettingsCenterPage({ notify, onRefreshMe }) {
    const [tab, setTab] = React.useState(0);
    const [profile, setProfile] = React.useState(null);
    const [versions, setVersions] = React.useState([]);
    const [logoFile, setLogoFile] = React.useState(null);
    const [monoFile, setMonoFile] = React.useState(null);
    const [changeNotes, setChangeNotes] = React.useState('');
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
            fd.append('change_notes', changeNotes || 'Updated company profile & branding via SPA');
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
                title="System Configuration, Company Profile & Branding"
                subtitle="Centralized SACCO identity, logo management, encrypted settings registry, Maker-Checker approvals, and diagnostics."
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
                            <${MUI.Typography} variant="h6">Company Profile &amp; Official Document Metadata</${MUI.Typography}>
                            <${MUI.Chip} color="primary" label=${`Active Branding v${profile.current_version}`} />
                        </${MUI.Box}>
                        <${MUI.Grid} container spacing=${2}>
                            <${MUI.Grid} item xs=${12} sm=${6}><${MUI.TextField} label="Legal Name" fullWidth value=${profile.legal_name || ''} onChange=${(e) => setProfile({ ...profile, legal_name: e.target.value })} /></${MUI.Grid}>
                            <${MUI.Grid} item xs=${12} sm=${4}><${MUI.TextField} label="Trading Name" fullWidth value=${profile.trading_name || ''} onChange=${(e) => setProfile({ ...profile, trading_name: e.target.value })} /></${MUI.Grid}>
                            <${MUI.Grid} item xs=${12} sm=${2}><${MUI.TextField} label="Acronym" fullWidth value=${profile.short_name || ''} onChange=${(e) => setProfile({ ...profile, short_name: e.target.value })} /></${MUI.Grid}>
                            <${MUI.Grid} item xs=${12} sm=${6}><${MUI.TextField} label="SACCO Registration No" fullWidth value=${profile.registration_number || ''} onChange=${(e) => setProfile({ ...profile, registration_number: e.target.value })} /></${MUI.Grid}>
                            <${MUI.Grid} item xs=${12} sm=${6}><${MUI.TextField} label="KRA PIN / Tax ID" fullWidth value=${profile.tax_pin || ''} onChange=${(e) => setProfile({ ...profile, tax_pin: e.target.value })} /></${MUI.Grid}>
                            <${MUI.Grid} item xs=${12} sm=${6}><${MUI.TextField} label="Physical Address" fullWidth value=${profile.physical_address || ''} onChange=${(e) => setProfile({ ...profile, physical_address: e.target.value })} /></${MUI.Grid}>
                            <${MUI.Grid} item xs=${12} sm=${6}><${MUI.TextField} label="Postal Address" fullWidth value=${profile.postal_address || ''} onChange=${(e) => setProfile({ ...profile, postal_address: e.target.value })} /></${MUI.Grid}>
                            <${MUI.Grid} item xs=${12} sm=${4}><${MUI.TextField} label="Telephone Numbers" fullWidth value=${profile.phone_numbers || ''} onChange=${(e) => setProfile({ ...profile, phone_numbers: e.target.value })} /></${MUI.Grid}>
                            <${MUI.Grid} item xs=${12} sm=${4}><${MUI.TextField} label="Official Email" fullWidth value=${profile.official_email || ''} onChange=${(e) => setProfile({ ...profile, official_email: e.target.value })} /></${MUI.Grid}>
                            <${MUI.Grid} item xs=${12} sm=${4}><${MUI.TextField} label="Website" fullWidth value=${profile.website || ''} onChange=${(e) => setProfile({ ...profile, website: e.target.value })} /></${MUI.Grid}>
                            <${MUI.Grid} item xs=${12} sm=${6}><${MUI.TextField} label="Public QR Verification Base URL (HTTPS)" fullWidth value=${profile.public_base_url || ''} onChange=${(e) => setProfile({ ...profile, public_base_url: e.target.value })} /></${MUI.Grid}>
                            <${MUI.Grid} item xs=${6} sm=${3}><${MUI.TextField} label="Primary Brand Color" fullWidth value=${profile.primary_color || '#10315C'} onChange=${(e) => setProfile({ ...profile, primary_color: e.target.value })} /></${MUI.Grid}>
                            <${MUI.Grid} item xs=${6} sm=${3}><${MUI.TextField} label="Secondary Accent Color" fullWidth value=${profile.secondary_color || '#FF8A00'} onChange=${(e) => setProfile({ ...profile, secondary_color: e.target.value })} /></${MUI.Grid}>
                            <${MUI.Grid} item xs=${12}><${MUI.TextField} label="Document Footer Text" fullWidth value=${profile.footer_text || ''} onChange=${(e) => setProfile({ ...profile, footer_text: e.target.value })} /></${MUI.Grid}>
                        </${MUI.Grid}>

                        <${MUI.Divider} sx=${{ my: 3 }} />
                        <${MUI.Typography} variant="subtitle1" sx=${{ fontWeight: 700, mb: 2 }}>Official Company Logo Assets (PNG/JPEG, max 2 MB)</${MUI.Typography}>
                        <${MUI.Grid} container spacing=${3}>
                            <${MUI.Grid} item xs=${12} md=${6}>
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
                            <${MUI.Grid} item xs=${12} md=${6}>
                                <${MUI.Paper} variant="outlined" sx=${{ p: 2 }}>
                                    <${MUI.Typography} variant="subtitle2" sx=${{ mb: 1 }}>Monochrome Logo (Optional)</${MUI.Typography}>
                                    ${profile.monochrome_logo_url ? html`
                                        <${MUI.Box} sx=${{ mb: 1.5, display: 'flex', alignItems: 'center', gap: 2 }}>
                                            <img src=${profile.monochrome_logo_url} alt="Monochrome Logo" style=${{ maxHeight: 72, maxWidth: 180, objectFit: 'contain', border: '1px solid #E2E8F0', padding: 4, borderRadius: 8 }} />
                                            <${MUI.Button} size="small" color="error" variant="outlined" onClick=${() => handleDeleteLogo('monochrome')}>Remove Monochrome</${MUI.Button}>
                                        </${MUI.Box}>
                                    ` : html`<${MUI.Typography} variant="caption" color="text.secondary" display="block" sx=${{ mb: 1.5 }}>Optional monochrome emblem for thermal or B&amp;W prints.</${MUI.Typography}>`}
                                    <input type="file" accept=".png,.jpg,.jpeg" onChange=${(e) => setMonoFile(e.target.files?.[0] || null)} />
                                </${MUI.Paper}>
                            </${MUI.Grid}>
                        </${MUI.Grid}>

                        <${MUI.Stack} direction=${{ xs: 'column', sm: 'row' }} spacing=${2} sx=${{ mt: 3, alignItems: 'center' }}>
                            <${MUI.TextField} label="Branding Change Notes (Audit Trail)" fullWidth value=${changeNotes} onChange=${(e) => setChangeNotes(e.target.value)} />
                            <${MUI.Button} variant="contained" size="large" onClick=${handleSaveBranding} sx=${{ whiteSpace: 'nowrap' }}>
                                Save Profile &amp; Publish Branding
                            </${MUI.Button}>
                        </${MUI.Stack}>
                    </${MUI.Card}>

                    <${MUI.Typography} variant="h6">Branding Version History (Immutable Document Snapshots)</${MUI.Typography}>
                    <${ResponsiveDataGrid}
                        rows=${versions}
                        columns=${[
                            { key: 'version_number', label: 'Version', render: (r) => html`<${MUI.Chip} size="small" label=${`v${r.version_number}`} />` },
                            { key: 'logo_sha256', label: 'Logo SHA-256', render: (r) => r.logo_sha256 ? html`<span class="nht-mono">${r.logo_sha256.slice(0, 14)}...</span>` : 'Text Fallback' },
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

            ${tab === 2 && html`
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

            ${tab === 3 && html`
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
            <${PageHeader} title="Executive Reports & Official Exports" subtitle="Permission-controlled Branded PDF Compliance Audit and Financial Excel Workbooks." />
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
