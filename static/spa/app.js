import { React, createRoot, MUI, html, apiFetch } from './api.js';
import { createNhtTheme } from './theme.js';
import { AppLayout } from './layout.js';
import {
    LockoutPage,
    LoginPage,
    PasswordChangePage,
    PasswordResetPage,
    ProfilePage,
    StaffManagementPage,
} from './pages/auth.js';
import { DashboardPage } from './pages/dashboard.js';
import { MembersPage, VehiclesPage, DriversPage, RoutesPage } from './pages/fleet.js';
import { DocumentsPage, CompliancePage, ComplianceCardsPage, RenewalsPage } from './pages/compliance.js';
import { InvoicesPage, PaymentsVouchersPage, ReconciliationPage } from './pages/finance.js';
import { AccountingPage } from './pages/accounting.js';
import { MaintenancePage, IncidentsPage, GovernancePage, NotificationsPage } from './pages/operations.js';
import { MemberPortalPage, DriverPortalPage } from './pages/portals.js';
import { SuperAdminConsolePage, SettingsCenterPage, AuditTrailPage, ReportsPage } from './pages/admin_center.js';
import { PublicVerifyPage, ReceiptDetailPage } from './pages/public_pages.js';

const ROUTE_MAP = {
    'superadmin': SuperAdminConsolePage,
    'dashboard': DashboardPage,
    'member-portal': MemberPortalPage,
    'driver-portal': DriverPortalPage,
    'members': MembersPage,
    'vehicles': VehiclesPage,
    'compliance-cards': ComplianceCardsPage,
    'drivers': DriversPage,
    'routes': RoutesPage,
    'documents': DocumentsPage,
    'compliance': CompliancePage,
    'renewals': RenewalsPage,
    'invoices': InvoicesPage,
    'payments': PaymentsVouchersPage,
    'reconciliation': ReconciliationPage,
    'accounting': AccountingPage,
    'maintenance': MaintenancePage,
    'incidents': IncidentsPage,
    'governance': GovernancePage,
    'notifications': NotificationsPage,
    'staff': StaffManagementPage,
    'users': StaffManagementPage,
    'settings': SettingsCenterPage,
    'audit': AuditTrailPage,
    'reports': ReportsPage,
    'profile': ProfilePage,
    'password-change': PasswordChangePage,
    'receipt-detail': ReceiptDetailPage,
};

const STANDALONE_PUBLIC_ROUTES = new Set([
    'public-verify',
    'lockout',
    'password-reset',
    'password-reset-done',
    'password-reset-confirm',
    'password-reset-complete',
]);

const UNIVERSAL_AUTH_ROUTES = new Set(['profile', 'password-change', 'receipt-detail']);

function getInitialRouteFromBootstrap() {
    return (window.__NHT_BOOTSTRAP__?.initial_route || '').trim();
}

function isAdminPortalContext() {
    return Boolean(window.__NHT_BOOTSTRAP__?.is_admin_portal || window.location.pathname.startsWith('/admin'));
}

function resolveDefaultRoute(payload) {
    const bootRoute = getInitialRouteFromBootstrap();
    if (bootRoute && ROUTE_MAP[bootRoute] && bootRoute !== 'login') {
        return bootRoute;
    }
    if (isAdminPortalContext() && (payload?.user?.role === 'SUPER_ADMIN' || payload?.user?.is_superuser)) {
        return 'superadmin';
    }
    return payload?.user?.default_route || 'dashboard';
}

