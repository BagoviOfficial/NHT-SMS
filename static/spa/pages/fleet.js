import { React, MUI, html, apiFetch, extractList } from '../api.js';
import { MaterialIcon, PageHeader, ResponsiveDataGrid, ResponsiveDialog, StatusChip } from '../components.js';

export function MembersPage({ notify }) {
    const [rows, setRows] = React.useState([]);
    const [loading, setLoading] = React.useState(true);
    const [search, setSearch] = React.useState('');
    const [statusFilter, setStatusFilter] = React.useState('');
    const [createOpen, setCreateOpen] = React.useState(false);
    const [editTarget, setEditTarget] = React.useState(null);
    const [form, setForm] = React.useState({
        first_name: '',
        middle_name: '',
        last_name: '',
        national_id: '',
        phone_number: '',
        email: '',
        postal_address: '',
        county: 'Isiolo',
        category: 'INDIVIDUAL',
        next_of_kin_name: '',
        next_of_kin_relation: 'Spouse',
        next_of_kin_phone: '',
    });

    const load = React.useCallback(async () => {
        setLoading(true);
        try {
            const qs = new URLSearchParams();
            if (search) qs.set('search', search);
            if (statusFilter) qs.set('status', statusFilter);
            const res = await apiFetch(`/api/v1/members/?${qs.toString()}`);
            setRows(extractList(res));
        } catch (err) {
            notify(err.message, 'error');
        } finally {
            setLoading(false);
        }
    }, [search, statusFilter, notify]);

    React.useEffect(() => { load(); }, [load]);

    const handleCreate = async () => {
        try {
            await apiFetch('/api/v1/members/', { method: 'POST', body: form });
            notify('Member registered with atomic membership number.', 'success');
            setCreateOpen(false);
            setForm({
                first_name: '', middle_name: '', last_name: '', national_id: '', phone_number: '',
                email: '', postal_address: '', county: 'Isiolo', category: 'INDIVIDUAL',
                next_of_kin_name: '', next_of_kin_relation: 'Spouse', next_of_kin_phone: '',
            });
            load();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const handleSaveEdit = async () => {
        try {
            await apiFetch(`/api/v1/members/${editTarget.id}/`, {
                method: 'PATCH',
                body: {
                    first_name: editTarget.first_name,
                    middle_name: editTarget.middle_name,
                    last_name: editTarget.last_name,
                    phone_number: editTarget.phone_number,
                    email: editTarget.email,
                    county: editTarget.county,
                    category: editTarget.category,
                    postal_address: editTarget.postal_address,
                    next_of_kin_name: editTarget.next_of_kin_name,
                    next_of_kin_relation: editTarget.next_of_kin_relation,
                    next_of_kin_phone: editTarget.next_of_kin_phone,
                },
            });
            notify('Member profile updated.', 'success');
            setEditTarget(null);
            load();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

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
            <${PageHeader}
                title="SACCO Members Registry"
                subtitle="Operator onboarding, KYC profiles, approvals, suspensions, and branded membership certificates."
                action=${html`
                    <${MUI.Button} variant="contained" startIcon=${html`<${MaterialIcon} name="person_add" />`} onClick=${() => setCreateOpen(true)}>
                        Register Member
                    </${MUI.Button}>
                `}
            />
            <${ResponsiveDataGrid}
                loading=${loading}
                rows=${rows}
                search=${search}
                onSearchChange=${setSearch}
                searchPlaceholder="Search member name, ID, phone, #..."
                toolbarExtra=${html`
                    <${MUI.TextField}
                        select
                        size="small"
                        label="Status"
                        value=${statusFilter}
                        onChange=${(e) => setStatusFilter(e.target.value)}
                        sx=${{ minWidth: 150 }}
                    >
                        <${MUI.MenuItem} value="">All Statuses</${MUI.MenuItem}>
                        <${MUI.MenuItem} value="PENDING">Pending</${MUI.MenuItem}>
                        <${MUI.MenuItem} value="ACTIVE">Active</${MUI.MenuItem}>
                        <${MUI.MenuItem} value="SUSPENDED">Suspended</${MUI.MenuItem}>
                    </${MUI.TextField}>
                `}
                columns=${[
                    { key: 'membership_number', label: 'Member #', render: (r) => html`<span class="nht-mono">${r.membership_number}</span>` },
                    { key: 'full_name', label: 'Full Name', render: (r) => html`<strong>${r.full_name}</strong>` },
                    { key: 'phone_number', label: 'Phone' },
                    { key: 'county', label: 'County' },
                    { key: 'category_display', label: 'Category' },
                    { key: 'status', label: 'Status', render: (r) => html`<${StatusChip} value=${r.status} />` },
                    {
                        key: 'actions',
                        label: 'Actions',
                        align: 'right',
                        render: (r) => html`
                            <${MUI.Stack} direction="row" spacing=${0.5} justifyContent="flex-end" flexWrap="wrap">
                                <${MUI.Button} size="small" onClick=${() => setEditTarget({ ...r })}>Edit</${MUI.Button}>
                                <${MUI.Button} size="small" href="/api/v1/members/${r.id}/certificate_pdf/" target="_blank">Cert PDF</${MUI.Button}>
                                ${r.status === 'PENDING' && html`<${MUI.Button} size="small" color="success" onClick=${() => doAction(r.id, 'approve')}>Approve</${MUI.Button}>`}
                                ${r.status === 'ACTIVE' && html`<${MUI.Button} size="small" color="warning" onClick=${() => doAction(r.id, 'suspend')}>Suspend</${MUI.Button}>`}
                                ${r.status === 'SUSPENDED' && html`<${MUI.Button} size="small" color="primary" onClick=${() => doAction(r.id, 'reinstate')}>Reinstate</${MUI.Button}>`}
                            </${MUI.Stack}>
                        `,
                    },
                ]}
            />

            <${ResponsiveDialog}
                open=${createOpen}
                onClose=${() => setCreateOpen(false)}
                title="Register New SACCO Member"
                actions=${html`
                    <${MUI.Button} onClick=${() => setCreateOpen(false)}>Cancel</${MUI.Button}>
                    <${MUI.Button} variant="contained" onClick=${handleCreate}>Register Member</${MUI.Button}>
                `}
            >
                <${MUI.Stack} spacing=${2} sx=${{ pt: 1 }}>
                    <${MUI.Grid} container spacing=${2}>
                        <${MUI.Grid} item xs=${12} sm=${4}><${MUI.TextField} label="First Name" fullWidth required value=${form.first_name} onChange=${(e) => setForm({ ...form, first_name: e.target.value })} /></${MUI.Grid}>
                        <${MUI.Grid} item xs=${12} sm=${4}><${MUI.TextField} label="Middle Name" fullWidth value=${form.middle_name} onChange=${(e) => setForm({ ...form, middle_name: e.target.value })} /></${MUI.Grid}>
                        <${MUI.Grid} item xs=${12} sm=${4}><${MUI.TextField} label="Last Name" fullWidth required value=${form.last_name} onChange=${(e) => setForm({ ...form, last_name: e.target.value })} /></${MUI.Grid}>
                    </${MUI.Grid}>
                    <${MUI.Grid} container spacing=${2}>
                        <${MUI.Grid} item xs=${12} sm=${6}><${MUI.TextField} label="National ID" fullWidth required value=${form.national_id} onChange=${(e) => setForm({ ...form, national_id: e.target.value })} /></${MUI.Grid}>
                        <${MUI.Grid} item xs=${12} sm=${6}><${MUI.TextField} label="Phone (+2547...)" fullWidth required value=${form.phone_number} onChange=${(e) => setForm({ ...form, phone_number: e.target.value })} /></${MUI.Grid}>
                    </${MUI.Grid}>
                    <${MUI.TextField} label="Email" type="email" fullWidth required value=${form.email} onChange=${(e) => setForm({ ...form, email: e.target.value })} />
                    <${MUI.Grid} container spacing=${2}>
                        <${MUI.Grid} item xs=${12} sm=${6}><${MUI.TextField} label="County" fullWidth value=${form.county} onChange=${(e) => setForm({ ...form, county: e.target.value })} /></${MUI.Grid}>
                        <${MUI.Grid} item xs=${12} sm=${6}>
                            <${MUI.TextField} select label="Category" fullWidth value=${form.category} onChange=${(e) => setForm({ ...form, category: e.target.value })}>
                                <${MUI.MenuItem} value="INDIVIDUAL">Individual Operator</${MUI.MenuItem}>
                                <${MUI.MenuItem} value="FLEET_OWNER">Fleet Owner</${MUI.MenuItem}>
                                <${MUI.MenuItem} value="CORPORATE">Corporate Operator</${MUI.MenuItem}>
                            </${MUI.TextField}>
                        </${MUI.Grid}>
                    </${MUI.Grid}>
                    <${MUI.Grid} container spacing=${2}>
                        <${MUI.Grid} item xs=${12} sm=${4}><${MUI.TextField} label="Next of Kin Name" fullWidth required value=${form.next_of_kin_name} onChange=${(e) => setForm({ ...form, next_of_kin_name: e.target.value })} /></${MUI.Grid}>
                        <${MUI.Grid} item xs=${12} sm=${4}><${MUI.TextField} label="Relationship" fullWidth required value=${form.next_of_kin_relation} onChange=${(e) => setForm({ ...form, next_of_kin_relation: e.target.value })} /></${MUI.Grid}>
                        <${MUI.Grid} item xs=${12} sm=${4}><${MUI.TextField} label="Kin Phone" fullWidth required value=${form.next_of_kin_phone} onChange=${(e) => setForm({ ...form, next_of_kin_phone: e.target.value })} /></${MUI.Grid}>
                    </${MUI.Grid}>
                </${MUI.Stack}>
            </${ResponsiveDialog}>

            <${ResponsiveDialog}
                open=${Boolean(editTarget)}
                onClose=${() => setEditTarget(null)}
                title=${`Edit Member: ${editTarget?.membership_number || ''}`}
                actions=${html`
                    <${MUI.Button} onClick=${() => setEditTarget(null)}>Cancel</${MUI.Button}>
                    <${MUI.Button} variant="contained" onClick=${handleSaveEdit}>Save Changes</${MUI.Button}>
                `}
            >
                ${editTarget && html`
                    <${MUI.Stack} spacing=${2} sx=${{ pt: 1 }}>
                        <${MUI.Grid} container spacing=${2}>
                            <${MUI.Grid} item xs=${6}><${MUI.TextField} label="First Name" fullWidth value=${editTarget.first_name || ''} onChange=${(e) => setEditTarget({ ...editTarget, first_name: e.target.value })} /></${MUI.Grid}>
                            <${MUI.Grid} item xs=${6}><${MUI.TextField} label="Last Name" fullWidth value=${editTarget.last_name || ''} onChange=${(e) => setEditTarget({ ...editTarget, last_name: e.target.value })} /></${MUI.Grid}>
                        </${MUI.Grid}>
                        <${MUI.TextField} label="Phone Number" fullWidth value=${editTarget.phone_number || ''} onChange=${(e) => setEditTarget({ ...editTarget, phone_number: e.target.value })} />
                        <${MUI.TextField} label="Email" fullWidth value=${editTarget.email || ''} onChange=${(e) => setEditTarget({ ...editTarget, email: e.target.value })} />
                        <${MUI.TextField} label="County" fullWidth value=${editTarget.county || ''} onChange=${(e) => setEditTarget({ ...editTarget, county: e.target.value })} />
                        <${MUI.TextField} label="Next of Kin Name" fullWidth value=${editTarget.next_of_kin_name || ''} onChange=${(e) => setEditTarget({ ...editTarget, next_of_kin_name: e.target.value })} />
                    </${MUI.Stack}>
                `}
            </${ResponsiveDialog}>
        </${MUI.Box}>
    `;
}

export function VehiclesPage({ notify, onNavigate }) {
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

    const handleQuickIssueCard = async (vehicle) => {
        try {
            const card = await apiFetch('/api/v1/compliance-cards/', {
                method: 'POST',
                body: { vehicle: vehicle.id },
            });
            notify(`Compliance Card ${card.certificate_number} issued for ${vehicle.registration_number}.`, 'success');
            if (onNavigate) onNavigate('compliance-cards');
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    return html`
        <${MUI.Box}>
            <${PageHeader}
                title="Fleet Vehicles & Compliance Cards"
                subtitle="PSV fleet registry, compliance standing, ownership transfers, and compliance card issuance."
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
                                <${MUI.Button} size="small" color="success" onClick=${() => handleQuickIssueCard(r)}>Issue QR Card</${MUI.Button}>
                                <${MUI.Button} size="small" href="/verify/vehicle/${r.qr_token}/" target="_blank">Verify QR</${MUI.Button}>
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

    const handleRelieve = async (id) => {
        try {
            await apiFetch(`/api/v1/driver-assignments/${id}/relieve/`, { method: 'POST', body: {} });
            notify('Driver assignment relieved.', 'info');
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
                    {
                        key: 'actions',
                        label: 'Action',
                        align: 'right',
                        render: (r) => r.is_current && html`<${MUI.Button} size="small" color="warning" onClick=${() => handleRelieve(r.id)}>Relieve</${MUI.Button}>`,
                    },
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
    const [allocations, setAllocations] = React.useState([]);
    const [vehicles, setVehicles] = React.useState([]);
    const [loading, setLoading] = React.useState(true);
    const [createOpen, setCreateOpen] = React.useState(false);
    const [allocOpen, setAllocOpen] = React.useState(false);
    const [routeForm, setRouteForm] = React.useState({ route_code: '', name: '', origin: '', destination: '', distance_km: '120', is_active: true });
    const [allocForm, setAllocForm] = React.useState({ vehicle: '', route: '', road_service_license: '' });

    const load = React.useCallback(async () => {
        setLoading(true);
        try {
            const [rRes, aRes, vRes] = await Promise.all([
                apiFetch('/api/v1/routes/'),
                apiFetch('/api/v1/route-assignments/'),
                apiFetch('/api/v1/vehicles/'),
            ]);
            setRoutes(extractList(rRes));
            setAllocations(extractList(aRes));
            setVehicles(extractList(vRes));
        } catch (err) {
            notify(err.message, 'error');
        } finally {
            setLoading(false);
        }
    }, [notify]);

    React.useEffect(() => { load(); }, [load]);

    const handleCreateRoute = async () => {
        try {
            await apiFetch('/api/v1/routes/', { method: 'POST', body: routeForm });
            notify('Transit route created.', 'success');
            setCreateOpen(false);
            load();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const handleAlloc = async () => {
        try {
            await apiFetch('/api/v1/route-assignments/', { method: 'POST', body: { ...allocForm, is_active: true } });
            notify('Vehicle allocated to route.', 'success');
            setAllocOpen(false);
            load();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    return html`
        <${MUI.Box}>
            <${PageHeader}
                title="Authorized Transit Routes & Allocations"
                subtitle="NTSA corridor definitions, stage stops, and active vehicle route allocations."
                action=${html`
                    <${MUI.Stack} direction="row" spacing=${1}>
                        <${MUI.Button} variant="outlined" onClick=${() => setAllocOpen(true)}>Allocate Vehicle</${MUI.Button}>
                        <${MUI.Button} variant="contained" startIcon=${html`<${MaterialIcon} name="add_road" />`} onClick=${() => setCreateOpen(true)}>New Route</${MUI.Button}>
                    </${MUI.Stack}>
                `}
            />
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

            <${MUI.Typography} variant="h6" sx=${{ mt: 3, mb: 1.5 }}>Active Vehicle Route Allocations</${MUI.Typography}>
            <${ResponsiveDataGrid}
                loading=${loading}
                rows=${allocations}
                columns=${[
                    { key: 'vehicle_plate', label: 'Vehicle', render: (r) => html`<strong>${r.vehicle_plate}</strong>` },
                    { key: 'route_code', label: 'Route Code' },
                    { key: 'route_name', label: 'Route Name' },
                    { key: 'road_service_license', label: 'RSL #' },
                    { key: 'assigned_date', label: 'Assigned Date' },
                    { key: 'is_active', label: 'Status', render: (r) => html`<${StatusChip} value=${r.is_active ? 'ACTIVE' : 'CLOSED'} />` },
                ]}
            />

            <${ResponsiveDialog}
                open=${createOpen}
                onClose=${() => setCreateOpen(false)}
                title="Create Transit Route"
                actions=${html`
                    <${MUI.Button} onClick=${() => setCreateOpen(false)}>Cancel</${MUI.Button}>
                    <${MUI.Button} variant="contained" onClick=${handleCreateRoute}>Create Route</${MUI.Button}>
                `}
            >
                <${MUI.Stack} spacing=${2} sx=${{ pt: 1 }}>
                    <${MUI.TextField} label="Route Code" fullWidth value=${routeForm.route_code} onChange=${(e) => setRouteForm({ ...routeForm, route_code: e.target.value })} />
                    <${MUI.TextField} label="Route Name" fullWidth value=${routeForm.name} onChange=${(e) => setRouteForm({ ...routeForm, name: e.target.value })} />
                    <${MUI.TextField} label="Origin" fullWidth value=${routeForm.origin} onChange=${(e) => setRouteForm({ ...routeForm, origin: e.target.value })} />
                    <${MUI.TextField} label="Destination" fullWidth value=${routeForm.destination} onChange=${(e) => setRouteForm({ ...routeForm, destination: e.target.value })} />
                    <${MUI.TextField} label="Distance (km)" type="number" fullWidth value=${routeForm.distance_km} onChange=${(e) => setRouteForm({ ...routeForm, distance_km: e.target.value })} />
                </${MUI.Stack}>
            </${ResponsiveDialog}>

            <${ResponsiveDialog}
                open=${allocOpen}
                onClose=${() => setAllocOpen(false)}
                title="Allocate Vehicle to Route"
                actions=${html`
                    <${MUI.Button} onClick=${() => setAllocOpen(false)}>Cancel</${MUI.Button}>
                    <${MUI.Button} variant="contained" onClick=${handleAlloc}>Allocate</${MUI.Button}>
                `}
            >
                <${MUI.Stack} spacing=${2} sx=${{ pt: 1 }}>
                    <${MUI.TextField} select label="Vehicle" fullWidth value=${allocForm.vehicle} onChange=${(e) => setAllocForm({ ...allocForm, vehicle: e.target.value })}>
                        ${vehicles.map((v) => html`<${MUI.MenuItem} key=${v.id} value=${v.id}>${v.registration_number}</${MUI.MenuItem}>`)}
                    </${MUI.TextField}>
                    <${MUI.TextField} select label="Route" fullWidth value=${allocForm.route} onChange=${(e) => setAllocForm({ ...allocForm, route: e.target.value })}>
                        ${routes.map((rt) => html`<${MUI.MenuItem} key=${rt.id} value=${rt.id}>${rt.route_code}: ${rt.name}</${MUI.MenuItem}>`)}
                    </${MUI.TextField}>
                    <${MUI.TextField} label="Road Service License (RSL)" fullWidth value=${allocForm.road_service_license} onChange=${(e) => setAllocForm({ ...allocForm, road_service_license: e.target.value })} />
                </${MUI.Stack}>
            </${ResponsiveDialog}>
        </${MUI.Box}>
    `;
}
