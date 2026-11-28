import { React, MUI, html, apiFetch, extractList, formatDateTime } from '../api.js';
import { MaterialIcon, PageHeader, ResponsiveDataGrid, ResponsiveDialog, StatusChip } from '../components.js';

function AuthShellCard({ children, maxWidth = 460, p = 3, sx = {} }) {
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
            <${MUI.Card} sx=${{ maxWidth, width: '100%', p, borderRadius: 4, ...sx }}>
                <${MUI.CardContent}>${children}</${MUI.CardContent}>
            </${MUI.Card}>
        </${MUI.Box}>
    `;
}

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
        <${AuthShellCard} maxWidth=${440} p=${{ xs: 2, sm: 3.5 }}>
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
                        ${(window.__NHT_BOOTSTRAP__?.is_admin_portal || window.location.pathname.startsWith('/admin')) && html`
                            <${MUI.Chip} size="small" color="secondary" label="MUI Admin Dashboard" sx=${{ mt: 1, fontWeight: 700 }} />
                        `}
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
                                slotProps=${{
                                    input: {
                                        startAdornment: html`
                                            <${MUI.InputAdornment} position="start">
                                                <${MaterialIcon} name="person" />
                                            </${MUI.InputAdornment}>
                                        `,
                                    },
                                }}
                            />
                            <${MUI.TextField}
                                label="Password"
                                type="password"
                                fullWidth
                                required
                                value=${password}
                                onChange=${(e) => setPassword(e.target.value)}
                                slotProps=${{
                                    input: {
                                        startAdornment: html`
                                            <${MUI.InputAdornment} position="start">
                                                <${MaterialIcon} name="key" />
                                            </${MUI.InputAdornment}>
                                        `,
                                    },
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
                        <${MUI.Button} size="small" href="/accounts/password-reset/" sx=${{ mb: 1 }}>
                            Forgot Password?
                        </${MUI.Button}>
                        <${MUI.Typography} variant="caption" color="text.secondary" display="block">
                            Protected by Axes brute-force defense, TOTP MFA & immutable audit logging.
                        </${MUI.Typography}>
                    </${MUI.Box}>
        </${AuthShellCard}>
    `;
}

export function ProfilePage({ me, onNavigate }) {
    const p = window.__NHT_BOOTSTRAP__?.page_data?.profile || {};
    const user = me?.user || {};
    const rows = [
        ['Username', p.username || user.username || '—'],
        ['Full Name', p.full_name || user.full_name || 'Not specified'],
        ['Email Address', p.email || user.email || '—'],
        ['Phone Number', p.phone_number || user.phone_number || 'Not registered'],
        ['National ID / Passport', p.national_id || 'Not registered'],
        ['Assigned Role', p.role_display || user.role_display || '—'],
        ['Last Login IP', p.last_login_ip || 'None recorded'],
        ['Member Since', p.date_joined ? formatDateTime(p.date_joined) : '—'],
    ];

    return html`
        <${MUI.Box} sx=${{ maxWidth: 880, mx: 'auto' }}>
            <${PageHeader}
                title="User Profile & Security Overview"
                subtitle="Review your account credentials, security status, and recent login activity."
                action=${html`
                    <${MUI.Button} variant="contained" color="secondary" startIcon=${html`<${MaterialIcon} name="key" />`} onClick=${() => onNavigate('password-change')}>
                        Change Password
                    </${MUI.Button}>
                `}
            />
            <${MUI.Card} sx=${{ mb: 3 }}>
                <${MUI.CardContent}>
                    <${MUI.TableContainer}>
                        <${MUI.Table} size="small">
                            <${MUI.TableBody}>
                                ${rows.map(([label, val]) => html`
                                    <${MUI.TableRow} key=${label}>
                                        <${MUI.TableCell} sx=${{ width: '35%', color: 'text.secondary', fontWeight: 600 }}>${label}</${MUI.TableCell}>
                                        <${MUI.TableCell}><strong>${val}</strong></${MUI.TableCell}>
                                    </${MUI.TableRow}>
                                `)}
                                <${MUI.TableRow}>
                                    <${MUI.TableCell} sx=${{ color: 'text.secondary', fontWeight: 600 }}>Account Status</${MUI.TableCell}>
                                    <${MUI.TableCell}><${StatusChip} value=${p.is_active === false ? 'SUSPENDED' : 'ACTIVE'} /></${MUI.TableCell}>
                                </${MUI.TableRow}>
                            </${MUI.TableBody}>
                        </${MUI.Table}>
                    </${MUI.TableContainer}>
                </${MUI.CardContent}>
            </${MUI.Card}>

            ${(p.recent_logins || []).length > 0 && html`
                <${MUI.Box}>
                    <${MUI.Typography} variant="h6" sx=${{ mb: 1.5 }}>Recent Security Logins</${MUI.Typography}>
                    <${ResponsiveDataGrid}
                        rows=${p.recent_logins.map((r, i) => ({ ...r, id: i }))}
                        columns=${[
                            { key: 'timestamp', label: 'Timestamp', render: (r) => formatDateTime(r.timestamp) },
                            { key: 'status', label: 'Status', render: (r) => html`<${StatusChip} value=${r.status} />` },
                            { key: 'ip_address', label: 'IP Address', render: (r) => html`<span className="nht-mono">${r.ip_address}</span>` },
                            { key: 'user_agent', label: 'Device' },
                        ]}
                    />
                </${MUI.Box}>
            `}
        </${MUI.Box}>
    `;
}

