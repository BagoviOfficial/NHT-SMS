import ApexCharts from 'apexcharts';
import { React, MUI, html, apiFetch, formatCurrency, formatDateTime } from '../api.js';
import { PageHeader, StatCard, StatusChip, ResponsiveDataGrid } from '../components.js';

export function DashboardPage({ me, notify }) {
    const [data, setData] = React.useState(null);
    const [loading, setLoading] = React.useState(true);
    const compChartRef = React.useRef(null);
    const fleetChartRef = React.useRef(null);

    React.useEffect(() => {
        let mounted = true;
        apiFetch('/api/v1/dashboard/')
            .then((res) => { if (mounted) setData(res); })
            .catch((err) => notify(err.message, 'error'))
            .finally(() => { if (mounted) setLoading(false); });
        return () => { mounted = false; };
    }, [notify]);

    React.useEffect(() => {
        if (!data || !ApexCharts) return;
        const k = data.kpis;
        let compChart = null;
        let fleetChart = null;

        if (compChartRef.current) {
            compChartRef.current.innerHTML = '';
            compChart = new ApexCharts(compChartRef.current, {
                chart: { type: 'donut', height: 250 },
                series: [k.compliant_vehicles || 0, k.delinquent_vehicles || 0],
                labels: ['Compliant Fleet', 'Delinquent / Expired'],
                colors: ['#15803D', '#B91C1C'],
                legend: { position: 'bottom' },
            });
            compChart.render();
        }

        if (fleetChartRef.current) {
            fleetChartRef.current.innerHTML = '';
            fleetChart = new ApexCharts(fleetChartRef.current, {
                chart: { type: 'bar', height: 250, toolbar: { show: false } },
                series: [{ name: 'Vehicles', data: (data.fleet_categories || []).map((c) => c.count) }],
                xaxis: { categories: (data.fleet_categories || []).map((c) => c.category) },
                colors: ['#10315C'],
                plotOptions: { bar: { borderRadius: 6, columnWidth: '48%' } },
            });
            fleetChart.render();
        }

        return () => {
            if (compChart) compChart.destroy();
            if (fleetChart) fleetChart.destroy();
        };
    }, [data]);

    if (loading || !data) {
        return html`<${MUI.Box} sx=${{ p: 5, textAlign: 'center' }}><${MUI.CircularProgress} /></${MUI.Box}>`;
    }

    const k = data.kpis;
    const fin = k.financials || {};
    const role = me?.user?.role || '';

    return html`
        <${MUI.Box}>
            <${PageHeader}
                title="Enterprise SACCO Executive & Operations Dashboard"
                subtitle=${`Live database intelligence tailored for ${me?.user?.role_display || role}.`}
            />

            <${MUI.Grid} container spacing=${2.2} sx=${{ mb: 3 }}>
                <${MUI.Grid} size=${{ xs: 12, sm: 6, md: 3 }}>
                    <${StatCard}
                        title="SACCO Members"
                        value=${k.total_members}
                        subtitle="${k.active_members} active • ${k.pending_members} pending • ${k.suspended_members || 0} suspended"
                        icon="groups"
                        color="primary"
                    />
                </${MUI.Grid}>
                <${MUI.Grid} size=${{ xs: 12, sm: 6, md: 3 }}>
                    <${StatCard}
                        title="Fleet & Compliance"
                        value="${k.compliance_rate}%"
                        subtitle="${k.active_vehicles || k.total_vehicles} active • ${k.vehicles_awaiting_compliance || 0} awaiting"
                        icon="verified_user"
                        color="success"
                    />
                </${MUI.Grid}>
                <${MUI.Grid} size=${{ xs: 12, sm: 6, md: 3 }}>
                    <${StatCard}
                        title="Certificates & Permits"
                        value="${k.expiring_certificates || 0} / ${k.expired_certificates || 0}"
                        subtitle="Expiring / Expired cards (${k.expiring_docs} docs ≤30d)"
                        icon="qr_code_2"
                        color="warning"
                    />
                </${MUI.Grid}>
                <${MUI.Grid} size=${{ xs: 12, sm: 6, md: 3 }}>
                    <${StatCard}
                        title=${fin.restricted ? 'Active Transit Routes' : 'Collections Cleared'}
                        value=${fin.restricted ? (k.active_routes ?? (k.route_distribution || []).length) : formatCurrency(fin.total_collected)}
                        subtitle=${fin.restricted ? `${k.system_alerts || 0} alerts • ${k.pending_approvals || 0} approvals` : `Outstanding: ${formatCurrency(fin.total_outstanding)}`}
                        icon=${fin.restricted ? 'alt_route' : 'payments'}
                        color="info"
                    />
                </${MUI.Grid}>

                ${!fin.restricted && html`
                    <${MUI.Grid} size=${{ xs: 12, sm: 6, md: 3 }}>
                        <${StatCard}
                            title="Total Billed (Invoices)"
                            value=${formatCurrency(fin.total_invoiced)}
                            subtitle="Gross billed fees & statutory"
                            icon="receipt_long"
                            color="primary"
                        />
                    </${MUI.Grid}>
                    <${MUI.Grid} size=${{ xs: 12, sm: 6, md: 3 }}>
                        <${StatCard}
                            title="Approved Expenditure"
                            value=${formatCurrency(fin.total_expenses)}
                            subtitle="Net Cash: ${formatCurrency(fin.net_cash)}"
                            icon="account_balance"
                            color="warning"
                        />
                    </${MUI.Grid}>
                    <${MUI.Grid} size=${{ xs: 12, sm: 6, md: 3 }}>
                        <${StatCard}
                            title="Active Routes"
                            value=${k.active_routes || 0}
                            subtitle="Authorized NTSA corridors"
                            icon="alt_route"
                            color="info"
                        />
                    </${MUI.Grid}>
                    <${MUI.Grid} size=${{ xs: 12, sm: 6, md: 3 }}>
                        <${StatCard}
                            title="Alerts & Approvals"
                            value="${k.system_alerts || 0} / ${k.pending_approvals || 0}"
                            subtitle="Open alerts / Pending approvals"
                            icon="notifications_active"
                            color="error"
                        />
                    </${MUI.Grid}>
                `}
            </${MUI.Grid}>

            <${MUI.Grid} container spacing=${2.5} sx=${{ mb: 3 }}>
                <${MUI.Grid} size=${{ xs: 12, md: 5 }}>
                    <${MUI.Card} sx=${{ p: 2.5, height: '100%' }}>
                        <${MUI.Typography} variant="h6" sx=${{ mb: 1 }}>Fleet Compliance Breakdown</${MUI.Typography}>
                        <div ref=${compChartRef}></div>
                    </${MUI.Card}>
                </${MUI.Grid}>
                <${MUI.Grid} size=${{ xs: 12, md: 7 }}>
                    <${MUI.Card} sx=${{ p: 2.5, height: '100%' }}>
                        <${MUI.Typography} variant="h6" sx=${{ mb: 1 }}>Commercial Fleet Categories</${MUI.Typography}>
                        <div ref=${fleetChartRef}></div>
                    </${MUI.Card}>
                </${MUI.Grid}>
            </${MUI.Grid}>

            ${!fin.restricted && (data.recent_transactions || []).length > 0 && html`
                <${MUI.Box} sx=${{ mb: 3 }}>
                    <${MUI.Typography} variant="h6" sx=${{ mb: 1.5 }}>Recent Settled Transactions</${MUI.Typography}>
                    <${ResponsiveDataGrid}
                        rows=${data.recent_transactions}
                        columns=${[
                            { key: 'reference', label: 'Ref #', render: (r) => html`<span className="nht-mono">${r.reference}</span>` },
                            { key: 'member_name', label: 'Member' },
                            { key: 'invoice_number', label: 'Invoice #' },
                            { key: 'method', label: 'Method' },
                            { key: 'amount', label: 'Amount', align: 'right', render: (r) => formatCurrency(r.amount) },
                            { key: 'confirmed_at', label: 'Confirmed', render: (r) => formatDateTime(r.confirmed_at) },
                        ]}
                    />
                </${MUI.Box}>
            `}

            <${MUI.Typography} variant="h6" sx=${{ mb: 1.5 }}>Recent System Activity</${MUI.Typography}>
            <${ResponsiveDataGrid}
                rows=${data.recent_audit || []}
                columns=${[
                    { key: 'timestamp', label: 'Timestamp', render: (r) => formatDateTime(r.timestamp) },
                    { key: 'actor', label: 'Actor' },
                    { key: 'action', label: 'Action', render: (r) => html`<${MUI.Chip} size="small" label=${r.action} />` },
                    { key: 'entity_type', label: 'Entity', render: (r) => `${r.entity_type} (${r.entity_id || '—'})` },
                    { key: 'outcome', label: 'Outcome', render: (r) => html`<${StatusChip} value=${r.outcome} />` },
                ]}
            />
        </${MUI.Box}>
    `;
}
