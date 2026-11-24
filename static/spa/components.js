import { React, MUI, html } from './api.js';

export function MaterialIcon({ name, fontSize = 'small', color, sx = {} }) {
    return html`
        <${MUI.Icon} fontSize=${fontSize} color=${color} sx=${sx}>${name}</${MUI.Icon}>
    `;
}

const STATUS_COLOR_MAP = {
    ACTIVE: 'success',
    PAID: 'success',
    SUCCESS: 'success',
    VERIFIED: 'success',
    APPROVED: 'success',
    FULLY_COMPLIANT: 'success',
    HEALTHY: 'success',
    COMPLETED: 'success',
    PASSED: 'success',
    RESOLVED: 'success',
    PENDING: 'warning',
    INITIATED: 'warning',
    EXPIRING_SOON: 'warning',
    IN_PROGRESS: 'info',
    PROCESSING: 'info',
    PARTIALLY_PAID: 'info',
    INVOICED: 'info',
    SUBMITTED: 'info',
    DOC_UPLOADED: 'info',
    DEGRADED: 'warning',
    SUSPENDED: 'error',
    REJECTED: 'error',
    FAILED: 'error',
    DENIED: 'error',
    EXPIRED: 'error',
    NON_COMPLIANT: 'error',
    DOWN: 'error',
    OPEN: 'warning',
    CLOSED: 'default',
    CANCELLED: 'default',
};

export function StatusChip({ value, label }) {
    const key = String(value || '').toUpperCase();
    const color = STATUS_COLOR_MAP[key] || 'default';
    return html`
        <${MUI.Chip}
            size="small"
            color=${color}
            variant=${color === 'default' ? 'outlined' : 'filled'}
            label=${label || value || '—'}
        />
    `;
}