export function PasswordChangePage({ notify, onRefreshMe, onNavigate }) {
    const [oldPassword, setOldPassword] = React.useState('');
    const [newPassword, setNewPassword] = React.useState('');
    const [confirmPassword, setConfirmPassword] = React.useState('');
    const [saving, setSaving] = React.useState(false);
    const [error, setError] = React.useState('');

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        if (newPassword !== confirmPassword) {
            setError('New passwords do not match.');
            return;
        }
        setSaving(true);
        try {
            const res = await apiFetch('/api/v1/auth/password-change/', {
                method: 'POST',
                body: { old_password: oldPassword, new_password: newPassword },
            });
            notify(res.message || 'Password updated successfully.', 'success');
            setOldPassword('');
            setNewPassword('');
            setConfirmPassword('');
            if (onRefreshMe) await onRefreshMe();
            if (onNavigate) onNavigate('profile');
        } catch (err) {
            setError(err.message);
        } finally {
            setSaving(false);
        }
    };

    return html`
        <${MUI.Box} sx=${{ maxWidth: 560, mx: 'auto' }}>
            <${MUI.Card}>
                <${MUI.CardContent} sx=${{ p: 3 }}>
                    <${MUI.Stack} direction="row" spacing=${1.5} alignItems="center" sx=${{ mb: 2 }}>
                        <${MaterialIcon} name="key" color="secondary" />
                        <${MUI.Typography} variant="h6">Change Account Password</${MUI.Typography}>
                    </${MUI.Stack}>
                    <${MUI.Typography} variant="body2" color="text.secondary" sx=${{ mb: 2.5 }}>
                        Ensure your new password contains at least 10 characters, including letters, numbers, and symbols. Updating your password terminates other active sessions.
                    </${MUI.Typography}>
                    ${error && html`<${MUI.Alert} severity="error" sx=${{ mb: 2 }}>${error}</${MUI.Alert}>`}
                    <form onSubmit=${handleSubmit}>
                        <${MUI.Stack} spacing=${2}>
                            <${MUI.TextField} label="Current Password" type="password" fullWidth required value=${oldPassword} onChange=${(e) => setOldPassword(e.target.value)} />
                            <${MUI.TextField} label="New Password (min 10 chars)" type="password" fullWidth required value=${newPassword} onChange=${(e) => setNewPassword(e.target.value)} />
                            <${MUI.TextField} label="Confirm New Password" type="password" fullWidth required value=${confirmPassword} onChange=${(e) => setConfirmPassword(e.target.value)} />
                            <${MUI.Stack} direction="row" justifyContent="flex-end" spacing=${1}>
                                <${MUI.Button} variant="outlined" onClick=${() => onNavigate && onNavigate('profile')}>Cancel</${MUI.Button}>
                                <${MUI.Button} type="submit" variant="contained" color="secondary" disabled=${saving}>
                                    ${saving ? 'Updating...' : 'Update Password'}
                                </${MUI.Button}>
                            </${MUI.Stack}>
                        </${MUI.Stack}>
                    </form>
                </${MUI.CardContent}>
            </${MUI.Card}>
        </${MUI.Box}>
    `;
}

