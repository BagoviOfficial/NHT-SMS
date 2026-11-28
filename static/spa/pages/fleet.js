import { React, MUI, html, apiFetch, extractList } from '../api.js';
import { MaterialIcon, PageHeader, ResponsiveDataGrid, ResponsiveDialog, StatusChip } from '../components.js';

export const DEFAULT_COMMERCIAL_CATEGORIES = [
    { value: 'HEAVY_TRUCK', label: 'Heavy Commercial Truck (15+ Tonnes)' },
    { value: 'PRIME_MOVER', label: 'Prime Mover / Tractor Head' },
    { value: 'SEMI_TRAILER', label: 'Semi-Trailer / Flatbed / Box Trailer' },
    { value: 'MEDIUM_TRUCK', label: 'Medium Commercial Truck (8–15 Tonnes)' },
    { value: 'LIGHT_TRUCK', label: 'Light Commercial Truck (3–7 Tonnes)' },
    { value: 'TANKER', label: 'Fuel / Bulk Liquid Tanker' },
    { value: 'TIPPER', label: 'Tipper / Dump Truck' },
    { value: 'PARCEL_VAN', label: 'Commercial Delivery / Courier Van' },
];

export const DEFAULT_FUEL_TYPES = [
    { value: 'DIESEL', label: 'Diesel' },
    { value: 'PETROL', label: 'Petrol' },
    { value: 'NONE', label: 'N/A (Non-Motorized Trailer)' },
    { value: 'ELECTRIC', label: 'Electric' },
    { value: 'HYBRID', label: 'Hybrid' },
];

const CURRENT_YEAR = new Date().getFullYear();

const blankMemberForm = () => ({
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
    portal_username: '',
    portal_password: '',
    must_change_password: true,
});

export const blankVehicleEntry = () => ({
    registration_number: '',
    chassis_number: '',
    engine_number: '',
    make: '',
    model: '',
    year_of_manufacture: CURRENT_YEAR,
    category: 'HEAVY_TRUCK',
    fuel_type: 'DIESEL',
    carrying_capacity: 15,
    color: 'White with Sacco Stripes',
    status: 'ACTIVE',
});

export function VehicleFieldsSection({ value, onChange, categories, fuelTypes }) {
    const isTrailer = value.category === 'SEMI_TRAILER' || value.fuel_type === 'NONE';
    const handleCategoryChange = (newCat) => {
        const nextFuel = newCat === 'SEMI_TRAILER' ? 'NONE' : (value.fuel_type === 'NONE' ? 'DIESEL' : value.fuel_type);
        onChange({ ...value, category: newCat, fuel_type: nextFuel });
    };

    return html`
        <${MUI.Grid} container spacing=${1.5}>
            <${MUI.Grid} size=${{ xs: 12, sm: 6 }}>
                <${MUI.TextField}
                    label="Registration Plate *"
                    placeholder="e.g. KDA 123A or ZA 1234"
                    fullWidth
                    size="small"
                    value=${value.registration_number}
                    onChange=${(e) => onChange({ ...value, registration_number: e.target.value })}
                />
            </${MUI.Grid}>
            <${MUI.Grid} size=${{ xs: 12, sm: 6 }}>
                <${MUI.TextField}
                    select
                    label="Vehicle Category (Truck / Trailer) *"
                    fullWidth
                    size="small"
                    value=${value.category}
                    onChange=${(e) => handleCategoryChange(e.target.value)}
                >
                    ${categories.map((c) => html`<${MUI.MenuItem} key=${c.value} value=${c.value}>${c.label}</${MUI.MenuItem}>`)}
                </${MUI.TextField}>
            </${MUI.Grid}>
            <${MUI.Grid} size=${{ xs: 12, sm: 6 }}>
                <${MUI.TextField}
                    label="Make *"
                    placeholder="e.g. Isuzu, Mercedes-Benz, Scania, Sinotruk"
                    fullWidth
                    size="small"
                    value=${value.make}
                    onChange=${(e) => onChange({ ...value, make: e.target.value })}
                />
            </${MUI.Grid}>
            <${MUI.Grid} size=${{ xs: 12, sm: 6 }}>
                <${MUI.TextField}
                    label="Model *"
                    placeholder="e.g. Actros, FH16, NQR, 40ft Flatbed"
                    fullWidth
                    size="small"
                    value=${value.model}
                    onChange=${(e) => onChange({ ...value, model: e.target.value })}
                />
            </${MUI.Grid}>
            <${MUI.Grid} size=${{ xs: 12, sm: 4 }}>
                <${MUI.TextField}
                    label="Year of Manufacture *"
                    type="number"
                    fullWidth
                    size="small"
                    value=${value.year_of_manufacture}
                    onChange=${(e) => onChange({ ...value, year_of_manufacture: Number(e.target.value || CURRENT_YEAR) })}
                />
            </${MUI.Grid}>
            <${MUI.Grid} size=${{ xs: 12, sm: 4 }}>
                <${MUI.TextField}
                    label="Payload Capacity (Tonnes) *"
                    type="number"
                    fullWidth
                    size="small"
                    value=${value.carrying_capacity}
                    onChange=${(e) => onChange({ ...value, carrying_capacity: Number(e.target.value || 15) })}
                />
            </${MUI.Grid}>
            <${MUI.Grid} size=${{ xs: 12, sm: 4 }}>
                <${MUI.TextField}
                    select
                    label="Fuel Type *"
                    fullWidth
                    size="small"
                    value=${value.fuel_type}
                    onChange=${(e) => onChange({ ...value, fuel_type: e.target.value })}
                >
                    ${fuelTypes.map((f) => html`<${MUI.MenuItem} key=${f.value} value=${f.value}>${f.label}</${MUI.MenuItem}>`)}
                </${MUI.TextField}>
            </${MUI.Grid}>
            <${MUI.Grid} size=${{ xs: 12, sm: 6 }}>
                <${MUI.TextField}
                    label="Chassis Number *"
                    fullWidth
                    size="small"
                    value=${value.chassis_number}
                    onChange=${(e) => onChange({ ...value, chassis_number: e.target.value })}
                />
            </${MUI.Grid}>
            <${MUI.Grid} size=${{ xs: 12, sm: 6 }}>
                <${MUI.TextField}
                    label=${isTrailer ? 'Engine Number (Optional for trailers)' : 'Engine Number *'}
                    fullWidth
                    size="small"
                    value=${value.engine_number}
                    onChange=${(e) => onChange({ ...value, engine_number: e.target.value })}
                />
            </${MUI.Grid}>
            <${MUI.Grid} size=${{ xs: 12 }}>
                <${MUI.TextField}
                    label="Color / Livery"
                    fullWidth
                    size="small"
                    value=${value.color}
                    onChange=${(e) => onChange({ ...value, color: e.target.value })}
                />
            </${MUI.Grid}>
        </${MUI.Grid}>
    `;
}

