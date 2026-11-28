import { React, MUI, html, formatCurrency, formatDateTime } from '../api.js';
import { MaterialIcon } from '../components.js';

const OUTCOME_STYLE = {
    VALID: { color: 'success', icon: 'verified_user', severity: 'success' },
    EXPIRED: { color: 'warning', icon: 'schedule', severity: 'warning' },
    SUSPENDED: { color: 'warning', icon: 'pause_circle', severity: 'warning' },
    REVOKED: { color: 'error', icon: 'gpp_bad', severity: 'error' },
    SUPERSEDED: { color: 'info', icon: 'published_with_changes', severity: 'info' },
    INVALID: { color: 'error', icon: 'error', severity: 'error' },
};

export function PublicVerifyPage({ branding }) {
    const data = window.__NHT_BOOTSTRAP__?.page_data?.verify_result || { outcome: 'INVALID', headline: 'Invalid Token', detail: 'No verification data supplied.' };
    const st = OUTCOME_STYLE[data.outcome] || OUTCOME_STYLE.INVALID;
    const card = data.card;
    const saccoName = data.sacco_name || branding?.sacco_name || 'Northern Highways Transporters SACCO';

    const rows = card ? [
        ['Certificate Ref', card.certificate_number],
        card.fleet_number ? ['Fleet / Ref No', card.fleet_number] : null,
        card.assigned_route ? ['Assigned Route', card.assigned_route] : null,
        ['Vehicle Service', card.vehicle_status],
        ['Payload Capacity', `${card.carrying_capacity} Tonnes`],
        card.issue_date ? ['Issue Date', card.issue_date] : null,
        card.expiry_date ? ['Expiry Date', card.expiry_date] : null,
        ['Verified Timestamp', data.verified_at ? formatDateTime(data.verified_at) : ''],
    ].filter(Boolean) : [];

    return html`
        <${MUI.Box} sx=${{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', bgcolor: 'background.default', p: 2 }}>
            <${MUI.Card} sx=${{ maxWidth: 560, width: '100%', overflow: 'hidden', boxShadow: 6 }}>
                <${MUI.Box}
                    sx=${{
                        p: 3,
                        textAlign: 'center',
                        background: `linear-gradient(135deg, #091E38 0%, ${branding?.primary_color || '#10315C'} 100%)`,
                        color: '#FFFFFF',
                        borderBottom: `4px solid ${branding?.secondary_color || '#FF8A00'}`,
                    }}
                >
                    ${data.sacco_logo_url ? html`
                        <img
                            src=${data.sacco_logo_url}
                            alt=${saccoName}
                            style=${{ maxHeight: 56, background: '#FFFFFF', padding: '4px 10px', borderRadius: 8, marginBottom: 10 }}
                        />
                    ` : html`
                        <${MaterialIcon} name="verified_user" fontSize="large" sx=${{ color: '#FF8A00', mb: 1 }} />
                    `}
                    <${MUI.Typography} variant="h6" sx=${{ fontWeight: 800, color: '#FFFFFF' }}>${saccoName}</${MUI.Typography}>
                    <${MUI.Typography} variant="caption" sx=${{ color: 'rgba(255,255,255,0.84)' }}>
                        Official Live Fleet Compliance Verification Registry
                    </${MUI.Typography}>
                </${MUI.Box}>

                <${MUI.CardContent} sx=${{ p: 3, textAlign: 'center' }}>
                    ${card && html`
                        <${MUI.Box} sx=${{ mb: 2 }}>
                            <${MUI.Typography} className="nht-mono" variant="h4" color="primary.main" sx=${{ fontWeight: 800, letterSpacing: 2 }}>
                                ${card.registration_number}
                            </${MUI.Typography}>
                            <${MUI.Typography} variant="body2" color="text.secondary">
                                ${card.make_model} &bull; ${card.category}
                            </${MUI.Typography}>
                        </${MUI.Box}>
                    `}

                    <${MUI.Alert} severity=${st.severity} icon=${html`<${MaterialIcon} name=${st.icon} />`} sx=${{ mb: 2.5, textAlign: 'left' }}>
                        <${MUI.AlertTitle} sx=${{ fontWeight: 800 }}>${data.outcome}: ${data.headline}</${MUI.AlertTitle}>
                        ${data.detail}
                    </${MUI.Alert}>

                    ${rows.length > 0 && html`
                        <${MUI.TableContainer} component=${MUI.Paper} variant="outlined" sx=${{ mb: 2.5 }}>
                            <${MUI.Table} size="small">
                                <${MUI.TableBody}>
                                    ${rows.map(([label, value]) => html`
                                        <${MUI.TableRow} key=${label}>
                                            <${MUI.TableCell} sx=${{ color: 'text.secondary', fontWeight: 600 }}>${label}</${MUI.TableCell}>
                                            <${MUI.TableCell} align="right" className="nht-mono" sx=${{ fontWeight: 600 }}>${value}</${MUI.TableCell}>
                                        </${MUI.TableRow}>
                                    `)}
                                </${MUI.TableBody}>
                            </${MUI.Table}>
                        </${MUI.TableContainer}>
                    `}

                    <${MUI.Typography} variant="caption" color="text.secondary" sx=${{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5 }}>
                        <${MaterialIcon} name="lock" fontSize="small" />
                        Verified live against NHT-SMS database. Personal owner details are withheld under the Kenya Data Protection Act 2019.
                    </${MUI.Typography}>
                </${MUI.CardContent}>
            </${MUI.Card}>
        </${MUI.Box}>
    `;
}

export function ReceiptDetailPage({ me }) {
    const receipt = window.__NHT_BOOTSTRAP__?.page_data?.receipt;
    if (!receipt) {
        return html`<${MUI.Alert} severity="warning">No receipt selected. Open a receipt from Finance or your Member Portal.</${MUI.Alert}>`;
    }

    const brand = receipt.brand || {};
    const tradingName = brand.trading_name || me?.branding?.sacco_name || 'Northern Highways Transporters SACCO';
    const legalName = brand.legal_name || me?.branding?.legal_name || 'SACCO Society Limited';

    return html`
        <${MUI.Box} sx=${{ maxWidth: 820, mx: 'auto' }}>
            <${MUI.Stack} direction="row" justifyContent="space-between" alignItems="center" className="no-print" sx=${{ mb: 2 }}>
                <${MUI.Button} variant="outlined" startIcon=${html`<${MaterialIcon} name="arrow_back" />`} onClick=${() => window.history.back()}>
                    Back
                </${MUI.Button}>
                <${MUI.Stack} direction="row" spacing=${1}>
                    <${MUI.Button} variant="contained" color="secondary" href=${receipt.pdf_url} target="_blank" startIcon=${html`<${MaterialIcon} name="picture_as_pdf" />`}>
                        Download Branded PDF
                    </${MUI.Button}>
                    <${MUI.Button} variant="contained" onClick=${() => window.print()} startIcon=${html`<${MaterialIcon} name="print" />`}>
                        Print Receipt
                    </${MUI.Button}>
                </${MUI.Stack}>
            </${MUI.Stack}>

            <${MUI.Card}>
                <${MUI.CardContent} sx=${{ p: { xs: 2.5, sm: 4 } }}>
                    <${MUI.Box} sx=${{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', pb: 2.5, mb: 2.5, borderBottom: '1px solid', borderColor: 'divider', flexWrap: 'wrap', gap: 2 }}>
                        <${MUI.Stack} direction="row" spacing=${2} alignItems="center">
                            ${brand.logo_url ? html`
                                <img src=${brand.logo_url} alt=${tradingName} style=${{ maxHeight: 52, maxWidth: 140, objectFit: 'contain' }} />
                            ` : html`
                                <${MaterialIcon} name="local_shipping" fontSize="large" color="secondary" />
                            `}
                            <${MUI.Box}>
                                <${MUI.Typography} variant="h5">${tradingName}</${MUI.Typography}>
                                <${MUI.Typography} variant="caption" color="text.secondary">
                                    ${legalName} &bull; Official Financial Secretariat
                                </${MUI.Typography}>
                            </${MUI.Box}>
                        </${MUI.Stack}>
                        <${MUI.Box} sx=${{ textAlign: { xs: 'left', sm: 'right' } }}>
                            <${MUI.Chip} color="success" icon=${html`<${MaterialIcon} name="verified" />`} label="OFFICIAL RECEIPT" size="small" />
                            <${MUI.Typography} className="nht-mono" variant="subtitle1" sx=${{ fontWeight: 700, mt: 0.75 }}>
                                No: ${receipt.receipt_number}
                            </${MUI.Typography}>
                        </${MUI.Box}>
                    </${MUI.Box}>

                    <${MUI.Grid} container spacing=${2} sx=${{ mb: 3 }}>
                        <${MUI.Grid} size=${{ xs: 12, sm: 6 }}>
                            <${MUI.Typography} variant="caption" color="text.secondary" sx=${{ fontWeight: 700, textTransform: 'uppercase' }}>Received From</${MUI.Typography}>
                            <${MUI.Typography} variant="subtitle1" sx=${{ fontWeight: 700 }}>${receipt.member_name}</${MUI.Typography}>
                            <${MUI.Typography} variant="body2" color="text.secondary">Member No: <strong>${receipt.membership_number}</strong></${MUI.Typography}>
                            <${MUI.Typography} variant="body2" color="text.secondary">Phone: ${receipt.phone_number}</${MUI.Typography}>
                        </${MUI.Grid}>
                        <${MUI.Grid} size=${{ xs: 12, sm: 6 }} sx=${{ textAlign: { xs: 'left', sm: 'right' } }}>
                            <${MUI.Typography} variant="caption" color="text.secondary" sx=${{ fontWeight: 700, textTransform: 'uppercase' }}>Settlement Details</${MUI.Typography}>
                            <${MUI.Typography} variant="body2" color="text.secondary">Issued: ${formatDateTime(receipt.issued_at)}</${MUI.Typography}>
                            <${MUI.Typography} variant="body2" color="text.secondary">
                                Method: <${MUI.Chip} size="small" label=${receipt.method} />
                            </${MUI.Typography}>
                            <${MUI.Typography} variant="body2" color="text.secondary">
                                Ref: <span className="nht-mono"><strong>${receipt.reference}</strong></span>
                            </${MUI.Typography}>
                        </${MUI.Grid}>
                    </${MUI.Grid}>

                    <${MUI.TableContainer} component=${MUI.Paper} variant="outlined" sx=${{ mb: 2.5 }}>
                        <${MUI.Table} size="small">
                            <${MUI.TableHead}>
                                <${MUI.TableRow}>
                                    <${MUI.TableCell} sx=${{ fontWeight: 700 }}>Description</${MUI.TableCell}>
                                    <${MUI.TableCell} sx=${{ fontWeight: 700 }}>Invoice Reference</${MUI.TableCell}>
                                    <${MUI.TableCell} align="right" sx=${{ fontWeight: 700 }}>Amount Cleared</${MUI.TableCell}>
                                </${MUI.TableRow}>
                            </${MUI.TableHead}>
                            <${MUI.TableBody}>
                                <${MUI.TableRow}>
                                    <${MUI.TableCell}>Settlement of SACCO Services & Fleet Dues</${MUI.TableCell}>
                                    <${MUI.TableCell} className="nht-mono">${receipt.invoice_number}</${MUI.TableCell}>
                                    <${MUI.TableCell} align="right"><strong>${formatCurrency(receipt.amount)}</strong></${MUI.TableCell}>
                                </${MUI.TableRow}>
                                <${MUI.TableRow}>
                                    <${MUI.TableCell} colSpan=${2} align="right"><strong>Total Cleared</strong></${MUI.TableCell}>
                                    <${MUI.TableCell} align="right" sx=${{ color: 'success.main', fontWeight: 800 }}>${formatCurrency(receipt.amount)}</${MUI.TableCell}>
                                </${MUI.TableRow}>
                                <${MUI.TableRow}>
                                    <${MUI.TableCell} colSpan=${2} align="right">Invoice Outstanding Balance Due</${MUI.TableCell}>
                                    <${MUI.TableCell} align="right" className="nht-mono"><strong>${formatCurrency(receipt.balance_due)}</strong></${MUI.TableCell}>
                                </${MUI.TableRow}>
                            </${MUI.TableBody}>
                        </${MUI.Table}>
                    </${MUI.TableContainer}>

                    <${MUI.Box} sx=${{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', pt: 1.5, borderTop: '1px solid', borderColor: 'divider' }}>
                        <${MUI.Typography} variant="caption" color="text.secondary" sx=${{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                            <${MaterialIcon} name="lock" fontSize="small" color="success" />
                            System-generated verifiable electronic receipt &bull; Ref: ${receipt.payment_reference}
                        </${MUI.Typography}>
                        <${MUI.Typography} variant="caption" color="text.secondary">
                            <strong>SACCO Treasury Office</strong>
                        </${MUI.Typography}>
                    </${MUI.Box}>
                </${MUI.CardContent}>
            </${MUI.Card}>
        </${MUI.Box}>
    `;
}
