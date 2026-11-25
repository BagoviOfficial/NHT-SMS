import { React, MUI, html, apiFetch, extractList, formatDateTime } from '../api.js';
import { MaterialIcon, PageHeader, ResponsiveDataGrid, ResponsiveDialog, StatusChip } from '../components.js';

export function LoginPage({ branding, onLoginSuccess }) {
    const [username, setUsername] = React.useState('');
    const [password, setPassword] = React.useState('');
    const [loading, setLoading] = React.useState(false);
    const [error, setError] = React.useState('');

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setLoading(true);
        try {
            const data = await apiFetch('/api/v1/auth/login/', {
                method: 'POST',
                body: { username, password },
            });
            onLoginSuccess(data);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    return html`
        <${MUI.Box}
            sx=${{
                minHeight: '100vh',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: 'linear-gradient(135deg, #091E38 0%, #10315C 60%, #1B4A8A 100%)',
                p: 2,
            }}
        >
            <${MUI.Card} sx=${{ maxWidth: 440, width: '100%', p: { xs: 2, sm: 3.5 }, borderRadius: 4 }}>
                <${MUI.CardContent}>
                    <${MUI.Box} sx=${{ textAlign: 'center', mb: 3 }}>
                        ${branding?.logo_url ? html`
                            <img
                                src=${`${branding.logo_url}?v=${branding.branding_version || 1}`}
                                alt=${branding?.sacco_name || 'NHT-SMS'}
                                style=${{ maxHeight: 68, maxWidth: 180, margin: '0 auto 12px', display: 'block', objectFit: 'contain' }}
                            />
                        ` : html`
                            <${MUI.Avatar}
                                sx=${{
                                    width: 64,
                                    height: 64,
                                    mx: 'auto',
                                    mb: 1.5,
                                    bgcolor: '#FFF3E0',
                                    color: '#FF8A00',
                                    border: '2px solid #FF8A00',
                                }}
                            >
                                <${MaterialIcon} name="shield" fontSize="large" />
                            </${MUI.Avatar}>
                        `}
                        <${MUI.Typography} variant="h5" color="primary.main">${branding?.short_name || 'NHT-SMS'}</${MUI.Typography}>
                        <${MUI.Typography} variant="body2" color="text.secondary">
                            ${branding?.sacco_name || 'Northern Highways Transporters SACCO'}
                        </${MUI.Typography}>
                    </${MUI.Box}>

                    ${error && html`<${MUI.Alert} severity="error" sx=${{ mb: 2 }}>${error}</${MUI.Alert}>`}

                    <form onSubmit=${handleSubmit}>
                        <${MUI.Stack} spacing=${2.2}>
                            <${MUI.TextField}
                                label="Username or Email"
                                fullWidth
                                required
                                value=${username}
                                onChange=${(e) => setUsername(e.target.value)}
                                InputProps=${{
                                    startAdornment: html`
                                        <${MUI.InputAdornment} position="start">
                                            <${MaterialIcon} name="person" />
                                        </${MUI.InputAdornment}>
                                    `,
                                }}
                            />
                            <${MUI.TextField}
                                label="Password"
                                type="password"
                                fullWidth
                                required
                                value=${password}
                                onChange=${(e) => setPassword(e.target.value)}
                                InputProps=${{
                                    startAdornment: html`
                                        <${MUI.InputAdornment} position="start">
                                            <${MaterialIcon} name="key" />
                                        </${MUI.InputAdornment}>
                                    `,
                                }}
                            />
                            <${MUI.Button}
                                type="submit"
                                variant="contained"
                                size="large"
                                fullWidth
                                disabled=${loading}
                                startIcon=${html`<${MaterialIcon} name="login" />`}
                            >
                                ${loading ? 'Signing In...' : 'Sign In to Workspace'}
                            </${MUI.Button}>
                        </${MUI.Stack}>
                    </form>

                    <${MUI.Divider} sx=${{ my: 2.5 }} />
                    <${MUI.Box} sx=${{ textAlign: 'center' }}>
                        <${MUI.Typography} variant="caption" color="text.secondary" display="block">
                            Protected by Axes brute-force defense, TOTP MFA &amp; immutable audit logging.
                        </${MUI.Typography}>
                    </${MUI.Box}>
                </${MUI.CardContent}>
            </${MUI.Card}>
        </${MUI.Box}>
    `;
}

export function StaffManagementPage({ notify }) {
    const [staff, setStaff] = React.useState([]);
    const [roles, setRoles] = React.useState([]);
    const [history, setHistory] = React.useState([]);
    const [loading, setLoading] = React.useState(true);
    const [search, setSearch] = React.useState('');
    const [tab, setTab] = React.useState(0);
    const [createOpen, setCreateOpen] = React.useState(false);
    const [editTarget, setEditTarget] = React.useState(null);
    const [activityTarget, setActivityTarget] = React.useState(null);
    const [activityData, setActivityData] = React.useState(null);
    const [form, setForm] = React.useState({
        username: '',
        email: '',
        first_name: '',
        last_name: '',
        phone_number: '',
        national_id: '',
        role: 'SECRETARY',
        password: '',
    });

    const loadData = React.useCallback(async () => {
        setLoading(true);
        try {
            const [sRes, rRes, hRes] = await Promise.all([
                apiFetch(`/api/v1/staff/?search=${encodeURIComponent(search)}`),
                apiFetch('/api/v1/staff/roles/?scope=staff'),
                apiFetch('/api/v1/staff/login_history/'),
            ]);
            setStaff(extractList(sRes));
            setRoles(rRes || []);
            setHistory(hRes || []);
        } catch (err) {
            notify(err.message, 'error');
        } finally {
            setLoading(false);
        }
    }, [search, notify]);

    React.useEffect(() => { loadData(); }, [loadData]);

    const handleCreate = async () => {
        try {
            await apiFetch('/api/v1/staff/', { method: 'POST', body: form });
            notify('Staff account provisioned cleanly.', 'success');
            setCreateOpen(false);
            setForm({ username: '', email: '', first_name: '', last_name: '', phone_number: '', national_id: '', role: 'SECRETARY', password: '' });
            loadData();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const handleSaveEdit = async () => {
        try {
            await apiFetch(`/api/v1/staff/${editTarget.id}/`, {
                method: 'PATCH',
                body: {
                    email: editTarget.email,
                    first_name: editTarget.first_name,
                    last_name: editTarget.last_name,
                    phone_number: editTarget.phone_number,
                    national_id: editTarget.national_id,
                },
            });
            notify('Staff profile updated.', 'success');
            setEditTarget(null);
            loadData();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const handleAssignRole = async (userId, newRole) => {
        try {
            await apiFetch(`/api/v1/staff/${userId}/assign_role/`, { method: 'POST', body: { role: newRole } });
            notify(`Staff role updated to ${newRole}`, 'success');
            loadData();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const handleToggleActive = async (userId) => {
        try {
            await apiFetch(`/api/v1/staff/${userId}/toggle_active/`, { method: 'POST' });
            notify('Staff account status updated.', 'success');
            loadData();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const handleInitiateRecovery = async (userObj) => {
        try {
            const res = await apiFetch(`/api/v1/staff/${userObj.id}/initiate_recovery/`, {
                method: 'POST',
                body: { send_email: true },
            });
            notify(res.message || 'Password recovery initiated.', 'info');
            loadData();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const openActivity = async (userObj) => {
        setActivityTarget(userObj);
        setActivityData(null);
        try {
            const res = await apiFetch(`/api/v1/staff/${userObj.id}/activity/`);
            setActivityData(res);
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    return html`
        <${MUI.Box}>
            <${PageHeader}
                title="Staff Management & Role Authority"
                subtitle="Dedicated SACCO staff & administrator directory (strictly separated from SACCO Member & Driver accounts)."
                action=${html`
                    <${MUI.Button} variant="contained" startIcon=${html`<${MaterialIcon} name="person_add" />`} onClick=${() => setCreateOpen(true)}>
                        Register Staff User
                    </${MUI.Button}>
                `}
            />

            <${MUI.Tabs} value=${tab} onChange=${(_, v) => setTab(v)} sx=${{ mb: 2 }}>
                <${MUI.Tab} label="SACCO Staff Accounts (${staff.length})" />
                <${MUI.Tab} label="Security Login Telemetry" />
            </${MUI.Tabs}>

            ${tab === 0 ? html`
                <${ResponsiveDataGrid}
                    loading=${loading}
                    rows=${staff}
                    search=${search}
                    onSearchChange=${setSearch}
                    searchPlaceholder="Search staff username, name, email..."
                    columns=${[
                        { key: 'username', label: 'Username', render: (r) => html`<strong>${r.username}</strong>` },
                        { key: 'full_name', label: 'Staff Name' },
                        { key: 'email', label: 'Email' },
                        {
                            key: 'role',
                            label: 'Assigned Role',
                            render: (r) => html`
                                <${MUI.Select}
                                    size="small"
                                    value=${r.role}
                                    onChange=${(e) => handleAssignRole(r.id, e.target.value)}
                                >
                                    ${roles.map((rl) => html`
                                        <${MUI.MenuItem} key=${rl.value} value=${rl.value}>${rl.label}</${MUI.MenuItem}>
                                    `)}
                                </${MUI.Select}>
                            `,
                        },
                        { key: 'is_active', label: 'Status', render: (r) => html`<${StatusChip} value=${r.is_active ? 'ACTIVE' : 'SUSPENDED'} />` },
                        {
                            key: 'actions',
                            label: 'Controls',
                            align: 'right',
                            render: (r) => html`
                                <${MUI.Stack} direction="row" spacing=${0.5} justifyContent="flex-end" flexWrap="wrap">
                                    <${MUI.Button} size="small" onClick=${() => setEditTarget({ ...r })}>Edit</${MUI.Button}>
                                    <${MUI.Button} size="small" onClick=${() => openActivity(r)}>Activity</${MUI.Button}>
                                    <${MUI.Button} size="small" color="info" onClick=${() => handleInitiateRecovery(r)}>Recovery</${MUI.Button}>
                                    <${MUI.Button}
                                        size="small"
                                        color=${r.is_active ? 'warning' : 'success'}
                                        onClick=${() => handleToggleActive(r.id)}
                                    >
                                        ${r.is_active ? 'Deactivate' : 'Activate'}
                                    </${MUI.Button}>
                                </${MUI.Stack}>
                            `,
                        },
                    ]}
                />
            ` : html`
                <${ResponsiveDataGrid}
                    loading=${loading}
                    rows=${history}
                    columns=${[
                        { key: 'username_attempted', label: 'Username' },
                        { key: 'ip_address', label: 'IP Address' },
                        { key: 'status', label: 'Outcome', render: (r) => html`<${StatusChip} value=${r.status} />` },
                        { key: 'timestamp', label: 'Timestamp', render: (r) => formatDateTime(r.timestamp) },
                    ]}
                />
            `}

            <${ResponsiveDialog}
                open=${createOpen}
                onClose=${() => setCreateOpen(false)}
                title="Register New SACCO Staff Account"
                actions=${html`
                    <${MUI.Button} onClick=${() => setCreateOpen(false)}>Cancel</${MUI.Button}>
                    <${MUI.Button} variant="contained" onClick=${handleCreate}>Create Staff User</${MUI.Button}>
                `}
            >
                <${MUI.Stack} spacing=${2} sx=${{ pt: 1 }}>
                    <${MUI.TextField} label="Username" fullWidth value=${form.username} onChange=${(e) => setForm({ ...form, username: e.target.value })} />
                    <${MUI.TextField} label="Email" type="email" fullWidth value=${form.email} onChange=${(e) => setForm({ ...form, email: e.target.value })} />
                    <${MUI.Grid} container spacing=${2}>
                        <${MUI.Grid} item xs=${12} sm=${6}>
                            <${MUI.TextField} label="First Name" fullWidth value=${form.first_name} onChange=${(e) => setForm({ ...form, first_name: e.target.value })} />
                        </${MUI.Grid}>
                        <${MUI.Grid} item xs=${12} sm=${6}>
                            <${MUI.TextField} label="Last Name" fullWidth value=${form.last_name} onChange=${(e) => setForm({ ...form, last_name: e.target.value })} />
                        </${MUI.Grid}>
                    </${MUI.Grid}>
                    <${MUI.TextField} label="Phone (+2547...)" fullWidth value=${form.phone_number} onChange=${(e) => setForm({ ...form, phone_number: e.target.value })} />
                    <${MUI.TextField} label="National ID" fullWidth value=${form.national_id} onChange=${(e) => setForm({ ...form, national_id: e.target.value })} />
                    <${MUI.TextField}
                        select
                        label="Staff Role"
                        fullWidth
                        value=${form.role}
                        onChange=${(e) => setForm({ ...form, role: e.target.value })}
                    >
                        ${roles.map((rl) => html`<${MUI.MenuItem} key=${rl.value} value=${rl.value}>${rl.label}</${MUI.MenuItem}>`)}
                    </${MUI.TextField}>
                    <${MUI.TextField} label="Initial Password (min 10 chars)" type="password" fullWidth value=${form.password} onChange=${(e) => setForm({ ...form, password: e.target.value })} />
                </${MUI.Stack}>
            </${ResponsiveDialog}>

            <${ResponsiveDialog}
                open=${Boolean(editTarget)}
                onClose=${() => setEditTarget(null)}
                title=${`Edit Staff Profile: ${editTarget?.username || ''}`}
                actions=${html`
                    <${MUI.Button} onClick=${() => setEditTarget(null)}>Cancel</${MUI.Button}>
                    <${MUI.Button} variant="contained" onClick=${handleSaveEdit}>Save Changes</${MUI.Button}>
                `}
            >
                ${editTarget && html`
                    <${MUI.Stack} spacing=${2} sx=${{ pt: 1 }}>
                        <${MUI.TextField} label="Email" type="email" fullWidth value=${editTarget.email || ''} onChange=${(e) => setEditTarget({ ...editTarget, email: e.target.value })} />
                        <${MUI.TextField} label="First Name" fullWidth value=${editTarget.first_name || ''} onChange=${(e) => setEditTarget({ ...editTarget, first_name: e.target.value })} />
                        <${MUI.TextField} label="Last Name" fullWidth value=${editTarget.last_name || ''} onChange=${(e) => setEditTarget({ ...editTarget, last_name: e.target.value })} />
                        <${MUI.TextField} label="Phone Number" fullWidth value=${editTarget.phone_number || ''} onChange=${(e) => setEditTarget({ ...editTarget, phone_number: e.target.value })} />
                        <${MUI.TextField} label="National ID" fullWidth value=${editTarget.national_id || ''} onChange=${(e) => setEditTarget({ ...editTarget, national_id: e.target.value })} />
                    </${MUI.Stack}>
                `}
            </${ResponsiveDialog}>

            <${ResponsiveDialog}
                open=${Boolean(activityTarget)}
                onClose=${() => setActivityTarget(null)}
                title=${`Account Activity & Audit History: ${activityTarget?.username || ''}`}
                maxWidth="md"
                actions=${html`<${MUI.Button} onClick=${() => setActivityTarget(null)}>Close</${MUI.Button}>`}
            >
                ${!activityData ? html`<${MUI.Box} sx=${{ p: 3, textAlign: 'center' }}><${MUI.CircularProgress} /></${MUI.Box}>` : html`
                    <${MUI.Stack} spacing=${2}>
                        <${MUI.Typography} variant="subtitle2">Recent Login Attempts</${MUI.Typography}>
                        <${ResponsiveDataGrid}
                            rows=${activityData.login_history || []}
                            columns=${[
                                { key: 'timestamp', label: 'Time', render: (r) => formatDateTime(r.timestamp) },
                                { key: 'ip_address', label: 'IP' },
                                { key: 'status', label: 'Status', render: (r) => html`<${StatusChip} value=${r.status} />` },
                            ]}
                        />
                        <${MUI.Typography} variant="subtitle2">Audit Trail Events</${MUI.Typography}>
                        <${ResponsiveDataGrid}
                            rows=${activityData.audit_logs || []}
                            columns=${[
                                { key: 'timestamp', label: 'Time', render: (r) => formatDateTime(r.timestamp) },
                                { key: 'action', label: 'Action' },
                                { key: 'entity_type', label: 'Entity' },
                                { key: 'outcome', label: 'Outcome', render: (r) => html`<${StatusChip} value=${r.outcome} />` },
                            ]}
                        />
                    </${MUI.Stack}>
                `}
            </${ResponsiveDialog}>
        </${MUI.Box}>
    `;
}

export const UsersAdminPage = StaffManagementPage;
