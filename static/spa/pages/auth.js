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
                        <${MUI.Typography} variant="h5" color="primary.main">NHT-SMS</${MUI.Typography}>
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
                        <${MUI.Button} size="small" href="/accounts/login/">
                            Switch to Classic Django Login
                        </${MUI.Button}>
                        <${MUI.Typography} variant="caption" color="text.secondary" display="block" sx=${{ mt: 1 }}>
                            Protected by Axes brute-force defense, TOTP MFA & immutable audit logging.
                        </${MUI.Typography}>
                    </${MUI.Box}>
                </${MUI.CardContent}>
            </${MUI.Card}>
        </${MUI.Box}>
    `;
}

export function UsersAdminPage({ notify }) {
    const [users, setUsers] = React.useState([]);
    const [roles, setRoles] = React.useState([]);
    const [history, setHistory] = React.useState([]);
    const [loading, setLoading] = React.useState(true);
    const [search, setSearch] = React.useState('');
    const [tab, setTab] = React.useState(0);
    const [createOpen, setCreateOpen] = React.useState(false);
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
            const [uRes, rRes, hRes] = await Promise.all([
                apiFetch(`/api/v1/users/?search=${encodeURIComponent(search)}`),
                apiFetch('/api/v1/users/roles/'),
                apiFetch('/api/v1/users/login_history/'),
            ]);
            setUsers(extractList(uRes));
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
            await apiFetch('/api/v1/users/', { method: 'POST', body: form });
            notify('User provisioned successfully.', 'success');
            setCreateOpen(false);
            setForm({ username: '', email: '', first_name: '', last_name: '', phone_number: '', national_id: '', role: 'SECRETARY', password: '' });
            loadData();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const handleAssignRole = async (userId, newRole) => {
        try {
            await apiFetch(`/api/v1/users/${userId}/assign_role/`, { method: 'POST', body: { role: newRole } });
            notify(`Role updated to ${newRole}`, 'success');
            loadData();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const handleToggleActive = async (userId) => {
        try {
            await apiFetch(`/api/v1/users/${userId}/toggle_active/`, { method: 'POST' });
            notify('User status updated.', 'success');
            loadData();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    return html`
        <${MUI.Box}>
            <${PageHeader}
                title="Users & Role Allocation"
                subtitle="Manage all 11 SACCO personas, role clearances, account status, and login telemetry."
                action=${html`
                    <${MUI.Button} variant="contained" startIcon=${html`<${MaterialIcon} name="person_add" />`} onClick=${() => setCreateOpen(true)}>
                        Provision User
                    </${MUI.Button}>
                `}
            />

            <${MUI.Tabs} value=${tab} onChange=${(_, v) => setTab(v)} sx=${{ mb: 2 }}>
                <${MUI.Tab} label="System Accounts (${users.length})" />
                <${MUI.Tab} label="Recent Login History" />
            </${MUI.Tabs}>

            ${tab === 0 ? html`
                <${ResponsiveDataGrid}
                    loading=${loading}
                    rows=${users}
                    search=${search}
                    onSearchChange=${setSearch}
                    searchPlaceholder="Search username, email, phone..."
                    columns=${[
                        { key: 'username', label: 'Username', render: (r) => html`<strong>${r.username}</strong>` },
                        { key: 'full_name', label: 'Name' },
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
                            label: 'Actions',
                            align: 'right',
                            render: (r) => html`
                                <${MUI.Button}
                                    size="small"
                                    color=${r.is_active ? 'warning' : 'success'}
                                    onClick=${() => handleToggleActive(r.id)}
                                >
                                    ${r.is_active ? 'Suspend' : 'Activate'}
                                </${MUI.Button}>
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
                title="Provision New System Account"
                actions=${html`
                    <${MUI.Button} onClick=${() => setCreateOpen(false)}>Cancel</${MUI.Button}>
                    <${MUI.Button} variant="contained" onClick=${handleCreate}>Create User</${MUI.Button}>
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
                        label="Role"
                        fullWidth
                        value=${form.role}
                        onChange=${(e) => setForm({ ...form, role: e.target.value })}
                    >
                        ${roles.map((rl) => html`<${MUI.MenuItem} key=${rl.value} value=${rl.value}>${rl.label}</${MUI.MenuItem}>`)}
                    </${MUI.TextField}>
                    <${MUI.TextField} label="Initial Password (min 10 chars)" type="password" fullWidth value=${form.password} onChange=${(e) => setForm({ ...form, password: e.target.value })} />
                </${MUI.Stack}>
            </${ResponsiveDialog}>
        </${MUI.Box}>
    `;
}