export function PageHeader({ title, subtitle, action }) {
    return html`
        <${MUI.Box}
            sx=${{
                display: 'flex',
                flexDirection: { xs: 'column', sm: 'row' },
                justifyContent: 'space-between',
                alignItems: { xs: 'flex-start', sm: 'center' },
                gap: 2,
                mb: 3,
            }}
        >
            <${MUI.Box}>
                <${MUI.Typography} variant="h5" color="primary.main">${title}</${MUI.Typography}>
                ${subtitle && html`
                    <${MUI.Typography} variant="body2" color="text.secondary">${subtitle}</${MUI.Typography}>
                `}
            </${MUI.Box}>
            ${action && html`<${MUI.Box} sx=${{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>${action}</${MUI.Box}>`}
        </${MUI.Box}>
    `;
}

export function StatCard({ title, value, subtitle, icon, color = 'primary' }) {
    return html`
        <${MUI.Card} sx=${{ height: '100%' }}>
            <${MUI.CardContent} sx=${{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 2 }}>
                <${MUI.Box} sx=${{ minWidth: 0 }}>
                    <${MUI.Typography} variant="caption" color="text.secondary" sx=${{ fontWeight: 700, textTransform: 'uppercase' }}>
                        ${title}
                    </${MUI.Typography}>
                    <${MUI.Typography} variant="h5" sx=${{ mt: 0.5, fontWeight: 800, wordBreak: 'break-word' }}>
                        ${value}
                    </${MUI.Typography}>
                    ${subtitle && html`
                        <${MUI.Typography} variant="caption" color="text.secondary">${subtitle}</${MUI.Typography}>
                    `}
                </${MUI.Box}>
                <${MUI.Avatar} sx=${{ bgcolor: `${color}.light`, color: `${color}.contrastText`, width: 46, height: 46 }}>
                    <${MaterialIcon} name=${icon} fontSize="medium" />
                </${MUI.Avatar}>
            </${MUI.CardContent}>
        </${MUI.Card}>
    `;
}

export function ResponsiveDataGrid({
    columns,
    rows,
    loading = false,
    emptyText = 'No records found.',
    search = '',
    onSearchChange = null,
    searchPlaceholder = 'Search...',
    toolbarExtra = null,
}) {
    const theme = MUI.useTheme();
    const isDesktop = MUI.useMediaQuery(theme.breakpoints.up('md'));

    return html`
        <${MUI.Card}>
            ${(onSearchChange || toolbarExtra) && html`
                <${MUI.Box}
                    sx=${{
                        p: 2,
                        borderBottom: '1px solid rgba(15,23,42,0.08)',
                        display: 'flex',
                        flexDirection: { xs: 'column', sm: 'row' },
                        gap: 1.5,
                        alignItems: { xs: 'stretch', sm: 'center' },
                        justifyContent: 'space-between',
                    }}
                >
                    ${onSearchChange ? html`
                        <${MUI.TextField}
                            size="small"
                            value=${search}
                            onChange=${(e) => onSearchChange(e.target.value)}
                            placeholder=${searchPlaceholder}
                            sx=${{ minWidth: { sm: 260 } }}
                            InputProps=${{
                                startAdornment: html`
                                    <${MUI.InputAdornment} position="start">
                                        <${MaterialIcon} name="search" />
                                    </${MUI.InputAdornment}>
                                `,
                            }}
                        />
                    ` : html`<span />`}
                    ${toolbarExtra && html`<${MUI.Box} sx=${{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>${toolbarExtra}</${MUI.Box}>`}
                </${MUI.Box}>
            `}

            ${loading ? html`
                <${MUI.Box} sx=${{ p: 4, display: 'flex', justifyContent: 'center' }}>
                    <${MUI.CircularProgress} />
                </${MUI.Box}>
            ` : (!rows || rows.length === 0) ? html`
                <${MUI.Box} sx=${{ p: 4, textAlign: 'center' }}>
                    <${MUI.Typography} color="text.secondary">${emptyText}</${MUI.Typography}>
                </${MUI.Box}>
            ` : isDesktop ? html`
                <${MUI.TableContainer}>
                    <${MUI.Table} size="small">
                        <${MUI.TableHead} sx=${{ bgcolor: '#F8FAFC' }}>
                            <${MUI.TableRow}>
                                ${columns.map((col) => html`
                                    <${MUI.TableCell}
                                        key=${col.key}
                                        align=${col.align || 'left'}
                                        sx=${{ fontWeight: 700, color: 'text.secondary', py: 1.5 }}
                                    >
                                        ${col.label}
                                    </${MUI.TableCell}>
                                `)}
                            </${MUI.TableRow}>
                        </${MUI.TableHead}>
                        <${MUI.TableBody}>
                            ${rows.map((row, idx) => html`
                                <${MUI.TableRow} key=${row.id || idx} hover>
                                    ${columns.map((col) => html`
                                        <${MUI.TableCell} key=${col.key} align=${col.align || 'left'} sx=${{ py: 1.4 }}>
                                            ${col.render ? col.render(row) : (row[col.key] ?? '—')}
                                        </${MUI.TableCell}>
                                    `)}
                                </${MUI.TableRow}>
                            `)}
                        </${MUI.TableBody}>
                    </${MUI.Table}>
                </${MUI.TableContainer}>
            ` : html`
                <${MUI.Stack} spacing=${1.5} sx=${{ p: 1.5 }}>
                    ${rows.map((row, idx) => html`
                        <${MUI.Paper} key=${row.id || idx} variant="outlined" sx=${{ p: 2, borderRadius: 3 }}>
                            <${MUI.Stack} spacing=${1}>
                                ${columns.map((col) => html`
                                    <${MUI.Box}
                                        key=${col.key}
                                        sx=${{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}
                                    >
                                        <${MUI.Typography} variant="caption" color="text.secondary" sx=${{ fontWeight: 700 }}>
                                            ${col.label}
                                        </${MUI.Typography}>
                                        <${MUI.Box} sx=${{ textAlign: 'right' }}>
                                            ${col.render ? col.render(row) : (row[col.key] ?? '—')}
                                        </${MUI.Box}>
                                    </${MUI.Box}>
                                `)}
                            </${MUI.Stack}>
                        </${MUI.Paper}>
                    `)}
                </${MUI.Stack}>
            `}
        </${MUI.Card}>
    `;
}

export function ResponsiveDialog({ open, onClose, title, children, actions, maxWidth = 'sm' }) {
    const theme = MUI.useTheme();
    const fullScreen = MUI.useMediaQuery(theme.breakpoints.down('sm'));

    return html`
        <${MUI.Dialog} open=${open} onClose=${onClose} fullWidth maxWidth=${maxWidth} fullScreen=${fullScreen}>
            <${MUI.DialogTitle} sx=${{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontWeight: 700 }}>
                <span>${title}</span>
                <${MUI.IconButton} onClick=${onClose} size="small">
                    <${MaterialIcon} name="close" />
                </${MUI.IconButton}>
            </${MUI.DialogTitle}>
            <${MUI.DialogContent} dividers>${children}</${MUI.DialogContent}>
            ${actions && html`<${MUI.DialogActions} sx=${{ p: 2 }}>${actions}</${MUI.DialogActions}>`}
        </${MUI.Dialog}>
    `;
}
