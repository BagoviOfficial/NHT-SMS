import { React, ReactDOM, MUI, html, apiFetch } from './api.js';
import { createNhtTheme } from './theme.js';
import { AppLayout } from './layout.js';
import { LoginPage, UsersAdminPage } from './pages/auth.js';
import { DashboardPage } from './pages/dashboard.js';
import { MembersPage, VehiclesPage, DriversPage, RoutesPage } from './pages/fleet.js';
import { DocumentsPage, CompliancePage, RenewalsPage } from './pages/compliance.js';
import { InvoicesPage, PaymentsVouchersPage, ReconciliationPage } from './pages/finance.js';
import { AccountingPage } from './pages/accounting.js';
import { MaintenancePage, IncidentsPage, GovernancePage, NotificationsPage } from './pages/operations.js';
import { MemberPortalPage, DriverPortalPage } from './pages/portals.js';
import { SettingsCenterPage, AuditTrailPage, ReportsPage } from './pages/admin_center.js';

const ROUTE_MAP = {
    'dashboard': DashboardPage,
    'member-portal': MemberPortalPage,
    'driver-portal': DriverPortalPage,
    'members': MembersPage,
    'vehicles': VehiclesPage,
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
    'users': UsersAdminPage,
    'settings': SettingsCenterPage,
    'audit': AuditTrailPage,
    'reports': ReportsPage,
};

function getHashRoute(defaultRoute) {
    const raw = (window.location.hash || '').replace(/^#\/?/, '').trim();
    return raw && ROUTE_MAP[raw] ? raw : defaultRoute;
}

function App() {
    const [me, setMe] = React.useState(null);
    const [loading, setLoading] = React.useState(true);
    const [route, setRoute] = React.useState('dashboard');
    const [toast, setToast] = React.useState({ open: false, message: '', severity: 'info' });

    const notify = React.useCallback((message, severity = 'info') => {
        setToast({ open: true, message, severity });
    }, []);

    const syncMe = React.useCallback(async () => {
        setLoading(true);
        try {
            const data = await apiFetch('/api/v1/auth/me/');
            setMe(data);
            if (data.authenticated) {
                const def = data.user?.default_route || 'dashboard';
                setRoute(getHashRoute(def));
            }
        } catch (err) {
            notify(err.message, 'error');
        } finally {
            setLoading(false);
        }
    }, [notify]);

    React.useEffect(() => { syncMe(); }, [syncMe]);

    React.useEffect(() => {
        const onHash = () => {
            if (me?.authenticated) {
                setRoute(getHashRoute(me.user?.default_route || 'dashboard'));
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
        () => createNhtTheme(me?.branding || window.__NHT_BOOTSTRAP__ || {}),
        [me]
    );

    let content = null;
    if (loading || !me) {
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
                    const def = payload.user?.default_route || 'dashboard';
                    navigate(def);
                }}
            />
        `;
    } else {
        const allowed = new Set(me.allowed_sections || []);
        const PageComponent = ROUTE_MAP[route];
        const isPermitted = allowed.has(route) && PageComponent;

        content = html`
            <${AppLayout}
                me=${me}
                activeRoute=${route}
                onNavigate=${navigate}
                onLogout=${handleLogout}
                notify=${notify}
            >
                ${isPermitted ? html`
                    <${PageComponent} me=${me} notify=${notify} />
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

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(html`<${App} />`);
