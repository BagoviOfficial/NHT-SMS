import { React, MUI, html, apiFetch, extractList, formatCurrency, formatDateTime } from '../api.js';
import { PageHeader, ResponsiveDataGrid, ResponsiveDialog, StatusChip } from '../components.js';

export function MaintenancePage({ notify }) {
    const [records, setRecords] = React.useState([]);
    const [loading, setLoading] = React.useState(true);

    const load = React.useCallback(async () => {
        setLoading(true);
        try {
            const res = await apiFetch('/api/v1/maintenance/');
            setRecords(extractList(res));
        } catch (err) {
            notify(err.message, 'error');
        } finally {
            setLoading(false);
        }
    }, [notify]);

    React.useEffect(() => { load(); }, [load]);

    const completeOrder = async (id) => {
        try {
            await apiFetch(`/api/v1/maintenance/${id}/complete/`, { method: 'POST', body: { downtime_hours: 4 } });
            notify('Maintenance work order completed.', 'success');
            load();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    return html`
        <${MUI.Box}>
            <${PageHeader} title="Fleet Maintenance & Work Orders" subtitle="Workshop bookings, parts & labour costs, and vehicle downtime tracking." />
            <${ResponsiveDataGrid}
                loading=${loading}
                rows=${records}
                columns=${[
                    { key: 'work_order_number', label: 'Work Order', render: (r) => html`<span className="nht-mono">${r.work_order_number}</span>` },
                    { key: 'vehicle_plate', label: 'Vehicle' },
                    { key: 'type_display', label: 'Type' },
                    { key: 'scheduled_date', label: 'Scheduled' },
                    { key: 'total_cost', label: 'Total Cost', align: 'right', render: (r) => formatCurrency(r.total_cost) },
                    { key: 'status', label: 'Status', render: (r) => html`<${StatusChip} value=${r.status} />` },
                    {
                        key: 'actions',
                        label: 'Action',
                        align: 'right',
                        render: (r) => r.status !== 'COMPLETED' && html`
                            <${MUI.Button} size="small" color="success" onClick=${() => completeOrder(r.id)}>Mark Complete</${MUI.Button}>
                        `,
                    },
                ]}
            />
        </${MUI.Box}>
    `;
}

export function IncidentsPage({ notify }) {
    const [rows, setRows] = React.useState([]);
    const [loading, setLoading] = React.useState(true);
    const [updateTarget, setUpdateTarget] = React.useState(null);
    const [notes, setNotes] = React.useState('');

    const load = React.useCallback(async () => {
        setLoading(true);
        try {
            const res = await apiFetch('/api/v1/incidents/');
            setRows(extractList(res));
        } catch (err) {
            notify(err.message, 'error');
        } finally {
            setLoading(false);
        }
    }, [notify]);

    React.useEffect(() => { load(); }, [load]);

    const handleResolve = async () => {
        try {
            await apiFetch(`/api/v1/incidents/${updateTarget.id}/add_update/`, {
                method: 'POST',
                body: { status: 'RESOLVED', notes },
            });
            notify('Incident updated & resolved.', 'success');
            setUpdateTarget(null);
            setNotes('');
            load();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    return html`
        <${MUI.Box}>
            <${PageHeader} title="Incidents & Complaints Desk" subtitle="Safety incidents, member inquiries, and investigation tracking." />
            <${ResponsiveDataGrid}
                loading=${loading}
                rows=${rows}
                columns=${[
                    { key: 'ticket_number', label: 'Ticket #', render: (r) => html`<span className="nht-mono">${r.ticket_number}</span>` },
                    { key: 'title', label: 'Subject' },
                    { key: 'severity', label: 'Severity', render: (r) => html`<${StatusChip} value=${r.severity === 'CRITICAL' || r.severity === 'HIGH' ? 'REJECTED' : 'PENDING'} label=${r.severity} />` },
                    { key: 'vehicle_plate', label: 'Vehicle', render: (r) => r.vehicle_plate || '—' },
                    { key: 'status', label: 'Status', render: (r) => html`<${StatusChip} value=${r.status} />` },
                    {
                        key: 'actions',
                        label: 'Action',
                        align: 'right',
                        render: (r) => r.status !== 'RESOLVED' && r.status !== 'CLOSED' && html`
                            <${MUI.Button} size="small" color="success" onClick=${() => setUpdateTarget(r)}>Resolve</${MUI.Button}>
                        `,
                    },
                ]}
            />
            <${ResponsiveDialog}
                open=${Boolean(updateTarget)}
                onClose=${() => setUpdateTarget(null)}
                title=${`Resolve ${updateTarget?.ticket_number || ''}`}
                actions=${html`
                    <${MUI.Button} onClick=${() => setUpdateTarget(null)}>Cancel</${MUI.Button}>
                    <${MUI.Button} variant="contained" color="success" onClick=${handleResolve}>Resolve Ticket</${MUI.Button}>
                `}
            >
                <${MUI.TextField} label="Resolution Notes" fullWidth multiline rows=${3} sx=${{ mt: 1 }} value=${notes} onChange=${(e) => setNotes(e.target.value)} />
            </${ResponsiveDialog}>
        </${MUI.Box}>
    `;
}

export function GovernancePage({ notify }) {
    const [tab, setTab] = React.useState(0);
    const [committees, setCommittees] = React.useState([]);
    const [meetings, setMeetings] = React.useState([]);
    const [resolutions, setResolutions] = React.useState([]);
    const [loading, setLoading] = React.useState(true);

    React.useEffect(() => {
        setLoading(true);
        Promise.all([
            apiFetch('/api/v1/committees/'),
            apiFetch('/api/v1/meetings/'),
            apiFetch('/api/v1/resolutions/'),
        ])
            .then(([c, m, r]) => {
                setCommittees(extractList(c));
                setMeetings(extractList(m));
                setResolutions(extractList(r));
            })
            .catch((err) => notify(err.message, 'error'))
            .finally(() => setLoading(false));
    }, [notify]);

    return html`
        <${MUI.Box}>
            <${PageHeader} title="SACCO Governance" subtitle="Board committees, scheduled meetings, minutes, and passed resolutions." />
            <${MUI.Tabs} value=${tab} onChange=${(_, v) => setTab(v)} sx=${{ mb: 2 }}>
                <${MUI.Tab} label="Committees (${committees.length})" />
                <${MUI.Tab} label="Meetings (${meetings.length})" />
                <${MUI.Tab} label="Resolutions (${resolutions.length})" />
            </${MUI.Tabs}>

            ${tab === 0 && html`
                <${ResponsiveDataGrid}
                    loading=${loading}
                    rows=${committees}
                    columns=${[
                        { key: 'name', label: 'Committee' },
                        { key: 'committee_type', label: 'Type' },
                        { key: 'chairperson_name', label: 'Chairperson' },
                        { key: 'is_active', label: 'Status', render: (r) => html`<${StatusChip} value=${r.is_active ? 'ACTIVE' : 'CLOSED'} />` },
                    ]}
                />
            `}
            ${tab === 1 && html`
                <${ResponsiveDataGrid}
                    loading=${loading}
                    rows=${meetings}
                    columns=${[
                        { key: 'meeting_number', label: 'Meeting #', render: (r) => html`<span className="nht-mono">${r.meeting_number}</span>` },
                        { key: 'committee_name', label: 'Committee' },
                        { key: 'title', label: 'Purpose' },
                        { key: 'scheduled_date', label: 'Date', render: (r) => formatDateTime(r.scheduled_date) },
                        { key: 'status', label: 'Status', render: (r) => html`<${StatusChip} value=${r.status} />` },
                    ]}
                />
            `}
            ${tab === 2 && html`
                <${ResponsiveDataGrid}
                    loading=${loading}
                    rows=${resolutions}
                    columns=${[
                        { key: 'resolution_number', label: 'Resolution #', render: (r) => html`<span className="nht-mono">${r.resolution_number}</span>` },
                        { key: 'title', label: 'Title' },
                        { key: 'votes_for', label: 'For / Against', render: (r) => `${r.votes_for} / ${r.votes_against}` },
                        { key: 'status', label: 'Status', render: (r) => html`<${StatusChip} value=${r.status} />` },
                    ]}
                />
            `}
        </${MUI.Box}>
    `;
}

export function NotificationsPage({ notify }) {
    const [items, setItems] = React.useState([]);
    const [loading, setLoading] = React.useState(true);

    const load = React.useCallback(async () => {
        setLoading(true);
        try {
            const res = await apiFetch('/api/v1/notifications/');
            setItems(extractList(res));
        } catch (err) {
            notify(err.message, 'error');
        } finally {
            setLoading(false);
        }
    }, [notify]);

    React.useEffect(() => { load(); }, [load]);

    const markRead = async (id) => {
        try {
            await apiFetch(`/api/v1/notifications/${id}/mark_read/`, { method: 'POST', body: {} });
            load();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    return html`
        <${MUI.Box}>
            <${PageHeader} title="Notifications & Notices" subtitle="Multi-channel SMS, WhatsApp, Email, and In-App dispatches." />
            <${ResponsiveDataGrid}
                loading=${loading}
                rows=${items}
                columns=${[
                    { key: 'channel', label: 'Channel' },
                    { key: 'title', label: 'Title' },
                    { key: 'message', label: 'Message' },
                    { key: 'status', label: 'Status', render: (r) => html`<${StatusChip} value=${r.status} />` },
                    { key: 'created_at', label: 'Sent', render: (r) => formatDateTime(r.created_at) },
                    {
                        key: 'actions',
                        label: 'Action',
                        align: 'right',
                        render: (r) => r.status !== 'READ' && html`
                            <${MUI.Button} size="small" onClick=${() => markRead(r.id)}>Mark Read</${MUI.Button}>
                        `,
                    },
                ]}
            />
        </${MUI.Box}>
    `;
}
