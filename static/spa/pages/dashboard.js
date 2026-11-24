import { React, MUI, html, apiFetch, formatCurrency, formatDateTime } from '../api.js';
import { PageHeader, StatCard, StatusChip, ResponsiveDataGrid } from '../components.js';

export function DashboardPage({ notify }) {
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
        if (!data || !window.ApexCharts) return;
        const k = data.kpis;
        let compChart = null;
        let fleetChart = null;

        if (compChartRef.current) {
            compChartRef.current.innerHTML = '';
            compChart = new window.ApexCharts(compChartRef.current, {
                chart: { type: 'donut', height: 260 },
                series: [k.compliant_vehicles || 0, k.delinquent_vehicles || 0],
                labels: ['Compliant Fleet', 'Delinquent / Expired'],
                colors: ['#15803D', '#B91C1C'],
                legend: { position: 'bottom' },
            });
            compChart.render();
        }

        if (fleetChartRef.current) {
            fleetChartRef.current.innerHTML = '';
            fleetChart = new window.ApexCharts(fleetChartRef.current, {
                chart: { type: 'bar', height: 260, toolbar: { show: false } },
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

    return html`
        <${MUI.Box}>
            <${PageHeader}
                title="SACCO Executive & Operations Overview"
                subtitle="Real-time fleet compliance, membership, treasury collections, and audit activity."
            />

            <${MUI.Grid} container spacing=${2.5} sx=${{ mb: 3 }}>
                <${MUI.Grid} item xs=${12} sm=${6} md=${3}>
                    <${StatCard}
                        title="Registered Members"
                        value=${k.total_members}
                        subtitle="${k.active_members} active • ${k.pending_members} pending"
                        icon="groups"
                        color="primary"
                    />
                </${MUI.Grid}>
                <${MUI.Grid} item xs=${12} sm=${6} md=${3}>
                    <${StatCard}
                        title="Fleet Compliance"
                        value="${k.compliance_rate}%"
                        subtitle="${k.compliant_vehicles}/${k.total_vehicles} vehicles compliant"
                        icon="verified_user"
                        color="success"
                    />
                </${MUI.Grid}>
                <${MUI.Grid} item xs=${12} sm=${6} md=${3}>
                    <${StatCard}
                        title="Expiring / Expired Docs"
                        value="${k.expiring_docs} / ${k.expired_docs}"
                        subtitle="Next 30 days vs overdue"
                        icon="warning_amber"
                        color="warning"
                    />
                </${MUI.Grid}>
                <${MUI.Grid} item xs=${12} sm=${6} md=${3}>
                    <${StatCard}
                        title=${fin.restricted ? 'Active Routes' : 'Collections Cleared'}
                        value=${fin.restricted ? (k.route_distribution || []).length : formatCurrency(fin.total_collected)}
                        subtitle=${fin.restricted ? 'Authorized corridors' : `Outstanding: ${formatCurrency(fin.total_outstanding)}`}
                        icon=${fin.restricted ? 'alt_route' : 'payments'}
                        color="info"
                    />
                </${MUI.Grid}>
            </${MUI.Grid}>

            <${MUI.Grid} container spacing=${2.5} sx=${{ mb: 3 }}>
                <${MUI.Grid} item xs=${12} md=${5}>
                    <${MUI.Card} sx=${{ p: 2.5, height: '100%' }}>
                        <${MUI.Typography} variant="h6" sx=${{ mb: 1 }}>Fleet Compliance Breakdown</${MUI.Typography}>
                        <div ref=${compChartRef}></div>
                    </${MUI.Card}>
                </${MUI.Grid}>
                <${MUI.Grid} item xs=${12} md=${7}>
                    <${MUI.Card} sx=${{ p: 2.5, height: '100%' }}>
                        <${MUI.Typography} variant="h6" sx=${{ mb: 1 }}>PSV Fleet Categories</${MUI.Typography}>
                        <div ref=${fleetChartRef}></div>
                    </${MUI.Card}>
                </${MUI.Grid}>
            </${MUI.Grid}>

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