export function MembersPage({ notify }) {
    const [rows, setRows] = React.useState([]);
    const [categories, setCategories] = React.useState(DEFAULT_COMMERCIAL_CATEGORIES);
    const [fuelTypes, setFuelTypes] = React.useState(DEFAULT_FUEL_TYPES);
    const [loading, setLoading] = React.useState(true);
    const [search, setSearch] = React.useState('');
    const [statusFilter, setStatusFilter] = React.useState('');
    const [createOpen, setCreateOpen] = React.useState(false);
    const [editTarget, setEditTarget] = React.useState(null);
    const [portalTarget, setPortalTarget] = React.useState(null);
    const [portalResetForm, setPortalResetForm] = React.useState({ password: '', must_change_password: true });
    const [credsModal, setCredsModal] = React.useState(null);
    const [form, setForm] = React.useState(blankMemberForm);
    const [memberVehicles, setMemberVehicles] = React.useState([blankVehicleEntry()]);

    const load = React.useCallback(async () => {
        setLoading(true);
        try {
            const qs = new URLSearchParams();
            if (search) qs.set('search', search);
            if (statusFilter) qs.set('status', statusFilter);
            const [mRes, catRes] = await Promise.all([
                apiFetch(`/api/v1/members/?${qs.toString()}`),
                apiFetch('/api/v1/vehicles/categories/').catch(() => null),
            ]);
            setRows(extractList(mRes));
            if (catRes?.categories?.length) setCategories(catRes.categories);
            if (catRes?.fuel_types?.length) setFuelTypes(catRes.fuel_types);
        } catch (err) {
            notify(err.message, 'error');
        } finally {
            setLoading(false);
        }
    }, [search, statusFilter, notify]);

    React.useEffect(() => { load(); }, [load]);

    const handleCreate = async () => {
        if (!form.first_name.trim() || !form.last_name.trim() || !form.national_id.trim() || !form.phone_number.trim() || !form.email.trim() || !form.next_of_kin_name.trim() || !form.next_of_kin_phone.trim()) {
            notify('Please complete all required member KYC and next-of-kin fields.', 'warning');
            return;
        }
        if (!memberVehicles.length) {
            notify('Please include at least one commercial truck or trailer for the member.', 'warning');
            return;
        }
        for (let i = 0; i < memberVehicles.length; i += 1) {
            const v = memberVehicles[i];
            const isTrailer = v.category === 'SEMI_TRAILER' || v.fuel_type === 'NONE';
            if (!v.registration_number.trim() || !v.chassis_number.trim() || !v.make.trim() || !v.model.trim() || (!isTrailer && !v.engine_number.trim())) {
                notify(`Please complete required details for Truck / Trailer #${i + 1}.`, 'warning');
                return;
            }
        }
        try {
            const payload = {
                ...form,
                vehicles: memberVehicles.map((v) => ({
                    ...v,
                    engine_number: v.engine_number?.trim() || null,
                })),
            };
            const created = await apiFetch('/api/v1/members/', { method: 'POST', body: payload });
            notify(`Member ${created.membership_number} registered with portal account & ${created.vehicle_count || memberVehicles.length} vehicle(s).`, 'success');
            setCreateOpen(false);
            setForm(blankMemberForm());
            setMemberVehicles([blankVehicleEntry()]);
            if (created.provisioned_portal_credentials) {
                setCredsModal({
                    title: 'Member Onboarded & Portal Account Created',
                    membership_number: created.membership_number,
                    full_name: created.full_name,
                    credentials: created.provisioned_portal_credentials,
                    vehicles: created.vehicles || [],
                });
            }
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

    const handleProvisionPortal = async () => {
        if (!portalTarget) return;
        try {
            const res = await apiFetch(`/api/v1/members/${portalTarget.id}/provision_portal_account/`, {
                method: 'POST',
                body: portalResetForm,
            });
            notify(`Portal account @${res.username} activated/reset.`, 'success');
            setCredsModal({
                title: 'Member Portal Credentials Provisioned',
                membership_number: portalTarget.membership_number,
                full_name: portalTarget.full_name,
                credentials: res,
                vehicles: portalTarget.vehicles || [],
            });
            setPortalTarget(null);
            setPortalResetForm({ password: '', must_change_password: true });
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
                subtitle="Commercial operator onboarding with trucks/trailers, member portal accounts, approvals, and certificates."
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
                    { key: 'membership_number', label: 'Member #', render: (r) => html`<span className="nht-mono">${r.membership_number}</span>` },
                    { key: 'full_name', label: 'Full Name', render: (r) => html`<strong>${r.full_name}</strong>` },
                    { key: 'phone_number', label: 'Phone' },
                    {
                        key: 'username',
                        label: 'Portal Account',
                        render: (r) => html`
                            <${MUI.Stack} direction="row" spacing=${0.5} alignItems="center">
                                <span className="nht-mono">@${r.username || '—'}</span>
                                <${MUI.Chip}
                                    size="small"
                                    label=${r.has_portal_account ? 'Active' : 'Setup Needed'}
                                    color=${r.has_portal_account ? 'success' : 'warning'}
                                    variant="outlined"
                                />
                            </${MUI.Stack}>
                        `,
                    },
                    {
                        key: 'vehicles',
                        label: 'Trucks & Trailers',
                        render: (r) => {
                            const list = r.vehicles || [];
                            if (!list.length) return html`<${MUI.Typography} variant="caption" color="text.secondary">None</${MUI.Typography}>`;
                            return html`
                                <${MUI.Stack} direction="row" spacing=${0.5} flexWrap="wrap" useFlexGap>
                                    ${list.map((v) => html`<${MUI.Chip} key=${v.id} size="small" label=${v.registration_number} variant="outlined" color="primary" />`)}
                                </${MUI.Stack}>
                            `;
                        },
                    },
                    { key: 'category_display', label: 'Category' },
                    { key: 'status', label: 'Status', render: (r) => html`<${StatusChip} value=${r.status} />` },
                    {
                        key: 'actions',
                        label: 'Actions',
                        align: 'right',
                        render: (r) => html`
                            <${MUI.Stack} direction="row" spacing=${0.5} justifyContent="flex-end" flexWrap="wrap">
                                <${MUI.Button} size="small" onClick=${() => setEditTarget({ ...r })}>Edit</${MUI.Button}>
                                <${MUI.Button} size="small" color="info" onClick=${() => { setPortalTarget(r); setPortalResetForm({ password: '', must_change_password: true }); }}>
                                    Portal Account
                                </${MUI.Button}>
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
                title="Register New SACCO Member, Portal Account & Vehicles"
                maxWidth="md"
                actions=${html`
                    <${MUI.Button} onClick=${() => setCreateOpen(false)}>Cancel</${MUI.Button}>
                    <${MUI.Button} variant="contained" onClick=${handleCreate}>Register Member & Vehicles</${MUI.Button}>
                `}
            >
                <${MUI.Stack} spacing=${2.5} sx=${{ pt: 1 }}>
                    <${MUI.Typography} variant="subtitle2" sx=${{ fontWeight: 700, color: 'primary.main' }}>
                        1. Member Personal & KYC Details
                    </${MUI.Typography}>
                    <${MUI.Grid} container spacing=${2}>
                        <${MUI.Grid} size=${{ xs: 12, sm: 4 }}><${MUI.TextField} label="First Name" fullWidth required value=${form.first_name} onChange=${(e) => setForm({ ...form, first_name: e.target.value })} /></${MUI.Grid}>
                        <${MUI.Grid} size=${{ xs: 12, sm: 4 }}><${MUI.TextField} label="Middle Name" fullWidth value=${form.middle_name} onChange=${(e) => setForm({ ...form, middle_name: e.target.value })} /></${MUI.Grid}>
                        <${MUI.Grid} size=${{ xs: 12, sm: 4 }}><${MUI.TextField} label="Last Name" fullWidth required value=${form.last_name} onChange=${(e) => setForm({ ...form, last_name: e.target.value })} /></${MUI.Grid}>
                    </${MUI.Grid}>
                    <${MUI.Grid} container spacing=${2}>
                        <${MUI.Grid} size=${{ xs: 12, sm: 6 }}><${MUI.TextField} label="National ID / Passport" fullWidth required value=${form.national_id} onChange=${(e) => setForm({ ...form, national_id: e.target.value })} /></${MUI.Grid}>
                        <${MUI.Grid} size=${{ xs: 12, sm: 6 }}><${MUI.TextField} label="Phone (+2547...)" fullWidth required value=${form.phone_number} onChange=${(e) => setForm({ ...form, phone_number: e.target.value })} /></${MUI.Grid}>
                    </${MUI.Grid}>
                    <${MUI.Grid} container spacing=${2}>
                        <${MUI.Grid} size=${{ xs: 12, sm: 6 }}><${MUI.TextField} label="Email" type="email" fullWidth required value=${form.email} onChange=${(e) => setForm({ ...form, email: e.target.value })} /></${MUI.Grid}>
                        <${MUI.Grid} size=${{ xs: 12, sm: 6 }}><${MUI.TextField} label="Postal Address" fullWidth value=${form.postal_address} onChange=${(e) => setForm({ ...form, postal_address: e.target.value })} /></${MUI.Grid}>
                    </${MUI.Grid}>
                    <${MUI.Grid} container spacing=${2}>
                        <${MUI.Grid} size=${{ xs: 12, sm: 6 }}><${MUI.TextField} label="County" fullWidth value=${form.county} onChange=${(e) => setForm({ ...form, county: e.target.value })} /></${MUI.Grid}>
                        <${MUI.Grid} size=${{ xs: 12, sm: 6 }}>
                            <${MUI.TextField} select label="Membership Category" fullWidth value=${form.category} onChange=${(e) => setForm({ ...form, category: e.target.value })}>
                                <${MUI.MenuItem} value="INDIVIDUAL">Individual Truck / Commercial Owner</${MUI.MenuItem}>
                                <${MUI.MenuItem} value="FLEET_OWNER">Fleet Owner (Multiple Trucks & Trailers)</${MUI.MenuItem}>
                                <${MUI.MenuItem} value="CORPORATE">Corporate Transport Operator</${MUI.MenuItem}>
                            </${MUI.TextField}>
                        </${MUI.Grid}>
                    </${MUI.Grid}>
                    <${MUI.Grid} container spacing=${2}>
                        <${MUI.Grid} size=${{ xs: 12, sm: 4 }}><${MUI.TextField} label="Next of Kin Name" fullWidth required value=${form.next_of_kin_name} onChange=${(e) => setForm({ ...form, next_of_kin_name: e.target.value })} /></${MUI.Grid}>
                        <${MUI.Grid} size=${{ xs: 12, sm: 4 }}><${MUI.TextField} label="Relationship" fullWidth required value=${form.next_of_kin_relation} onChange=${(e) => setForm({ ...form, next_of_kin_relation: e.target.value })} /></${MUI.Grid}>
                        <${MUI.Grid} size=${{ xs: 12, sm: 4 }}><${MUI.TextField} label="Kin Phone" fullWidth required value=${form.next_of_kin_phone} onChange=${(e) => setForm({ ...form, next_of_kin_phone: e.target.value })} /></${MUI.Grid}>
                    </${MUI.Grid}>

                    <${MUI.Divider} />

                    <${MUI.Typography} variant="subtitle2" sx=${{ fontWeight: 700, color: 'primary.main' }}>
                        2. Member Self-Service Portal Account
                    </${MUI.Typography}>
                    <${MUI.Alert} severity="info" sx=${{ py: 0.5 }}>
                        Every member receives a dedicated Member Portal login account. Leave username/password blank to auto-generate secure credentials.
                    </${MUI.Alert}>
                    <${MUI.Grid} container spacing=${2}>
                        <${MUI.Grid} size=${{ xs: 12, sm: 6 }}>
                            <${MUI.TextField}
                                label="Portal Username (Optional)"
                                placeholder="Auto-generated from email if blank"
                                fullWidth
                                value=${form.portal_username}
                                onChange=${(e) => setForm({ ...form, portal_username: e.target.value })}
                            />
                        </${MUI.Grid}>
                        <${MUI.Grid} size=${{ xs: 12, sm: 6 }}>
                            <${MUI.TextField}
                                label="Portal Password (Optional)"
                                type="password"
                                placeholder="Auto-generated strong password if blank"
                                fullWidth
                                value=${form.portal_password}
                                onChange=${(e) => setForm({ ...form, portal_password: e.target.value })}
                            />
                        </${MUI.Grid}>
                    </${MUI.Grid}>
                    <${MUI.FormControlLabel}
                        control=${html`<${MUI.Switch} checked=${Boolean(form.must_change_password)} onChange=${(e) => setForm({ ...form, must_change_password: e.target.checked })} />`}
                        label="Require member to change password on first portal login"
                    />

                    <${MUI.Divider} />

                    <${MUI.Box} sx=${{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 1 }}>
                        <${MUI.Typography} variant="subtitle2" sx=${{ fontWeight: 700, color: 'primary.main' }}>
                            3. Vehicle Details (Commercial Trucks & Trailers)
                        </${MUI.Typography}>
                        <${MUI.Button}
                            size="small"
                            variant="outlined"
                            startIcon=${html`<${MaterialIcon} name="add" />`}
                            onClick=${() => setMemberVehicles([...memberVehicles, blankVehicleEntry()])}
                        >
                            Add Another Truck / Trailer
                        </${MUI.Button}>
                    </${MUI.Box}>
                    ${memberVehicles.map((veh, idx) => html`
                        <${MUI.Paper} key=${idx} variant="outlined" sx=${{ p: 2, borderRadius: 2 }}>
                            <${MUI.Box} sx=${{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
                                <${MUI.Typography} variant="caption" sx=${{ fontWeight: 700, textTransform: 'uppercase' }}>
                                    Commercial Unit #${idx + 1}
                                </${MUI.Typography}>
                                ${memberVehicles.length > 1 && html`
                                    <${MUI.Button}
                                        size="small"
                                        color="error"
                                        onClick=${() => setMemberVehicles(memberVehicles.filter((_, i) => i !== idx))}
                                    >
                                        Remove
                                    </${MUI.Button}>
                                `}
                            </${MUI.Box}>
                            <${VehicleFieldsSection}
                                value=${veh}
                                categories=${categories}
                                fuelTypes=${fuelTypes}
                                onChange=${(nextVeh) => setMemberVehicles(memberVehicles.map((item, i) => (i === idx ? nextVeh : item)))}
                            />
                        </${MUI.Paper}>
                    `)}
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
                            <${MUI.Grid} size=${{ xs: 6 }}><${MUI.TextField} label="First Name" fullWidth value=${editTarget.first_name || ''} onChange=${(e) => setEditTarget({ ...editTarget, first_name: e.target.value })} /></${MUI.Grid}>
                            <${MUI.Grid} size=${{ xs: 6 }}><${MUI.TextField} label="Last Name" fullWidth value=${editTarget.last_name || ''} onChange=${(e) => setEditTarget({ ...editTarget, last_name: e.target.value })} /></${MUI.Grid}>
                        </${MUI.Grid}>
                        <${MUI.TextField} label="Phone Number" fullWidth value=${editTarget.phone_number || ''} onChange=${(e) => setEditTarget({ ...editTarget, phone_number: e.target.value })} />
                        <${MUI.TextField} label="Email" fullWidth value=${editTarget.email || ''} onChange=${(e) => setEditTarget({ ...editTarget, email: e.target.value })} />
                        <${MUI.TextField} label="County" fullWidth value=${editTarget.county || ''} onChange=${(e) => setEditTarget({ ...editTarget, county: e.target.value })} />
                        <${MUI.TextField} label="Next of Kin Name" fullWidth value=${editTarget.next_of_kin_name || ''} onChange=${(e) => setEditTarget({ ...editTarget, next_of_kin_name: e.target.value })} />
                        <${MUI.Divider} />
                        <${MUI.Typography} variant="subtitle2">Registered Commercial Fleet (${(editTarget.vehicles || []).length})</${MUI.Typography}>
                        ${(editTarget.vehicles || []).length === 0 ? html`
                            <${MUI.Typography} variant="body2" color="text.secondary">No vehicles registered under this member yet.</${MUI.Typography}>
                        ` : (editTarget.vehicles || []).map((v) => html`
                            <${MUI.Chip}
                                key=${v.id}
                                label="${v.registration_number} — ${v.make} ${v.model} (${v.category_display}, ${v.carrying_capacity}T)"
                                variant="outlined"
                                sx=${{ justifyContent: 'flex-start' }}
                            />
                        `)}
                    </${MUI.Stack}>
                `}
            </${ResponsiveDialog}>

            <${ResponsiveDialog}
                open=${Boolean(portalTarget)}
                onClose=${() => setPortalTarget(null)}
                title=${`Provision / Reset Portal Account: ${portalTarget?.full_name || ''}`}
                actions=${html`
                    <${MUI.Button} onClick=${() => setPortalTarget(null)}>Cancel</${MUI.Button}>
                    <${MUI.Button} variant="contained" color="info" onClick=${handleProvisionPortal}>Activate & Issue Credentials</${MUI.Button}>
                `}
            >
                ${portalTarget && html`
                    <${MUI.Stack} spacing=${2} sx=${{ pt: 1 }}>
                        <${MUI.Alert} severity="info">
                            Portal Username: <strong>@${portalTarget.username || 'auto'}</strong> (${portalTarget.membership_number})
                        </${MUI.Alert}>
                        <${MUI.TextField}
                            label="New Temporary Password (Optional)"
                            type="password"
                            placeholder="Leave blank to auto-generate strong password"
                            fullWidth
                            value=${portalResetForm.password}
                            onChange=${(e) => setPortalResetForm({ ...portalResetForm, password: e.target.value })}
                        />
                        <${MUI.FormControlLabel}
                            control=${html`<${MUI.Switch} checked=${Boolean(portalResetForm.must_change_password)} onChange=${(e) => setPortalResetForm({ ...portalResetForm, must_change_password: e.target.checked })} />`}
                            label="Require password change on next login"
                        />
                    </${MUI.Stack}>
                `}
            </${ResponsiveDialog}>

            <${ResponsiveDialog}
                open=${Boolean(credsModal)}
                onClose=${() => setCredsModal(null)}
                title=${credsModal?.title || 'Portal Credentials'}
                actions=${html`
                    <${MUI.Button} variant="contained" onClick=${() => setCredsModal(null)}>Done</${MUI.Button}>
                `}
            >
                ${credsModal && html`
                    <${MUI.Stack} spacing=${2} sx=${{ pt: 1 }}>
                        <${MUI.Alert} severity="success">
                            Portal access is active for <strong>${credsModal.full_name}</strong> (${credsModal.membership_number}). Share these credentials securely with the member.
                        </${MUI.Alert}>
                        <${MUI.Paper} variant="outlined" sx=${{ p: 2, bgcolor: 'background.default' }}>
                            <${MUI.Typography} variant="body2"><strong>Portal Login URL:</strong> /portal/ (or /app/)</${MUI.Typography}>
                            <${MUI.Typography} variant="body2"><strong>Username:</strong> <span className="nht-mono">${credsModal.credentials?.username}</span></${MUI.Typography}>
                            <${MUI.Typography} variant="body2"><strong>Temporary Password:</strong> <span className="nht-mono">${credsModal.credentials?.temporary_password}</span></${MUI.Typography}>
                        </${MUI.Paper}>
                        ${(credsModal.vehicles || []).length > 0 && html`
                            <${MUI.Box}>
                                <${MUI.Typography} variant="subtitle2" sx=${{ mb: 0.5 }}>Registered Commercial Units</${MUI.Typography}>
                                <${MUI.Stack} direction="row" spacing=${0.5} flexWrap="wrap" useFlexGap>
                                    ${credsModal.vehicles.map((v) => html`<${MUI.Chip} key=${v.id} size="small" color="primary" label="${v.registration_number} (${v.category_display})" />`)}
                                </${MUI.Stack}>
                            </${MUI.Box}>
                        `}
                    </${MUI.Stack}>
                `}
            </${ResponsiveDialog}>
        </${MUI.Box}>
    `;
}

export function VehiclesPage({ notify, onNavigate }) {
    const [rows, setRows] = React.useState([]);
    const [members, setMembers] = React.useState([]);
    const [categories, setCategories] = React.useState(DEFAULT_COMMERCIAL_CATEGORIES);
    const [fuelTypes, setFuelTypes] = React.useState(DEFAULT_FUEL_TYPES);
    const [loading, setLoading] = React.useState(true);
    const [search, setSearch] = React.useState('');
    const [createOpen, setCreateOpen] = React.useState(false);
    const [transferVehicle, setTransferVehicle] = React.useState(null);
    const [newOwner, setNewOwner] = React.useState('');
    const [transferReason, setTransferReason] = React.useState('');
    const [form, setForm] = React.useState({
        ...blankVehicleEntry(),
        current_owner: '',
    });

    const load = React.useCallback(async () => {
        setLoading(true);
        try {
            const [vRes, mRes, catRes] = await Promise.all([
                apiFetch(`/api/v1/vehicles/?search=${encodeURIComponent(search)}`),
                apiFetch('/api/v1/members/'),
                apiFetch('/api/v1/vehicles/categories/').catch(() => null),
            ]);
            setRows(extractList(vRes));
            setMembers(extractList(mRes));
            if (catRes?.categories?.length) setCategories(catRes.categories);
            if (catRes?.fuel_types?.length) setFuelTypes(catRes.fuel_types);
        } catch (err) {
            notify(err.message, 'error');
        } finally {
            setLoading(false);
        }
    }, [search, notify]);

    React.useEffect(() => { load(); }, [load]);

    const handleCreate = async () => {
        const isTrailer = form.category === 'SEMI_TRAILER' || form.fuel_type === 'NONE';
        if (!form.registration_number.trim() || !form.chassis_number.trim() || !form.make.trim() || !form.model.trim() || !form.current_owner || (!isTrailer && !form.engine_number.trim())) {
            notify('Please complete all required truck/trailer fields and select an owner member.', 'warning');
            return;
        }
        try {
            await apiFetch('/api/v1/vehicles/', {
                method: 'POST',
                body: {
                    ...form,
                    engine_number: form.engine_number?.trim() || null,
                },
            });
            notify('Commercial truck / trailer registered.', 'success');
            setCreateOpen(false);
            setForm({ ...blankVehicleEntry(), current_owner: '' });
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
                title="Commercial Trucks & Trailers Registry"
                subtitle="Commercial trucks, prime movers, trailers, compliance standing, ownership transfers, and compliance card issuance."
                action=${html`
                    <${MUI.Button} variant="contained" startIcon=${html`<${MaterialIcon} name="local_shipping" />`} onClick=${() => setCreateOpen(true)}>
                        Register Truck / Trailer
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
                    { key: 'carrying_capacity', label: 'Payload', render: (r) => `${r.carrying_capacity} T` },
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
                title="Register Commercial Truck / Trailer"
                maxWidth="md"
                actions=${html`
                    <${MUI.Button} onClick=${() => setCreateOpen(false)}>Cancel</${MUI.Button}>
                    <${MUI.Button} variant="contained" onClick=${handleCreate}>Save Commercial Unit</${MUI.Button}>
                `}
            >
                <${MUI.Stack} spacing=${2} sx=${{ pt: 1 }}>
                    <${MUI.TextField} select label="Owner Member *" fullWidth value=${form.current_owner} onChange=${(e) => setForm({ ...form, current_owner: e.target.value })}>
                        ${members.map((m) => html`<${MUI.MenuItem} key=${m.id} value=${m.id}>${m.full_name} (${m.membership_number})</${MUI.MenuItem}>`)}
                    </${MUI.TextField}>
                    <${VehicleFieldsSection}
                        value=${form}
                        categories=${categories}
                        fuelTypes=${fuelTypes}
                        onChange=${setForm}
                    />
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

const blankDriverForm = () => ({
    full_name: '',
    national_id: '',
    phone_number: '',
    email: '',
    driving_license_number: '',
    dl_class: '',
    dl_issue_date: '',
    dl_expiry_date: '',
    psv_badge_number: '',
    psv_badge_expiry: '',
    emergency_contact_name: '',
    emergency_contact_phone: '',
    status: 'ACTIVE',
    vehicle: '',
    create_portal_account: false,
    portal_username: '',
    portal_password: '',
    must_change_password: true,
});

const DRIVER_STATUS_OPTIONS = [
    { value: 'ACTIVE', label: 'Active Authorized Driver' },
    { value: 'ON_LEAVE', label: 'On Leave' },
    { value: 'SUSPENDED', label: 'Suspended' },
    { value: 'INACTIVE', label: 'Inactive' },
];

function DriverFieldsSection({ value, onChange, vehicles, canAllocateVehicles }) {
    return html`
        <${MUI.Stack} spacing=${2.5}>
            <${MUI.Typography} variant="subtitle2" sx=${{ fontWeight: 700, color: 'primary.main' }}>
                1. Driver Personal & Emergency Contact Details
            </${MUI.Typography}>
            <${MUI.Grid} container spacing=${2}>
                <${MUI.Grid} size=${{ xs: 12, sm: 6 }}>
                    <${MUI.TextField}
                        label="Full Name *"
                        fullWidth
                        size="small"
                        value=${value.full_name || ''}
                        onChange=${(e) => onChange({ ...value, full_name: e.target.value })}
                    />
                </${MUI.Grid}>
                <${MUI.Grid} size=${{ xs: 12, sm: 6 }}>
                    <${MUI.TextField}
                        label="National ID / Passport *"
                        fullWidth
                        size="small"
                        value=${value.national_id || ''}
                        onChange=${(e) => onChange({ ...value, national_id: e.target.value })}
                    />
                </${MUI.Grid}>
                <${MUI.Grid} size=${{ xs: 12, sm: 6 }}>
                    <${MUI.TextField}
                        label="Phone Number (+2547...) *"
                        fullWidth
                        size="small"
                        value=${value.phone_number || ''}
                        onChange=${(e) => onChange({ ...value, phone_number: e.target.value })}
                    />
                </${MUI.Grid}>
                <${MUI.Grid} size=${{ xs: 12, sm: 6 }}>
                    <${MUI.TextField}
                        label="Email Address"
                        type="email"
                        placeholder="Required if creating portal account"
                        fullWidth
                        size="small"
                        value=${value.email || ''}
                        onChange=${(e) => onChange({ ...value, email: e.target.value })}
                    />
                </${MUI.Grid}>
                <${MUI.Grid} size=${{ xs: 12, sm: 4 }}>
                    <${MUI.TextField}
                        label="Emergency Contact Person *"
                        fullWidth
                        size="small"
                        value=${value.emergency_contact_name || ''}
                        onChange=${(e) => onChange({ ...value, emergency_contact_name: e.target.value })}
                    />
                </${MUI.Grid}>
                <${MUI.Grid} size=${{ xs: 12, sm: 4 }}>
                    <${MUI.TextField}
                        label="Emergency Contact Phone *"
                        fullWidth
                        size="small"
                        value=${value.emergency_contact_phone || ''}
                        onChange=${(e) => onChange({ ...value, emergency_contact_phone: e.target.value })}
                    />
                </${MUI.Grid}>
                <${MUI.Grid} size=${{ xs: 12, sm: 4 }}>
                    <${MUI.TextField}
                        select
                        label="Driver Status"
                        fullWidth
                        size="small"
                        value=${value.status || 'ACTIVE'}
                        onChange=${(e) => onChange({ ...value, status: e.target.value })}
                    >
                        ${DRIVER_STATUS_OPTIONS.map((opt) => html`
                            <${MUI.MenuItem} key=${opt.value} value=${opt.value}>${opt.label}</${MUI.MenuItem}>
                        `)}
                    </${MUI.TextField}>
                </${MUI.Grid}>
            </${MUI.Grid}>

            <${MUI.Divider} />

            <${MUI.Typography} variant="subtitle2" sx=${{ fontWeight: 700, color: 'primary.main' }}>
                2. Driving License & NTSA Endorsement Details
            </${MUI.Typography}>
            <${MUI.Grid} container spacing=${2}>
                <${MUI.Grid} size=${{ xs: 12, sm: 6 }}>
                    <${MUI.TextField}
                        label="Driving License Number *"
                        placeholder="e.g. DL-NTSA-1001"
                        fullWidth
                        size="small"
                        value=${value.driving_license_number || ''}
                        onChange=${(e) => onChange({ ...value, driving_license_number: e.target.value })}
                    />
                </${MUI.Grid}>
                <${MUI.Grid} size=${{ xs: 12, sm: 6 }}>
                    <${MUI.TextField}
                        label="License Class(es)"
                        placeholder="e.g. BCE, CE (Heavy Commercial), C1"
                        fullWidth
                        size="small"
                        value=${value.dl_class || ''}
                        onChange=${(e) => onChange({ ...value, dl_class: e.target.value })}
                    />
                </${MUI.Grid}>
                <${MUI.Grid} size=${{ xs: 12, sm: 6 }}>
                    <${MUI.TextField}
                        label="DL Issue Date"
                        type="date"
                        slotProps=${{ inputLabel: { shrink: true } }}
                        fullWidth
                        size="small"
                        value=${value.dl_issue_date || ''}
                        onChange=${(e) => onChange({ ...value, dl_issue_date: e.target.value })}
                    />
                </${MUI.Grid}>
                <${MUI.Grid} size=${{ xs: 12, sm: 6 }}>
                    <${MUI.TextField}
                        label="DL Expiry Date *"
                        type="date"
                        slotProps=${{ inputLabel: { shrink: true } }}
                        fullWidth
                        size="small"
                        value=${value.dl_expiry_date || ''}
                        onChange=${(e) => onChange({ ...value, dl_expiry_date: e.target.value })}
                    />
                </${MUI.Grid}>
                <${MUI.Grid} size=${{ xs: 12, sm: 6 }}>
                    <${MUI.TextField}
                        label="NTSA Commercial Endorsement / Badge #"
                        placeholder="e.g. COM-2026-001"
                        fullWidth
                        size="small"
                        value=${value.psv_badge_number || ''}
                        onChange=${(e) => onChange({ ...value, psv_badge_number: e.target.value })}
                    />
                </${MUI.Grid}>
                <${MUI.Grid} size=${{ xs: 12, sm: 6 }}>
                    <${MUI.TextField}
                        label="Endorsement / Badge Expiry Date"
                        type="date"
                        slotProps=${{ inputLabel: { shrink: true } }}
                        fullWidth
                        size="small"
                        value=${value.psv_badge_expiry || ''}
                        onChange=${(e) => onChange({ ...value, psv_badge_expiry: e.target.value })}
                    />
                </${MUI.Grid}>
            </${MUI.Grid}>

            ${canAllocateVehicles && html`
                <${MUI.Divider} />
                <${MUI.Typography} variant="subtitle2" sx=${{ fontWeight: 700, color: 'primary.main' }}>
                    3. Vehicle Allocation
                </${MUI.Typography}>
                <${MUI.TextField}
                    select
                    label="Allocated Commercial Truck / Trailer"
                    fullWidth
                    size="small"
                    value=${value.vehicle || ''}
                    onChange=${(e) => onChange({ ...value, vehicle: e.target.value })}
                    helperText="Assign a commercial truck or trailer now, or leave unassigned to allocate later."
                >
                    <${MUI.MenuItem} value="">Unassigned (No Vehicle Allocated)</${MUI.MenuItem}>
                    ${vehicles.map((v) => html`
                        <${MUI.MenuItem} key=${v.id} value=${v.id}>
                            ${v.registration_number} — ${v.make} ${v.model} (${v.category_display})
                        </${MUI.MenuItem}>
                    `)}
                </${MUI.TextField}>
            `}
        </${MUI.Stack}>
    `;
}

export function DriversPage({ me, notify }) {
    const user = me?.user || {};
    const canManageDrivers = Boolean(user.is_superuser || ['SUPER_ADMIN', 'CHAIRMAN', 'SECRETARY', 'FIELD_OFFICER', 'COMPLIANCE_OFFICER'].includes(user.role));
    const canAllocateVehicles = Boolean(user.is_superuser || ['SUPER_ADMIN', 'CHAIRMAN', 'SECRETARY', 'FIELD_OFFICER'].includes(user.role));

    const [drivers, setDrivers] = React.useState([]);
    const [assignments, setAssignments] = React.useState([]);
    const [vehicles, setVehicles] = React.useState([]);
    const [loading, setLoading] = React.useState(true);
    const [search, setSearch] = React.useState('');
    const [statusFilter, setStatusFilter] = React.useState('');

    const [createOpen, setCreateOpen] = React.useState(false);
    const [form, setForm] = React.useState(blankDriverForm);
    const [editTarget, setEditTarget] = React.useState(null);
    const [assignOpen, setAssignOpen] = React.useState(false);
    const [assignForm, setAssignForm] = React.useState({ driver: '', vehicle: '' });
    const [portalTarget, setPortalTarget] = React.useState(null);
    const [portalForm, setPortalForm] = React.useState({ email: '', portal_username: '', password: '', must_change_password: true });
    const [credsModal, setCredsModal] = React.useState(null);

    const load = React.useCallback(async () => {
        setLoading(true);
        try {
            const qs = new URLSearchParams();
            if (search) qs.set('search', search);
            if (statusFilter) qs.set('status', statusFilter);
            const [dRes, aRes, vRes] = await Promise.all([
                apiFetch(`/api/v1/drivers/?${qs.toString()}`),
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
    }, [search, statusFilter, notify]);

    React.useEffect(() => { load(); }, [load]);

    const validateDriverFields = (d) => {
        if (!d.full_name?.trim() || !d.national_id?.trim() || !d.phone_number?.trim() || !d.emergency_contact_name?.trim() || !d.emergency_contact_phone?.trim()) {
            notify('Please complete all required driver personal and emergency contact fields.', 'warning');
            return false;
        }
        if (!d.driving_license_number?.trim() || !d.dl_expiry_date) {
            notify('Please capture the Driving License Number and DL Expiry Date.', 'warning');
            return false;
        }
        if (d.dl_issue_date && d.dl_expiry_date && d.dl_expiry_date < d.dl_issue_date) {
            notify('DL Expiry Date cannot be earlier than DL Issue Date.', 'warning');
            return false;
        }
        if (d.create_portal_account && !d.email?.trim()) {
            notify('An email address is required when creating a Driver Portal account.', 'warning');
            return false;
        }
        return true;
    };

    const handleRegisterDriver = async () => {
        if (!validateDriverFields(form)) return;
        try {
            const payload = {
                full_name: form.full_name.trim(),
                national_id: form.national_id.trim(),
                phone_number: form.phone_number.trim(),
                email: form.email.trim(),
                driving_license_number: form.driving_license_number.trim(),
                dl_class: form.dl_class.trim(),
                dl_issue_date: form.dl_issue_date || null,
                dl_expiry_date: form.dl_expiry_date,
                psv_badge_number: form.psv_badge_number.trim(),
                psv_badge_expiry: form.psv_badge_expiry || null,
                emergency_contact_name: form.emergency_contact_name.trim(),
                emergency_contact_phone: form.emergency_contact_phone.trim(),
                status: form.status || 'ACTIVE',
                create_portal_account: Boolean(form.create_portal_account),
                portal_username: form.portal_username.trim(),
                portal_password: form.portal_password,
                must_change_password: Boolean(form.must_change_password),
            };
            if (canAllocateVehicles && form.vehicle) {
                payload.vehicle = form.vehicle;
            }
            const created = await apiFetch('/api/v1/drivers/', { method: 'POST', body: payload });
            const allocSuffix = created.current_vehicle_plate ? ` & allocated to ${created.current_vehicle_plate}` : '';
            notify(`Driver ${created.full_name} registered${allocSuffix}.`, 'success');
            setCreateOpen(false);
            setForm(blankDriverForm());
            if (created.provisioned_portal_credentials) {
                setCredsModal({
                    title: 'Driver Registered & Portal Account Created',
                    full_name: created.full_name,
                    driving_license_number: created.driving_license_number,
                    vehicle_plate: created.current_vehicle_plate,
                    credentials: created.provisioned_portal_credentials,
                });
            }
            load();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const handleSaveEdit = async () => {
        if (!editTarget || !validateDriverFields(editTarget)) return;
        try {
            const payload = {
                full_name: editTarget.full_name.trim(),
                national_id: editTarget.national_id.trim(),
                phone_number: editTarget.phone_number.trim(),
                email: (editTarget.email || '').trim(),
                driving_license_number: editTarget.driving_license_number.trim(),
                dl_class: (editTarget.dl_class || '').trim(),
                dl_issue_date: editTarget.dl_issue_date || null,
                dl_expiry_date: editTarget.dl_expiry_date,
                psv_badge_number: (editTarget.psv_badge_number || '').trim(),
                psv_badge_expiry: editTarget.psv_badge_expiry || null,
                emergency_contact_name: editTarget.emergency_contact_name.trim(),
                emergency_contact_phone: editTarget.emergency_contact_phone.trim(),
                status: editTarget.status,
            };
            if (canAllocateVehicles) {
                payload.vehicle = editTarget.vehicle || null;
            }
            await apiFetch(`/api/v1/drivers/${editTarget.id}/`, {
                method: 'PATCH',
                body: payload,
            });
            notify(`Driver ${editTarget.full_name} details updated.`, 'success');
            setEditTarget(null);
            load();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const handleAssign = async () => {
        if (!assignForm.driver || !assignForm.vehicle) {
            notify('Select both a driver and a vehicle.', 'warning');
            return;
        }
        try {
            await apiFetch('/api/v1/driver-assignments/', { method: 'POST', body: assignForm });
            notify('Driver assigned to vehicle.', 'success');
            setAssignOpen(false);
            setAssignForm({ driver: '', vehicle: '' });
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

    const handleProvisionPortal = async () => {
        if (!portalTarget) return;
        try {
            const res = await apiFetch(`/api/v1/drivers/${portalTarget.id}/provision_portal_account/`, {
                method: 'POST',
                body: portalForm,
            });
            notify(`Driver portal account @${res.username} activated/reset.`, 'success');
            setCredsModal({
                title: 'Driver Portal Credentials Provisioned',
                full_name: portalTarget.full_name,
                driving_license_number: portalTarget.driving_license_number,
                vehicle_plate: portalTarget.current_vehicle_plate,
                credentials: res,
            });
            setPortalTarget(null);
            setPortalForm({ email: '', portal_username: '', password: '', must_change_password: true });
            load();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    return html`
        <${MUI.Box}>
            <${PageHeader}
                title="Commercial Fleet Drivers & Vehicle Assignments"
                subtitle="Register drivers with driving license & NTSA endorsement details, allocate trucks/trailers, and manage driver records."
                action=${canManageDrivers && html`
                    <${MUI.Stack} direction="row" spacing=${1} flexWrap="wrap">
                        ${canAllocateVehicles && html`
                            <${MUI.Button} variant="outlined" startIcon=${html`<${MaterialIcon} name="assignment_ind" />`} onClick=${() => { setAssignForm({ driver: '', vehicle: '' }); setAssignOpen(true); }}>
                                Allocate Vehicle
                            </${MUI.Button}>
                        `}
                        <${MUI.Button} variant="contained" startIcon=${html`<${MaterialIcon} name="person_add" />`} onClick=${() => { setForm(blankDriverForm()); setCreateOpen(true); }}>
                            Register Driver
                        </${MUI.Button}>
                    </${MUI.Stack}>
                `}
            />
            <${ResponsiveDataGrid}
                loading=${loading}
                rows=${drivers}
                search=${search}
                onSearchChange=${setSearch}
                searchPlaceholder="Search driver name, ID, DL #, phone..."
                toolbarExtra=${html`
                    <${MUI.TextField}
                        select
                        size="small"
                        label="Status"
                        value=${statusFilter}
                        onChange=${(e) => setStatusFilter(e.target.value)}
                        sx=${{ minWidth: 160 }}
                    >
                        <${MUI.MenuItem} value="">All Statuses</${MUI.MenuItem}>
                        ${DRIVER_STATUS_OPTIONS.map((opt) => html`
                            <${MUI.MenuItem} key=${opt.value} value=${opt.value}>${opt.label}</${MUI.MenuItem}>
                        `)}
                    </${MUI.TextField}>
                `}
                columns=${[
                    {
                        key: 'full_name',
                        label: 'Driver',
                        render: (r) => html`
                            <${MUI.Box}>
                                <strong>${r.full_name}</strong>
                                <${MUI.Typography} variant="caption" color="text.secondary" display="block">
                                    ID: ${r.national_id} • ${r.phone_number}
                                </${MUI.Typography}>
                            </${MUI.Box}>
                        `,
                    },
                    {
                        key: 'driving_license_number',
                        label: 'Driving License',
                        render: (r) => html`
                            <${MUI.Stack} direction="row" spacing=${0.5} alignItems="center" flexWrap="wrap" useFlexGap>
                                <span className="nht-mono">${r.driving_license_number}</span>
                                ${r.dl_class && html`<${MUI.Chip} size="small" label=${`Class ${r.dl_class}`} variant="outlined" />`}
                            </${MUI.Stack}>
                        `,
                    },
                    {
                        key: 'dl_expiry_date',
                        label: 'DL Expiry',
                        render: (r) => {
                            const days = r.dl_days_remaining;
                            const chipColor = r.is_dl_expired ? 'error' : (days !== null && days <= 30 ? 'warning' : 'success');
                            return html`
                                <${MUI.Stack} direction="row" spacing=${0.5} alignItems="center">
                                    <span>${r.dl_expiry_date}</span>
                                    ${days !== null && html`
                                        <${MUI.Chip}
                                            size="small"
                                            color=${chipColor}
                                            variant="outlined"
                                            label=${r.is_dl_expired ? 'Expired' : `${days}d`}
                                        />
                                    `}
                                </${MUI.Stack}>
                            `;
                        },
                    },
                    {
                        key: 'current_vehicle_plate',
                        label: 'Allocated Vehicle',
                        render: (r) => r.current_vehicle_plate ? html`
                            <${MUI.Chip} size="small" color="primary" variant="outlined" label=${r.current_vehicle_plate} />
                        ` : html`<${MUI.Typography} variant="caption" color="text.secondary">Unassigned</${MUI.Typography}>`,
                    },
                    {
                        key: 'username',
                        label: 'Portal Account',
                        render: (r) => r.username ? html`
                            <${MUI.Stack} direction="row" spacing=${0.5} alignItems="center">
                                <span className="nht-mono">@${r.username}</span>
                                <${MUI.Chip}
                                    size="small"
                                    label=${r.has_portal_account ? 'Active' : 'Inactive'}
                                    color=${r.has_portal_account ? 'success' : 'warning'}
                                    variant="outlined"
                                />
                            </${MUI.Stack}>
                        ` : html`<${MUI.Typography} variant="caption" color="text.secondary">Not Linked</${MUI.Typography}>`,
                    },
                    { key: 'status', label: 'Status', render: (r) => html`<${StatusChip} value=${r.status} />` },
                    ...(canManageDrivers ? [{
                        key: 'actions',
                        label: 'Actions',
                        align: 'right',
                        render: (r) => html`
                            <${MUI.Stack} direction="row" spacing=${0.5} justifyContent="flex-end" flexWrap="wrap">
                                <${MUI.Button}
                                    size="small"
                                    onClick=${() => setEditTarget({ ...r, vehicle: r.current_vehicle || '' })}
                                >
                                    Edit
                                </${MUI.Button}>
                                ${canAllocateVehicles && html`
                                    <${MUI.Button}
                                        size="small"
                                        color="primary"
                                        onClick=${() => { setAssignForm({ driver: r.id, vehicle: r.current_vehicle || '' }); setAssignOpen(true); }}
                                    >
                                        Allocate
                                    </${MUI.Button}>
                                    <${MUI.Button}
                                        size="small"
                                        color="info"
                                        onClick=${() => { setPortalTarget(r); setPortalForm({ email: r.email || '', portal_username: r.username || '', password: '', must_change_password: true }); }}
                                    >
                                        Portal
                                    </${MUI.Button}>
                                `}
                            </${MUI.Stack}>
                        `,
                    }] : []),
                ]}
            />
            <${MUI.Typography} variant="h6" sx=${{ mt: 3, mb: 1.5 }}>Active & Historical Crew Assignments</${MUI.Typography}>
            <${ResponsiveDataGrid}
                loading=${loading}
                rows=${assignments}
                columns=${[
                    { key: 'driver_name', label: 'Driver', render: (r) => html`<strong>${r.driver_name}</strong>` },
                    { key: 'driver_dl_number', label: 'DL #', render: (r) => html`<span className="nht-mono">${r.driver_dl_number || '—'}</span>` },
                    { key: 'vehicle_plate', label: 'Vehicle', render: (r) => html`<strong>${r.vehicle_plate}</strong>` },
                    { key: 'vehicle_make_model', label: 'Unit' },
                    { key: 'is_current', label: 'Active', render: (r) => html`<${StatusChip} value=${r.is_current ? 'ACTIVE' : 'CLOSED'} />` },
                    ...(canAllocateVehicles ? [{
                        key: 'actions',
                        label: 'Action',
                        align: 'right',
                        render: (r) => r.is_current && html`<${MUI.Button} size="small" color="warning" onClick=${() => handleRelieve(r.id)}>Relieve</${MUI.Button}>`,
                    }] : []),
                ]}
            />

            <${ResponsiveDialog}
                open=${createOpen}
                onClose=${() => setCreateOpen(false)}
                title="Register Commercial Fleet Driver"
                maxWidth="md"
                actions=${html`
                    <${MUI.Button} onClick=${() => setCreateOpen(false)}>Cancel</${MUI.Button}>
                    <${MUI.Button} variant="contained" onClick=${handleRegisterDriver}>Register Driver</${MUI.Button}>
                `}
            >
                <${MUI.Stack} spacing=${2.5} sx=${{ pt: 1 }}>
                    <${DriverFieldsSection}
                        value=${form}
                        onChange=${setForm}
                        vehicles=${vehicles}
                        canAllocateVehicles=${canAllocateVehicles}
                    />
                    <${MUI.Divider} />
                    <${MUI.Typography} variant="subtitle2" sx=${{ fontWeight: 700, color: 'primary.main' }}>
                        4. Driver Self-Service Portal Account (Optional)
                    </${MUI.Typography}>
                    <${MUI.FormControlLabel}
                        control=${html`
                            <${MUI.Switch}
                                checked=${Boolean(form.create_portal_account)}
                                onChange=${(e) => setForm({ ...form, create_portal_account: e.target.checked })}
                            />
                        `}
                        label="Provision Driver Portal login account upon registration"
                    />
                    ${form.create_portal_account && html`
                        <${MUI.Stack} spacing=${1.5}>
                            <${MUI.Grid} container spacing=${2}>
                                <${MUI.Grid} size=${{ xs: 12, sm: 6 }}>
                                    <${MUI.TextField}
                                        label="Portal Username (Optional)"
                                        placeholder="Auto-generated from email if blank"
                                        fullWidth
                                        size="small"
                                        value=${form.portal_username}
                                        onChange=${(e) => setForm({ ...form, portal_username: e.target.value })}
                                    />
                                </${MUI.Grid}>
                                <${MUI.Grid} size=${{ xs: 12, sm: 6 }}>
                                    <${MUI.TextField}
                                        label="Portal Password (Optional)"
                                        type="password"
                                        placeholder="Auto-generated strong password if blank"
                                        fullWidth
                                        size="small"
                                        value=${form.portal_password}
                                        onChange=${(e) => setForm({ ...form, portal_password: e.target.value })}
                                    />
                                </${MUI.Grid}>
                            </${MUI.Grid}>
                            <${MUI.FormControlLabel}
                                control=${html`
                                    <${MUI.Switch}
                                        checked=${Boolean(form.must_change_password)}
                                        onChange=${(e) => setForm({ ...form, must_change_password: e.target.checked })}
                                    />
                                `}
                                label="Require driver to change password on first login"
                            />
                        </${MUI.Stack}>
                    `}
                </${MUI.Stack}>
            </${ResponsiveDialog}>

            <${ResponsiveDialog}
                open=${Boolean(editTarget)}
                onClose=${() => setEditTarget(null)}
                title=${`Edit Driver Details: ${editTarget?.full_name || ''}`}
                maxWidth="md"
                actions=${html`
                    <${MUI.Button} onClick=${() => setEditTarget(null)}>Cancel</${MUI.Button}>
                    <${MUI.Button} variant="contained" onClick=${handleSaveEdit}>Save Driver Changes</${MUI.Button}>
                `}
            >
                ${editTarget && html`
                    <${MUI.Box} sx=${{ pt: 1 }}>
                        <${DriverFieldsSection}
                            value=${editTarget}
                            onChange=${setEditTarget}
                            vehicles=${vehicles}
                            canAllocateVehicles=${canAllocateVehicles}
                        />
                    </${MUI.Box}>
                `}
            </${ResponsiveDialog}>

            <${ResponsiveDialog}
                open=${assignOpen}
                onClose=${() => setAssignOpen(false)}
                title="Allocate Vehicle to Driver"
                actions=${html`
                    <${MUI.Button} onClick=${() => setAssignOpen(false)}>Cancel</${MUI.Button}>
                    <${MUI.Button} variant="contained" onClick=${handleAssign}>Allocate Vehicle</${MUI.Button}>
                `}
            >
                <${MUI.Stack} spacing=${2} sx=${{ pt: 1 }}>
                    <${MUI.TextField} select label="Driver" fullWidth value=${assignForm.driver} onChange=${(e) => setAssignForm({ ...assignForm, driver: e.target.value })}>
                        ${drivers.map((d) => html`<${MUI.MenuItem} key=${d.id} value=${d.id}>${d.full_name} (DL: ${d.driving_license_number})</${MUI.MenuItem}>`)}
                    </${MUI.TextField}>
                    <${MUI.TextField} select label="Commercial Truck / Trailer" fullWidth value=${assignForm.vehicle} onChange=${(e) => setAssignForm({ ...assignForm, vehicle: e.target.value })}>
                        ${vehicles.map((v) => html`<${MUI.MenuItem} key=${v.id} value=${v.id}>${v.registration_number} — ${v.make} ${v.model}</${MUI.MenuItem}>`)}
                    </${MUI.TextField}>
                </${MUI.Stack}>
            </${ResponsiveDialog}>

            <${ResponsiveDialog}
                open=${Boolean(portalTarget)}
                onClose=${() => setPortalTarget(null)}
                title=${`Driver Portal Account: ${portalTarget?.full_name || ''}`}
                actions=${html`
                    <${MUI.Button} onClick=${() => setPortalTarget(null)}>Cancel</${MUI.Button}>
                    <${MUI.Button} variant="contained" color="info" onClick=${handleProvisionPortal}>Activate & Issue Credentials</${MUI.Button}>
                `}
            >
                ${portalTarget && html`
                    <${MUI.Stack} spacing=${2} sx=${{ pt: 1 }}>
                        <${MUI.Alert} severity="info">
                            ${portalTarget.username ? html`Existing Portal Username: <strong>@${portalTarget.username}</strong>` : 'No portal account linked yet. Provide an email to create one.'}
                        </${MUI.Alert}>
                        ${!portalTarget.username && html`
                            <${MUI.Stack} spacing=${2}>
                                <${MUI.TextField}
                                    label="Driver Email *"
                                    type="email"
                                    fullWidth
                                    value=${portalForm.email}
                                    onChange=${(e) => setPortalForm({ ...portalForm, email: e.target.value })}
                                />
                                <${MUI.TextField}
                                    label="Portal Username (Optional)"
                                    placeholder="Auto-generated from email if blank"
                                    fullWidth
                                    value=${portalForm.portal_username}
                                    onChange=${(e) => setPortalForm({ ...portalForm, portal_username: e.target.value })}
                                />
                            </${MUI.Stack}>
                        `}
                        <${MUI.TextField}
                            label="New Temporary Password (Optional)"
                            type="password"
                            placeholder="Leave blank to auto-generate strong password"
                            fullWidth
                            value=${portalForm.password}
                            onChange=${(e) => setPortalForm({ ...portalForm, password: e.target.value })}
                        />
                        <${MUI.FormControlLabel}
                            control=${html`<${MUI.Switch} checked=${Boolean(portalForm.must_change_password)} onChange=${(e) => setPortalForm({ ...portalForm, must_change_password: e.target.checked })} />`}
                            label="Require password change on next login"
                        />
                    </${MUI.Stack}>
                `}
            </${ResponsiveDialog}>

            <${ResponsiveDialog}
                open=${Boolean(credsModal)}
                onClose=${() => setCredsModal(null)}
                title=${credsModal?.title || 'Driver Portal Credentials'}
                actions=${html`
                    <${MUI.Button} variant="contained" onClick=${() => setCredsModal(null)}>Done</${MUI.Button}>
                `}
            >
                ${credsModal && html`
                    <${MUI.Stack} spacing=${2} sx=${{ pt: 1 }}>
                        <${MUI.Alert} severity="success">
                            Driver Portal access is active for <strong>${credsModal.full_name}</strong> (DL: ${credsModal.driving_license_number}).
                        </${MUI.Alert}>
                        <${MUI.Paper} variant="outlined" sx=${{ p: 2, bgcolor: 'background.default' }}>
                            <${MUI.Typography} variant="body2"><strong>Portal Login URL:</strong> /app/</${MUI.Typography}>
                            <${MUI.Typography} variant="body2"><strong>Username:</strong> <span className="nht-mono">${credsModal.credentials?.username}</span></${MUI.Typography}>
                            <${MUI.Typography} variant="body2"><strong>Temporary Password:</strong> <span className="nht-mono">${credsModal.credentials?.temporary_password}</span></${MUI.Typography}>
                            ${credsModal.vehicle_plate && html`<${MUI.Typography} variant="body2"><strong>Allocated Vehicle:</strong> ${credsModal.vehicle_plate}</${MUI.Typography}>`}
                        </${MUI.Paper}>
                    </${MUI.Stack}>
                `}
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