export function LockoutPage() {
    return html`
        <${AuthShellCard} sx=${{ textAlign: 'center' }}>
                    <${MUI.Avatar} sx=${{ width: 68, height: 68, mx: 'auto', mb: 2, bgcolor: '#FEE2E2', color: '#B91C1C' }}>
                        <${MaterialIcon} name="gpp_bad" fontSize="large" />
                    </${MUI.Avatar}>
                    <${MUI.Typography} variant="h5" color="error.main" sx=${{ mb: 1 }}>Access Temporarily Suspended</${MUI.Typography}>
                    <${MUI.Typography} variant="body2" color="text.secondary" sx=${{ mb: 2.5 }}>
                        Too many failed login attempts were detected from your network address. Access has been temporarily locked under OWASP ASVS security policy.
                    </${MUI.Typography}>
                    <${MUI.Alert} severity="warning" sx=${{ mb: 2.5, textAlign: 'left' }}>
                        Wait for the cool-off period to elapse or contact your SACCO Super Administrator for account recovery.
                    </${MUI.Alert}>
                    <${MUI.Button} variant="contained" fullWidth href="/accounts/login/" startIcon=${html`<${MaterialIcon} name="arrow_back" />`}>
                        Return to Login
                    </${MUI.Button}>
        </${AuthShellCard}>
    `;
}

export function PasswordResetPage({ route }) {
    const [email, setEmail] = React.useState('');
    const [pw1, setPw1] = React.useState('');
    const [pw2, setPw2] = React.useState('');
    const pageData = window.__NHT_BOOTSTRAP__?.page_data || {};
    const csrf = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

    return html`
        <${AuthShellCard}>
                    <${MUI.Typography} variant="h5" color="primary.main" sx=${{ mb: 1 }}>Password Recovery</${MUI.Typography}>
                    ${route === 'password-reset' && html`
                        <form method="post" action="">
                            <input type="hidden" name="csrfmiddlewaretoken" value=${csrf} />
                            <${MUI.Typography} variant="body2" color="text.secondary" sx=${{ mb: 2 }}>
                                Enter your registered email address to receive password reset instructions.
                            </${MUI.Typography}>
                            <${MUI.TextField} name="email" type="email" label="Registered Email" fullWidth required value=${email} onChange=${(e) => setEmail(e.target.value)} sx=${{ mb: 2 }} />
                            <${MUI.Button} type="submit" variant="contained" fullWidth>Send Reset Link</${MUI.Button}>
                        </form>
                    `}
                    ${route === 'password-reset-done' && html`
                        <${MUI.Alert} severity="info" sx=${{ mb: 2 }}>
                            If an account matches that email, password reset instructions have been sent.
                        </${MUI.Alert}>
                    `}
                    ${route === 'password-reset-confirm' && (pageData.validlink ? html`
                        <form method="post" action="">
                            <input type="hidden" name="csrfmiddlewaretoken" value=${csrf} />
                            <${MUI.Stack} spacing=${2}>
                                <${MUI.TextField} name="new_password1" type="password" label="New Password" fullWidth required value=${pw1} onChange=${(e) => setPw1(e.target.value)} />
                                <${MUI.TextField} name="new_password2" type="password" label="Confirm Password" fullWidth required value=${pw2} onChange=${(e) => setPw2(e.target.value)} />
                                <${MUI.Button} type="submit" variant="contained" fullWidth>Set New Password</${MUI.Button}>
                            </${MUI.Stack}>
                        </form>
                    ` : html`
                        <${MUI.Alert} severity="error" sx=${{ mb: 2 }}>This password reset link is invalid or has expired.</${MUI.Alert}>
                    `)}
                    ${route === 'password-reset-complete' && html`
                        <${MUI.Alert} severity="success" sx=${{ mb: 2 }}>
                            Your password has been reset successfully. You may now sign in.
                        </${MUI.Alert}>
                    `}
                    <${MUI.Button} fullWidth href="/accounts/login/" sx=${{ mt: 2 }}>Return to Sign In</${MUI.Button}>
        </${AuthShellCard}>
    `;
}

