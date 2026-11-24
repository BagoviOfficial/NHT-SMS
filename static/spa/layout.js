import { React, MUI, html, apiFetch } from './api.js';
import { MaterialIcon, ResponsiveDialog } from './components.js';

const DRAWER_WIDTH = 264;

export const NAV_SECTIONS = [
    {
        group: 'Overview',
        items: [
            { id: 'dashboard', label: 'Executive Dashboard', icon: 'dashboard' },
            { id: 'member-portal', label: 'My Member Portal', icon: 'home' },
            { id: 'driver-portal', label: 'My Driver Portal', icon: 'directions_car' },
        ],
    },
    {
        group: 'Fleet & Registry',
        items: [
            { id: 'members', label: 'Members Registry', icon: 'groups' },
            { id: 'vehicles', label: 'Vehicles & QR', icon: 'directions_bus' },
            { id: 'drivers', label: 'PSV Drivers', icon: 'badge' },
            { id: 'routes', label: 'Transit Routes', icon: 'alt_route' },
        ],
    },
    {
        group: 'Compliance & Renewals',
        items: [
            { id: 'documents', label: 'Document Vault', icon: 'folder_shared' },
            { id: 'compliance', label: 'Compliance & Alerts', icon: 'verified_user' },
            { id: 'renewals', label: 'Renewal Workflow', icon: 'autorenew' },
        ],
    },
    {
        group: 'Finance & Accounting',
        items: [
            { id: 'invoices', label: 'Billing & Invoices', icon: 'receipt_long' },
            { id: 'payments', label: 'Payments & Vouchers', icon: 'payments' },
            { id: 'reconciliation', label: 'Reconciliation', icon: 'fact_check' },
            { id: 'accounting', label: 'General Ledger & Reports', icon: 'account_balance' },
        ],
    },
    {
        group: 'Operations & Governance',
        items: [
            { id: 'maintenance', label: 'Maintenance', icon: 'build' },
            { id: 'incidents', label: 'Incidents & Tickets', icon: 'report_problem' },
            { id: 'governance', label: 'Governance', icon: 'gavel' },
            { id: 'notifications', label: 'Notifications', icon: 'notifications' },
            { id: 'reports', label: 'Exports & Analytics', icon: 'assessment' },
        ],
    },
    {
        group: 'Administration',
        items: [
            { id: 'users', label: 'Users & Role Allocation', icon: 'manage_accounts' },
            { id: 'settings', label: 'System Settings & Health', icon: 'tune' },
            { id: 'audit', label: 'Audit Trail', icon: 'fingerprint' },
        ],
    },
];

