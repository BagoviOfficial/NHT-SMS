import { React, MUI, html, apiFetch, extractList } from '../api.js';
import { MaterialIcon, PageHeader, ResponsiveDataGrid, ResponsiveDialog, StatusChip } from '../components.js';

export function MembersPage({ notify }) {
    const [rows, setRows] = React.useState([]);
    const [loading, setLoading] = React.useState(true);
    const [search, setSearch] = React.useState('');

    const load = React.useCallback(async () => {
        setLoading(true);
        try {
            const res = await apiFetch(`/api/v1/members/?search=${encodeURIComponent(search)}`);
            setRows(extractList(res));
        } catch (err) {
            notify(err.message, 'error');
        } finally {
            setLoading(false);
        }
    }, [search, notify]);

    React.useEffect(() => { load(); }, [load]);

    const doAction = async (id, act) => {
        try {
            await apiFetch(`/api/v1/members/${id}/${act}/`, { method: 'POST', body: {} });
            notify(`Member ${act} succeeded.`, 'success');
            load();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    return html`
        <${MUI.Box}>
            <${PageHeader} title="SACCO Members Registry" subtitle="Operator onboarding, KYC standing, approvals, and suspensions." />
            <${ResponsiveDataGrid}
                loading=${loading}
                rows=${rows}
                search=${search}
                onSearchChange=${setSearch}
                searchPlaceholder="Search member name, ID, phone..."
                columns=${[
                    { key: 'membership_number', label: 'Member #', render: (r) => html`<span class="nht-mono">${r.membership_number}</span>` },
                    { key: 'full_name', label: 'Full Name' },
                    { key: 'phone_number', label: 'Phone' },
                    { key: 'county', label: 'County' },
                    { key: 'category_display', label: 'Category' },
                    { key: 'status', label: 'Status', render: (r) => html`<${StatusChip} value=${r.status} />` },
                    {
                        key: 'actions',
                        label: 'Actions',
                        align: 'right',
                        render: (r) => html`
                            <${MUI.Stack} direction="row" spacing=${0.5} justifyContent="flex-end">
                                ${r.status === 'PENDING' && html`<${MUI.Button} size="small" color="success" onClick=${() => doAction(r.id, 'approve')}>Approve</${MUI.Button}>`}
                                ${r.status === 'ACTIVE' && html`<${MUI.Button} size="small" color="warning" onClick=${() => doAction(r.id, 'suspend')}>Suspend</${MUI.Button}>`}
                                ${r.status === 'SUSPENDED' && html`<${MUI.Button} size="small" color="primary" onClick=${() => doAction(r.id, 'reinstate')}>Reinstate</${MUI.Button}>`}
                            </${MUI.Stack}>
                        `,
                    },
                ]}
            />
        </${MUI.Box}>
    `;
}

export function VehiclesPage({ notify }) {
    const [rows, setRows] = React.useState([]);
    const [members, setMembers] = React.useState([]);
    const [loading, setLoading] = React.useState(true);
    const [search, setSearch] = React.useState('');
    const [createOpen, setCreateOpen] = React.useState(false);
    const [transferVehicle, setTransferVehicle] = React.useState(null);
    const [newOwner, setNewOwner] = React.useState('');
    const [transferReason, setTransferReason] = React.useState('');
    const [form, setForm] = React.useState({
        registration_number: '', chassis_number: '', engine_number: '',
        make: 'Toyota', model: 'HiAce', year_of_manufacture: 2022,
        category: 'MATATU_14', fuel_type: 'DIESEL', carrying_capacity: 14,
        current_owner: '', status: 'ACTIVE',
    });

    const load = React.useCallback(async () => {
        setLoading(true);
        try {
            const [vRes, mRes] = await Promise.all([
                apiFetch(`/api/v1/vehicles/?search=${encodeURIComponent(search)}`),
                apiFetch('/api/v1/members/'),
            ]);
            setRows(extractList(vRes));
            setMembers(extractList(mRes));
        } catch (err) {
            notify(err.message, 'error');
        } finally {
            setLoading(false);
        }
    }, [search, notify]);

    React.useEffect(() => { load(); }, [load]);

    const handleCreate = async () => {
        try {
            await apiFetch('/api/v1/vehicles/', { method: 'POST', body: form });
            notify('Vehicle registered.', 'success');
            setCreateOpen(false);
            load();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const handleTransfer = async () => {
        try {
            await apiFetch(`/api/v1/vehicles/${transferVehicle.id}/transfer_ownership/`, {
                method: 'POST',
                body: { new_owner: newOwner, reason: transferReason },
            });
            notify('Ownership transferred cleanly.', 'success');
            setTransferVehicle(null);
            load();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    return html`
        <${MUI.Box}>
            <${PageHeader}
                title="Fleet Vehicles & QR Verification"
                subtitle="PSV fleet registry, compliance standing, ownership transfers, and public QR links."
                action=${html`
                    <${MUI.Button} variant="contained" startIcon=${html`<${MaterialIcon} name="add" />`} onClick=${() => setCreateOpen(true)}>
                        Register Vehicle
                    </${MUI.Button}>
                `}
            />
            <${ResponsiveDataGrid}
                loading=${loading}
                rows=${rows}
                search=${search}
                onSearchChange=${setSearch}
                searchPlaceholder="Search plate, make, model..."
                columns=${[
                    { key: 'registration_number', label: 'Plate', render: (r) => html`<strong>${r.registration_number}</strong>` },
                    { key: 'make', label: 'Make & Model', render: (r) => `${r.make} ${r.model} (${r.year_of_manufacture})` },
                    { key: 'category_display', label: 'Category' },
                    { key: 'owner_name', label: 'Owner' },
                    { key: 'compliance_status', label: 'Compliance', render: (r) => html`<${StatusChip} value=${r.compliance_status} />` },
                    { key: 'status', label: 'Status', render: (r) => html`<${StatusChip} value=${r.status} />` },
                    {
                        key: 'actions',
                        label: 'Actions',
                        align: 'right',
                        render: (r) => html`
                            <${MUI.Stack} direction="row" spacing=${0.5} justifyContent="flex-end">
                                <${MUI.Button} size="small" href="/verify/vehicle/${r.qr_token}/" target="_blank">QR Card</${MUI.Button}>
                                <${MUI.Button} size="small" onClick=${() => { setTransferVehicle(r); setNewOwner(''); }}>Transfer</${MUI.Button}>
                            </${MUI.Stack}>
                        `,
                    },
                ]}
            />

            <${ResponsiveDialog}
                open=${createOpen}
                onClose=${() => setCreateOpen(false)}
                title="Register PSV Vehicle"
                actions=${html`
                    <${MUI.Button} onClick=${() => setCreateOpen(false)}>Cancel</${MUI.Button}>
                    <${MUI.Button} variant="contained" onClick=${handleCreate}>Save Vehicle</${MUI.Button}>
                `}
            >
                <${MUI.Stack} spacing=${2} sx=${{ pt: 1 }}>
                    <${MUI.TextField} label="Registration Plate" fullWidth value=${form.registration_number} onChange=${(e) => setForm({ ...form, registration_number: e.target.value })} />
                    <${MUI.TextField} label="Chassis Number" fullWidth value=${form.chassis_number} onChange=${(e) => setForm({ ...form, chassis_number: e.target.value })} />
                    <${MUI.TextField} label="Engine Number" fullWidth value=${form.engine_number} onChange=${(e) => setForm({ ...form, engine_number: e.target.value })} />
                    <${MUI.TextField} select label="Owner Member" fullWidth value=${form.current_owner} onChange=${(e) => setForm({ ...form, current_owner: e.target.value })}>
                        ${members.map((m) => html`<${MUI.MenuItem} key=${m.id} value=${m.id}>${m.full_name} (${m.membership_number})</${MUI.MenuItem}>`)}
                    </${MUI.TextField}>
                    <${MUI.Grid} container spacing=${2}>
                        <${MUI.Grid} item xs=${6}><${MUI.TextField} label="Make" fullWidth value=${form.make} onChange=${(e) => setForm({ ...form, make: e.target.value })} /></${MUI.Grid}>
                        <${MUI.Grid} item xs=${6}><${MUI.TextField} label="Model" fullWidth value=${form.model} onChange=${(e) => setForm({ ...form, model: e.target.value })} /></${MUI.Grid}>
                    </${MUI.Grid}>
                </${MUI.Stack}>
            </${ResponsiveDialog}>

            <${ResponsiveDialog}
                open=${Boolean(transferVehicle)}
                onClose=${() => setTransferVehicle(null)}
                title=${`Transfer Ownership: ${transferVehicle?.registration_number || ''}`}
                actions=${html`
                    <${MUI.Button} onClick=${() => setTransferVehicle(null)}>Cancel</${MUI.Button}>
                    <${MUI.Button} variant="contained" onClick=${handleTransfer}>Authorize Transfer</${MUI.Button}>
                `}
            >
                <${MUI.Stack} spacing=${2} sx=${{ pt: 1 }}>
                    <${MUI.TextField} select label="New Owner" fullWidth value=${newOwner} onChange=${(e) => setNewOwner(e.target.value)}>
                        ${members.map((m) => html`<${MUI.MenuItem} key=${m.id} value=${m.id}>${m.full_name} (${m.membership_number})</${MUI.MenuItem}>`)}
                    </${MUI.TextField}>
                    <${MUI.TextField} label="Transfer Reason" fullWidth multiline rows=${2} value=${transferReason} onChange=${(e) => setTransferReason(e.target.value)} />
                </${MUI.Stack}>
            </${ResponsiveDialog}>
        </${MUI.Box}>
    `;
}

export function DriversPage({ notify }) {
    const [drivers, setDrivers] = React.useState([]);
    const [assignments, setAssignments] = React.useState([]);
    const [vehicles, setVehicles] = React.useState([]);
    const [loading, setLoading] = React.useState(true);
    const [assignOpen, setAssignOpen] = React.useState(false);
    const [assignForm, setAssignForm] = React.useState({ driver: '', vehicle: '' });

    const load = React.useCallback(async () => {
        setLoading(true);
        try {
            const [dRes, aRes, vRes] = await Promise.all([
                apiFetch('/api/v1/drivers/'),
                apiFetch('/api/v1/driver-assignments/'),
                apiFetch('/api/v1/vehicles/'),
            ]);
            setDrivers(extractList(dRes));
            setAssignments(extractList(aRes));
            setVehicles(extractList(vRes));
        } catch (err) {
            notify(err.message, 'error');
        } finally {
            setLoading(false);
        }
    }, [notify]);

    React.useEffect(() => { load(); }, [load]);

    const handleAssign = async () => {
        try {
            await apiFetch('/api/v1/driver-assignments/', { method: 'POST', body: assignForm });
            notify('Driver assigned to vehicle.', 'success');
            setAssignOpen(false);
            load();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    return html`
        <${MUI.Box}>
            <${PageHeader}
                title="PSV Drivers & Vehicle Assignments"
                subtitle="Certified driver credentials, DL/PSV badge expiries, and active vehicle allocations."
                action=${html`
                    <${MUI.Button} variant="contained" startIcon=${html`<${MaterialIcon} name="assignment_ind" />`} onClick=${() => setAssignOpen(true)}>
                        Assign Driver
                    </${MUI.Button}>
                `}
            />
            <${ResponsiveDataGrid}
                loading=${loading}
                rows=${drivers}
                columns=${[
                    { key: 'full_name', label: 'Driver Name', render: (r) => html`<strong>${r.full_name}</strong>` },
                    { key: 'username', label: 'Portal User', render: (r) => r.username || 'Unlinked' },
                    { key: 'driving_license_number', label: 'DL Number' },
                    { key: 'dl_expiry_date', label: 'DL Expiry' },
                    { key: 'psv_badge_number', label: 'PSV Badge' },
                    { key: 'status', label: 'Status', render: (r) => html`<${StatusChip} value=${r.status} />` },
                ]}
            />
            <${MUI.Typography} variant="h6" sx=${{ mt: 3, mb: 1.5 }}>Active Crew Assignments</${MUI.Typography}>
            <${ResponsiveDataGrid}
                loading=${loading}
                rows=${assignments}
                columns=${[
                    { key: 'driver_name', label: 'Driver' },
                    { key: 'vehicle_plate', label: 'Vehicle' },
                    { key: 'is_current', label: 'Active', render: (r) => html`<${StatusChip} value=${r.is_current ? 'ACTIVE' : 'CLOSED'} />` },
                ]}
            />

            <${ResponsiveDialog}
                open=${assignOpen}
                onClose=${() => setAssignOpen(false)}
                title="Assign Driver to Vehicle"
                actions=${html`
                    <${MUI.Button} onClick=${() => setAssignOpen(false)}>Cancel</${MUI.Button}>
                    <${MUI.Button} variant="contained" onClick=${handleAssign}>Assign</${MUI.Button}>
                `}
            >
                <${MUI.Stack} spacing=${2} sx=${{ pt: 1 }}>
                    <${MUI.TextField} select label="Driver" fullWidth value=${assignForm.driver} onChange=${(e) => setAssignForm({ ...assignForm, driver: e.target.value })}>
                        ${drivers.map((d) => html`<${MUI.MenuItem} key=${d.id} value=${d.id}>${d.full_name}</${MUI.MenuItem}>`)}
                    </${MUI.TextField}>
                    <${MUI.TextField} select label="Vehicle" fullWidth value=${assignForm.vehicle} onChange=${(e) => setAssignForm({ ...assignForm, vehicle: e.target.value })}>
                        ${vehicles.map((v) => html`<${MUI.MenuItem} key=${v.id} value=${v.id}>${v.registration_number}</${MUI.MenuItem}>`)}
                    </${MUI.TextField}>
                </${MUI.Stack}>
            </${ResponsiveDialog}>
        </${MUI.Box}>
    `;
}

export function RoutesPage({ notify }) {
    const [routes, setRoutes] = React.useState([]);
    const [loading, setLoading] = React.useState(true);

    React.useEffect(() => {
        apiFetch('/api/v1/routes/')
            .then((res) => setRoutes(extractList(res)))
            .catch((err) => notify(err.message, 'error'))
            .finally(() => setLoading(false));
    }, [notify]);

    return html`
        <${MUI.Box}>
            <${PageHeader} title="Authorized Transit Routes" subtitle="NTSA corridor definitions, stage stops, and active fleet counts." />
            <${ResponsiveDataGrid}
                loading=${loading}
                rows=${routes}
                columns=${[
                    { key: 'route_code', label: 'Code', render: (r) => html`<strong>${r.route_code}</strong>` },
                    { key: 'name', label: 'Route Name' },
                    { key: 'origin', label: 'Origin' },
                    { key: 'destination', label: 'Destination' },
                    { key: 'distance_km', label: 'Distance (km)' },
                    { key: 'active_vehicle_count', label: 'Vehicles' },
                    { key: 'is_active', label: 'Status', render: (r) => html`<${StatusChip} value=${r.is_active ? 'ACTIVE' : 'CLOSED'} />` },
                ]}
            />
        </${MUI.Box}>
    `;
}