export function StaffManagementPage({ me, notify }) {
    const [staff, setStaff] = React.useState([]);
    const [roles, setRoles] = React.useState([]);
    const [history, setHistory] = React.useState([]);
    const [loading, setLoading] = React.useState(true);
    const [search, setSearch] = React.useState('');
    const [roleFilter, setRoleFilter] = React.useState('');
    const [tab, setTab] = React.useState(0);
    const [createOpen, setCreateOpen] = React.useState(false);
    const [editTarget, setEditTarget] = React.useState(null);
    const [deleteTarget, setDeleteTarget] = React.useState(null);
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
            const qs = new URLSearchParams();
            if (search) qs.set('search', search);
            if (roleFilter) qs.set('role', roleFilter);
            const [sRes, rRes, hRes] = await Promise.all([
                apiFetch(`/api/v1/staff/?${qs.toString()}`),
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
    }, [search, roleFilter, notify]);

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

    const handleDeleteStaff = async () => {
        if (!deleteTarget) return;
        try {
            await apiFetch(`/api/v1/staff/${deleteTarget.id}/`, { method: 'DELETE' });
            notify(`Staff account ${deleteTarget.username} deleted.`, 'info');
            setDeleteTarget(null);
            loadData();
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
                    toolbarExtra=${html`
                        <${MUI.TextField}
                            select
                            size="small"
                            label="Filter Role"
                            value=${roleFilter}
                            onChange=${(e) => setRoleFilter(e.target.value)}
                            sx=${{ minWidth: 180 }}
                        >
                            <${MUI.MenuItem} value="">All Staff Roles</${MUI.MenuItem}>
                            ${roles.map((rl) => html`<${MUI.MenuItem} key=${rl.value} value=${rl.value}>${rl.label}</${MUI.MenuItem}>`)}
                        </${MUI.TextField}>
                    `}
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
                                    ${me?.user?.id !== r.id && html`
                                        <${MUI.Button} size="small" color="error" onClick=${() => setDeleteTarget(r)}>Delete</${MUI.Button}>
                                    `}
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
                        <${MUI.Grid} size=${{ xs: 12, sm: 6 }}>
                            <${MUI.TextField} label="First Name" fullWidth value=${form.first_name} onChange=${(e) => setForm({ ...form, first_name: e.target.value })} />
                        </${MUI.Grid}>
                        <${MUI.Grid} size=${{ xs: 12, sm: 6 }}>
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

            <${ResponsiveDialog}
                open=${Boolean(deleteTarget)}
                onClose=${() => setDeleteTarget(null)}
                title=${`Delete Staff Account: ${deleteTarget?.username || ''}`}
                actions=${html`
                    <${MUI.Button} onClick=${() => setDeleteTarget(null)}>Cancel</${MUI.Button}>
                    <${MUI.Button} variant="contained" color="error" onClick=${handleDeleteStaff}>Confirm Delete</${MUI.Button}>
                `}
            >
                <${MUI.Alert} severity="warning" sx=${{ mt: 1 }}>
                    Are you sure you want to permanently remove staff account <strong>${deleteTarget?.username}</strong>? Last active Super Admin and self-deletion are protected.
                </${MUI.Alert}>
            </${ResponsiveDialog}>
        </${MUI.Box}>
    `;
}

export const UsersAdminPage = StaffManagementPage;