export function AppLayout({ me, activeRoute, onNavigate, onLogout, notify, children }) {
    const theme = MUI.useTheme();
    const isDesktop = MUI.useMediaQuery(theme.breakpoints.up('md'));
    const [mobileOpen, setMobileOpen] = React.useState(false);
    const [menuAnchor, setMenuAnchor] = React.useState(null);
    const [pwdOpen, setPwdOpen] = React.useState(false);
    const [mfaOpen, setMfaOpen] = React.useState(false);
    const [pwdForm, setPwdForm] = React.useState({ old_password: '', new_password: '' });
    const [mfaData, setMfaData] = React.useState(null);
    const [mfaToken, setMfaToken] = React.useState('');

    const allowed = new Set(me.allowed_sections || []);
    const user = me.user || {};
    const branding = me.branding || {};

    const handleNav = (id) => {
        onNavigate(id);
        setMobileOpen(false);
    };

    const openMfaDialog = async () => {
        setMenuAnchor(null);
        setMfaOpen(true);
        try {
            const res = await apiFetch('/api/v1/auth/mfa/setup/');
            setMfaData(res);
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const handleVerifyMfa = async () => {
        try {
            const res = await apiFetch('/api/v1/auth/mfa/setup/', {
                method: 'POST',
                body: { token: mfaToken },
            });
            notify(res.message || 'MFA enabled!', 'success');
            setMfaOpen(false);
            setMfaToken('');
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const handleChangePassword = async () => {
        try {
            const res = await apiFetch('/api/v1/auth/password-change/', {
                method: 'POST',
                body: pwdForm,
            });
            notify(res.message || 'Password updated.', 'success');
            setPwdOpen(false);
            setPwdForm({ old_password: '', new_password: '' });
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const drawerContent = html`
        <${MUI.Box} sx=${{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            <${MUI.Box}
                sx=${{
                    p: 2.5,
                    background: 'linear-gradient(135deg, #091E38 0%, #10315C 100%)',
                    color: '#FFFFFF',
                    borderBottom: '3px solid #FF8A00',
                }}
            >
                <${MUI.Box} sx=${{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                    <${MUI.Avatar} sx=${{ bgcolor: '#FF8A00', color: '#091E38', fontWeight: 800 }}>
                        <${MaterialIcon} name="local_shipping" />
                    </${MUI.Avatar}>
                    <${MUI.Box} sx=${{ minWidth: 0 }}>
                        <${MUI.Typography} variant="subtitle1" sx=${{ fontWeight: 800, lineHeight: 1.2 }} noWrap>
                            NHT-SMS
                        </${MUI.Typography}>
                        <${MUI.Typography} variant="caption" sx=${{ color: 'rgba(255,255,255,0.78)' }} noWrap display="block">
                            ${branding.sacco_name || 'Northern Highways SACCO'}
                        </${MUI.Typography}>
                    </${MUI.Box}>
                </${MUI.Box}>
                <${MUI.Chip}
                    size="small"
                    label=${user.role_display || user.role}
                    sx=${{ mt: 1.5, bgcolor: 'rgba(255,255,255,0.14)', color: '#FFFFFF', fontWeight: 700 }}
                />
            </${MUI.Box}>

            <${MUI.Box} sx=${{ flexGrow: 1, overflowY: 'auto', py: 1 }}>
                ${NAV_SECTIONS.map((section) => {
                    const visibleItems = section.items.filter((it) => allowed.has(it.id));
                    if (visibleItems.length === 0) return null;
                    return html`
                        <${MUI.List}
                            key=${section.group}
                            dense
                            subheader=${html`
                                <${MUI.ListSubheader}
                                    component="div"
                                    sx=${{ bgcolor: 'transparent', fontWeight: 800, fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'text.secondary' }}
                                >
                                    ${section.group}
                                </${MUI.ListSubheader}>
                            `}
                        >
                            ${visibleItems.map((item) => {
                                const selected = activeRoute === item.id;
                                return html`
                                    <${MUI.ListItemButton}
                                        key=${item.id}
                                        selected=${selected}
                                        onClick=${() => handleNav(item.id)}
                                        sx=${{
                                            mx: 1,
                                            my: 0.25,
                                            borderRadius: 2,
                                            '&.Mui-selected': {
                                                bgcolor: 'primary.main',
                                                color: '#FFFFFF',
                                                '& .MuiIcon-root': { color: '#FF8A00' },
                                                '&:hover': { bgcolor: 'primary.dark' },
                                            },
                                        }}
                                    >
                                        <${MUI.ListItemIcon} sx=${{ minWidth: 36 }}>
                                            <${MaterialIcon} name=${item.icon} />
                                        </${MUI.ListItemIcon}>
                                        <${MUI.ListItemText}
                                            primary=${item.label}
                                            primaryTypographyProps=${{ fontSize: '0.86rem', fontWeight: selected ? 700 : 500 }}
                                        />
                                    </${MUI.ListItemButton}>
                                `;
                            })}
                        </${MUI.List}>
                    `;
                })}
            </${MUI.Box}>

            <${MUI.Divider} />
            <${MUI.Box} sx=${{ p: 1.5, display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                ${user.is_management_staff && html`
                    <${MUI.Button}
                        size="small"
                        variant="text"
                        href="/accounts/dashboard/"
                        startIcon=${html`<${MaterialIcon} name="open_in_new" />`}
                        sx=${{ justifyContent: 'flex-start' }}
                    >
                        Classic Staff View
                    </${MUI.Button}>
                `}
                ${user.is_member && html`
                    <${MUI.Button}
                        size="small"
                        variant="text"
                        href="/portal/"
                        startIcon=${html`<${MaterialIcon} name="open_in_new" />`}
                        sx=${{ justifyContent: 'flex-start' }}
                    >
                        Classic Member Portal
                    </${MUI.Button}>
                `}
                ${user.is_superuser && html`
                    <${MUI.Button}
                        size="small"
                        variant="text"
                        href="/admin/"
                        startIcon=${html`<${MaterialIcon} name="admin_panel_settings" />`}
                        sx=${{ justifyContent: 'flex-start' }}
                    >
                        Django Admin Core
                    </${MUI.Button}>
                `}
            </${MUI.Box}>
        </${MUI.Box}>
    `;

    return html`
        <${MUI.Box} sx=${{ display: 'flex', minHeight: '100vh', bgcolor: 'background.default' }}>
            <${MUI.AppBar}
                position="fixed"
                elevation=${1}
                sx=${{
                    width: { md: `calc(100% - ${DRAWER_WIDTH}px)` },
                    ml: { md: `${DRAWER_WIDTH}px` },
                    bgcolor: '#FFFFFF',
                    color: 'text.primary',
                    borderBottom: '1px solid rgba(15,23,42,0.08)',
                }}
            >
                <${MUI.Toolbar}>
                    ${!isDesktop && html`
                        <${MUI.IconButton}
                            edge="start"
                            onClick=${() => setMobileOpen(!mobileOpen)}
                            sx=${{ mr: 1.5 }}
                            aria-label="Open menu"
                        >
                            <${MaterialIcon} name="menu" />
                        </${MUI.IconButton}>
                    `}
                    <${MUI.Typography} variant="subtitle1" sx=${{ fontWeight: 700, flexGrow: 1 }} noWrap>
                        ${branding.sacco_name || 'Northern Highways Transporters SACCO'}
                    </${MUI.Typography}>

                    <${MUI.Button}
                        color="inherit"
                        onClick=${(e) => setMenuAnchor(e.currentTarget)}
                        startIcon=${html`
                            <${MUI.Avatar} sx=${{ width: 30, height: 30, bgcolor: 'primary.main', fontSize: '0.8rem' }}>
                                ${(user.full_name || user.username || 'U')[0].toUpperCase()}
                            </${MUI.Avatar}>
                        `}
                        endIcon=${html`<${MaterialIcon} name="expand_more" />`}
                    >
                        <${MUI.Box} sx=${{ display: { xs: 'none', sm: 'block' }, textAlign: 'left' }}>
                            <${MUI.Typography} variant="body2" sx=${{ fontWeight: 700, lineHeight: 1.1 }}>
                                ${user.full_name || user.username}
                            </${MUI.Typography}>
                            <${MUI.Typography} variant="caption" color="text.secondary">
                                ${user.role_display}
                            </${MUI.Typography}>
                        </${MUI.Box}>
                    </${MUI.Button}>

                    <${MUI.Menu}
                        anchorEl=${menuAnchor}
                        open=${Boolean(menuAnchor)}
                        onClose=${() => setMenuAnchor(null)}
                    >
                        <${MUI.MenuItem} onClick=${() => { setMenuAnchor(null); setPwdOpen(true); }}>
                            <${MUI.ListItemIcon}><${MaterialIcon} name="key" /></${MUI.ListItemIcon}>
                            Change Password
                        </${MUI.MenuItem}>
                        <${MUI.MenuItem} onClick=${openMfaDialog}>
                            <${MUI.ListItemIcon}><${MaterialIcon} name="security" /></${MUI.ListItemIcon}>
                            Two-Factor Auth (TOTP)
                        </${MUI.MenuItem}>
                        <${MUI.Divider} />
                        <${MUI.MenuItem} onClick=${() => { setMenuAnchor(null); onLogout(); }} sx=${{ color: 'error.main' }}>
                            <${MUI.ListItemIcon}><${MaterialIcon} name="logout" color="error" /></${MUI.ListItemIcon}>
                            Secure Logout
                        </${MUI.MenuItem}>
                    </${MUI.Menu}>
                </${MUI.Toolbar}>
            </${MUI.AppBar}>

            <${MUI.Box} component="nav" sx=${{ width: { md: DRAWER_WIDTH }, flexShrink: { md: 0 } }}>
                ${isDesktop ? html`
                    <${MUI.Drawer}
                        variant="permanent"
                        open
                        PaperProps=${{ sx: { width: DRAWER_WIDTH, boxSizing: 'border-box', borderRight: '1px solid rgba(15,23,42,0.08)' } }}
                    >
                        ${drawerContent}
                    </${MUI.Drawer}>
                ` : html`
                    <${MUI.Drawer}
                        variant="temporary"
                        open=${mobileOpen}
                        onClose=${() => setMobileOpen(false)}
                        ModalProps=${{ keepMounted: true }}
                        PaperProps=${{ sx: { width: DRAWER_WIDTH, boxSizing: 'border-box' } }}
                    >
                        ${drawerContent}
                    </${MUI.Drawer}>
                `}
            </${MUI.Box}>

            <${MUI.Box}
                component="main"
                sx=${{
                    flexGrow: 1,
                    p: { xs: 2, sm: 3 },
                    mt: 8,
                    width: { md: `calc(100% - ${DRAWER_WIDTH}px)` },
                    maxWidth: '100%',
                    overflowX: 'hidden',
                }}
            >
                ${children}
            </${MUI.Box}>

            <${ResponsiveDialog}
                open=${pwdOpen}
                onClose=${() => setPwdOpen(false)}
                title="Change Account Password"
                actions=${html`
                    <${MUI.Button} onClick=${() => setPwdOpen(false)}>Cancel</${MUI.Button}>
                    <${MUI.Button} variant="contained" onClick=${handleChangePassword}>Update Password</${MUI.Button}>
                `}
            >
                <${MUI.Stack} spacing=${2} sx=${{ pt: 1 }}>
                    <${MUI.TextField}
                        label="Current Password"
                        type="password"
                        fullWidth
                        value=${pwdForm.old_password}
                        onChange=${(e) => setPwdForm({ ...pwdForm, old_password: e.target.value })}
                    />
                    <${MUI.TextField}
                        label="New Password (min 10 chars)"
                        type="password"
                        fullWidth
                        value=${pwdForm.new_password}
                        onChange=${(e) => setPwdForm({ ...pwdForm, new_password: e.target.value })}
                    />
                </${MUI.Stack}>
            </${ResponsiveDialog}>

            <${ResponsiveDialog}
                open=${mfaOpen}
                onClose=${() => setMfaOpen(false)}
                title="Two-Factor Authentication (TOTP)"
                actions=${html`
                    <${MUI.Button} onClick=${() => setMfaOpen(false)}>Close</${MUI.Button}>
                    ${mfaData && !mfaData.enabled && html`
                        <${MUI.Button} variant="contained" onClick=${handleVerifyMfa}>Verify & Activate</${MUI.Button}>
                    `}
                `}
            >
                ${!mfaData ? html`<${MUI.CircularProgress} />` : mfaData.enabled ? html`
                    <${MUI.Alert} severity="success">
                        Two-factor authentication is currently active on device: <strong>${mfaData.device_name}</strong>.
                    </${MUI.Alert}>
                ` : html`
                    <${MUI.Stack} spacing=${2} alignItems="center">
                        <${MUI.Typography} variant="body2" color="text.secondary">
                            Scan this QR code in Google Authenticator / Authy, then enter the 6-digit code below.
                        </${MUI.Typography}>
                        <img src=${mfaData.qr_data_url} alt="TOTP QR" style=${{ maxWidth: 200, borderRadius: 8 }} />
                        <${MUI.TextField}
                            label="6-Digit Authenticator Code"
                            fullWidth
                            value=${mfaToken}
                            onChange=${(e) => setMfaToken(e.target.value)}
                        />
                    </${MUI.Stack}>
                `}
            </${ResponsiveDialog}>
        </${MUI.Box}>
    `;
}