function getHashRoute(defaultRoute) {
    const raw = (window.location.hash || '').replace(/^#\/?/, '').trim();
    return raw && ROUTE_MAP[raw] ? raw : defaultRoute;
}

function App() {
    const bootRoute = getInitialRouteFromBootstrap();
    const isStandalonePublic = STANDALONE_PUBLIC_ROUTES.has(bootRoute);

    const [me, setMe] = React.useState(null);
    const [loading, setLoading] = React.useState(!isStandalonePublic);
    const [route, setRoute] = React.useState(bootRoute || 'dashboard');
    const [mode, setMode] = React.useState(() => localStorage.getItem('nht_theme_mode') || 'light');
    const [toast, setToast] = React.useState({ open: false, message: '', severity: 'info' });

    const notify = React.useCallback((message, severity = 'info') => {
        setToast({ open: true, message, severity });
    }, []);

    const toggleThemeMode = React.useCallback(() => {
        setMode((prev) => {
            const next = prev === 'light' ? 'dark' : 'light';
            localStorage.setItem('nht_theme_mode', next);
            return next;
        });
    }, []);

    const syncMe = React.useCallback(async () => {
        if (isStandalonePublic) return;
        setLoading(true);
        try {
            const data = await apiFetch('/api/v1/auth/me/');
            setMe(data);
            if (data.authenticated) {
                const def = resolveDefaultRoute(data);
                setRoute(getHashRoute(def));
            }
        } catch (err) {
            notify(err.message, 'error');
        } finally {
            setLoading(false);
        }
    }, [isStandalonePublic, notify]);

    React.useEffect(() => { syncMe(); }, [syncMe]);

    React.useEffect(() => {
        const onHash = () => {
            if (me?.authenticated) {
                setRoute(getHashRoute(resolveDefaultRoute(me)));
            }
        };
        window.addEventListener('hashchange', onHash);
        return () => window.removeEventListener('hashchange', onHash);
    }, [me]);

    const navigate = (nextRoute) => {
        window.location.hash = `#${nextRoute}`;
        setRoute(nextRoute);
    };

    const handleLogout = async () => {
        try {
            await apiFetch('/api/v1/auth/logout/', { method: 'POST' });
            window.location.hash = '';
            await syncMe();
            notify('Signed out safely.', 'info');
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const theme = React.useMemo(
        () => createNhtTheme(me?.branding || window.__NHT_BOOTSTRAP__ || {}, mode),
        [me, mode]
    );

    let content = null;
    if (bootRoute === 'public-verify') {
        content = html`<${PublicVerifyPage} branding=${window.__NHT_BOOTSTRAP__} />`;
    } else if (bootRoute === 'lockout') {
        content = html`<${LockoutPage} />`;
    } else if (bootRoute.startsWith('password-reset')) {
        content = html`<${PasswordResetPage} route=${bootRoute} />`;
    } else if (loading || !me) {
        content = html`
            <${MUI.Box} sx=${{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <${MUI.CircularProgress} />
            </${MUI.Box}>
        `;
    } else if (!me.authenticated) {
        content = html`
            <${LoginPage}
                branding=${me.branding}
                onLoginSuccess=${(payload) => {
                    setMe(payload);
                    const def = resolveDefaultRoute(payload);
                    navigate(def);
                }}
            />
        `;
    } else if (isAdminPortalContext() && !me.user?.is_management_staff && !me.user?.is_superuser) {
        content = html`
            <${MUI.Box} sx=${{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', p: 3 }}>
                <${MUI.Card} sx=${{ maxWidth: 480, p: 3 }}>
                    <${MUI.Alert} severity="error" sx=${{ mb: 2 }}>
                        Access Denied (403): The <strong>/admin/</strong> Material UI Admin Dashboard is restricted to SACCO management and Super Administrator accounts.
                    </${MUI.Alert}>
                    <${MUI.Stack} direction="row" spacing=${1.5}>
                        <${MUI.Button} variant="contained" href="/app/">Open Self-Service Portal</${MUI.Button}>
                        <${MUI.Button} variant="outlined" color="error" onClick=${handleLogout}>Sign Out</${MUI.Button}>
                    </${MUI.Stack}>
                </${MUI.Card}>
            </${MUI.Box}>
        `;
    } else {
        const allowed = new Set(me.allowed_sections || []);
        const PageComponent = ROUTE_MAP[route];
        const isPermitted = Boolean(PageComponent) && (allowed.has(route) || UNIVERSAL_AUTH_ROUTES.has(route));

        content = html`
            <${AppLayout}
                me=${me}
                activeRoute=${route}
                onNavigate=${navigate}
                onLogout=${handleLogout}
                notify=${notify}
                themeMode=${mode}
                onToggleTheme=${toggleThemeMode}
            >
                ${isPermitted ? html`
                    <${PageComponent} me=${me} notify=${notify} onRefreshMe=${syncMe} onNavigate=${navigate} />
                ` : html`
                    <${MUI.Alert} severity="error" sx=${{ mt: 2 }}>
                        Access Denied (403): Your role (<strong>${me.user?.role_display}</strong>) is not cleared for the <strong>${route}</strong> module.
                    </${MUI.Alert}>
                `}
            </${AppLayout}>
        `;
    }

    return html`
        <${MUI.ThemeProvider} theme=${theme}>
            <${MUI.CssBaseline} />
            ${content}
            <${MUI.Snackbar}
                open=${toast.open}
                autoHideDuration=${5000}
                onClose=${() => setToast((prev) => ({ ...prev, open: false }))}
                anchorOrigin=${{ vertical: 'bottom', horizontal: 'right' }}
            >
                <${MUI.Alert}
                    severity=${toast.severity}
                    variant="filled"
                    onClose=${() => setToast((prev) => ({ ...prev, open: false }))}
                >
                    ${toast.message}
                </${MUI.Alert}>
            </${MUI.Snackbar}>
        </${MUI.ThemeProvider}>
    `;
}

const root = createRoot(document.getElementById('root'));
root.render(html`<${App} />`);
