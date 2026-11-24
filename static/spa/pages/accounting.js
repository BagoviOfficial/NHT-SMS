import { React, MUI, html, apiFetch, extractList, formatCurrency } from '../api.js';
import { MaterialIcon, PageHeader, ResponsiveDataGrid, ResponsiveDialog, StatusChip } from '../components.js';

export function AccountingPage({ notify }) {
    const [tab, setTab] = React.useState(0);
    const [accounts, setAccounts] = React.useState([]);
    const [journals, setJournals] = React.useState([]);
    const [expenses, setExpenses] = React.useState([]);
    const [periods, setPeriods] = React.useState([]);
    const [reports, setReports] = React.useState(null);
    const [loading, setLoading] = React.useState(true);
    const [expOpen, setExpOpen] = React.useState(false);
    const [expForm, setExpForm] = React.useState({ category: '', payment_account: '', amount: '', payee: '', description: '' });

    const load = React.useCallback(async () => {
        setLoading(true);
        try {
            const [aRes, jRes, eRes, pRes, rRes] = await Promise.all([
                apiFetch('/api/v1/accounts/'),
                apiFetch('/api/v1/journals/'),
                apiFetch('/api/v1/expenses/'),
                apiFetch('/api/v1/financial-periods/'),
                apiFetch('/api/v1/accounting/reports/'),
            ]);
            setAccounts(extractList(aRes));
            setJournals(extractList(jRes));
            setExpenses(extractList(eRes));
            setPeriods(extractList(pRes));
            setReports(rRes);
        } catch (err) {
            notify(err.message, 'error');
        } finally {
            setLoading(false);
        }
    }, [notify]);

    React.useEffect(() => { load(); }, [load]);

    const handleCreateExpense = async () => {
        try {
            await apiFetch('/api/v1/expenses/', { method: 'POST', body: expForm });
            notify('Expense claim submitted (Maker stage).', 'success');
            setExpOpen(false);
            load();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const doExpenseAction = async (id, act) => {
        try {
            await apiFetch(`/api/v1/expenses/${id}/${act}/`, { method: 'POST', body: {} });
            notify(`Expense ${act}d.`, 'success');
            load();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    const togglePeriod = async (p) => {
        const endpoint = p.is_closed ? 'reopen' : 'close';
        try {
            await apiFetch(`/api/v1/financial-periods/${p.id}/${endpoint}/`, { method: 'POST', body: {} });
            notify(`Period ${p.name} ${endpoint}d.`, 'success');
            load();
        } catch (err) {
            notify(err.message, 'error');
        }
    };

    return html`
        <${MUI.Box}>
            <${PageHeader}
                title="General Ledger & Financial Statements"
                subtitle="Double-entry Chart of Accounts, Journal Entries, Maker-Checker Expenses, Periods & Statements."
                action=${html`
                    <${MUI.Button} variant="contained" startIcon=${html`<${MaterialIcon} name="receipt" />`} onClick=${() => setExpOpen(true)}>
                        Record Expense (Maker)
                    </${MUI.Button}>
                `}
            />

            <${MUI.Tabs} value=${tab} onChange=${(_, v) => setTab(v)} variant="scrollable" scrollButtons="auto" sx=${{ mb: 2 }}>
                <${MUI.Tab} label="Financial Statements" />
                <${MUI.Tab} label="Chart of Accounts" />
                <${MUI.Tab} label="Journal Entries" />
                <${MUI.Tab} label="Expenses" />
                <${MUI.Tab} label="Periods" />
            </${MUI.Tabs}>

            ${tab === 0 && reports && html`
                <${MUI.Grid} container spacing=${2.5}>
                    <${MUI.Grid} item xs=${12} md=${6}>
                        <${MUI.Card} sx=${{ p: 2.5 }}>
                            <${MUI.Box} sx=${{ display: 'flex', justifyContent: 'space-between', mb: 1.5 }}>
                                <${MUI.Typography} variant="h6">Income & Expenditure</${MUI.Typography}>
                                <${StatusChip} value=${Number(reports.income_and_expenditure.net_surplus) >= 0 ? 'SUCCESS' : 'PENDING'} label="Net: ${formatCurrency(reports.income_and_expenditure.net_surplus)}" />
                            </${MUI.Box}>
                            <${MUI.Typography} variant="body2">Total Revenue: <strong>${formatCurrency(reports.income_and_expenditure.total_revenue)}</strong></${MUI.Typography}>
                            <${MUI.Typography} variant="body2">Total Expenses: <strong>${formatCurrency(reports.income_and_expenditure.total_expenses)}</strong></${MUI.Typography}>
                        </${MUI.Card}>
                    </${MUI.Grid}>
                    <${MUI.Grid} item xs=${12} md=${6}>
                        <${MUI.Card} sx=${{ p: 2.5 }}>
                            <${MUI.Box} sx=${{ display: 'flex', justifyContent: 'space-between', mb: 1.5 }}>
                                <${MUI.Typography} variant="h6">Balance Sheet</${MUI.Typography}>
                                <${StatusChip} value=${reports.balance_sheet.is_balanced ? 'VERIFIED' : 'REJECTED'} label=${reports.balance_sheet.is_balanced ? 'Balanced' : 'Unbalanced'} />
                            </${MUI.Box}>
                            <${MUI.Typography} variant="body2">Total Assets: <strong>${formatCurrency(reports.balance_sheet.total_assets)}</strong></${MUI.Typography}>
                            <${MUI.Typography} variant="body2">Liabilities + Equity: <strong>${formatCurrency(reports.balance_sheet.total_liabilities_and_equity)}</strong></${MUI.Typography}>
                        </${MUI.Card}>
                    </${MUI.Grid}>
                    <${MUI.Grid} item xs=${12}>
                        <${MUI.Typography} variant="h6" sx=${{ mb: 1 }}>
                            Trial Balance (Debits: ${formatCurrency(reports.trial_balance.total_debits)} | Credits: ${formatCurrency(reports.trial_balance.total_credits)})
                        </${MUI.Typography}>
                        <${ResponsiveDataGrid}
                            rows=${reports.trial_balance.lines || []}
                            columns=${[
                                { key: 'code', label: 'Code', render: (r) => html`<span class="nht-mono">${r.code}</span>` },
                                { key: 'name', label: 'Account' },
                                { key: 'type', label: 'Type' },
                                { key: 'debit', label: 'Debits', align: 'right', render: (r) => formatCurrency(r.debit) },
                                { key: 'credit', label: 'Credits', align: 'right', render: (r) => formatCurrency(r.credit) },
                                { key: 'balance', label: 'Balance', align: 'right', render: (r) => formatCurrency(r.balance) },
                            ]}
                        />
                    </${MUI.Grid}>
                </${MUI.Grid}>
            `}

            ${tab === 1 && html`
                <${ResponsiveDataGrid}
                    loading=${loading}
                    rows=${accounts}
                    columns=${[
                        { key: 'code', label: 'Code', render: (r) => html`<span class="nht-mono">${r.code}</span>` },
                        { key: 'name', label: 'Name' },
                        { key: 'type_display', label: 'Type' },
                        { key: 'current_balance', label: 'Balance', align: 'right', render: (r) => formatCurrency(r.current_balance) },
                    ]}
                />
            `}

            ${tab === 2 && html`
                <${ResponsiveDataGrid}
                    loading=${loading}
                    rows=${journals}
                    columns=${[
                        { key: 'entry_number', label: 'Entry #', render: (r) => html`<span class="nht-mono">${r.entry_number}</span>` },
                        { key: 'date', label: 'Date' },
                        { key: 'reference', label: 'Reference' },
                        { key: 'narration', label: 'Narration' },
                        { key: 'period_name', label: 'Period' },
                        { key: 'is_reversal', label: 'Type', render: (r) => html`<${StatusChip} value=${r.is_reversal ? 'WARNING' : 'VERIFIED'} label=${r.is_reversal ? 'Reversal' : 'Posted'} />` },
                    ]}
                />
            `}

            ${tab === 3 && html`
                <${ResponsiveDataGrid}
                    loading=${loading}
                    rows=${expenses}
                    columns=${[
                        { key: 'expense_number', label: 'Voucher #', render: (r) => html`<span class="nht-mono">${r.expense_number}</span>` },
                        { key: 'payee', label: 'Payee' },
                        { key: 'category_name', label: 'Expense Account' },
                        { key: 'amount', label: 'Amount', align: 'right', render: (r) => formatCurrency(r.amount) },
                        { key: 'recorded_by_username', label: 'Maker' },
                        { key: 'status', label: 'Status', render: (r) => html`<${StatusChip} value=${r.status} />` },
                        {
                            key: 'actions',
                            label: 'Checker',
                            align: 'right',
                            render: (r) => r.status === 'PENDING' && html`
                                <${MUI.Stack} direction="row" spacing=${0.5} justifyContent="flex-end">
                                    <${MUI.Button} size="small" color="success" onClick=${() => doExpenseAction(r.id, 'approve')}>Approve</${MUI.Button}>
                                    <${MUI.Button} size="small" color="error" onClick=${() => doExpenseAction(r.id, 'reject')}>Reject</${MUI.Button}>
                                </${MUI.Stack}>
                            `,
                        },
                    ]}
                />
            `}

            ${tab === 4 && html`
                <${ResponsiveDataGrid}
                    loading=${loading}
                    rows=${periods}
                    columns=${[
                        { key: 'name', label: 'Period' },
                        { key: 'start_date', label: 'Start' },
                        { key: 'end_date', label: 'End' },
                        { key: 'is_closed', label: 'Status', render: (r) => html`<${StatusChip} value=${r.is_closed ? 'CLOSED' : 'ACTIVE'} label=${r.is_closed ? 'Closed' : 'Open'} />` },
                        {
                            key: 'actions',
                            label: 'Action',
                            align: 'right',
                            render: (r) => html`
                                <${MUI.Button} size="small" onClick=${() => togglePeriod(r)}>
                                    ${r.is_closed ? 'Reopen' : 'Close Period'}
                                </${MUI.Button}>
                            `,
                        },
                    ]}
                />
            `}

            <${ResponsiveDialog}
                open=${expOpen}
                onClose=${() => setExpOpen(false)}
                title="Record Operating Expense Claim"
                actions=${html`
                    <${MUI.Button} onClick=${() => setExpOpen(false)}>Cancel</${MUI.Button}>
                    <${MUI.Button} variant="contained" onClick=${handleCreateExpense}>Submit Claim</${MUI.Button}>
                `}
            >
                <${MUI.Stack} spacing=${2} sx=${{ pt: 1 }}>
                    <${MUI.TextField} select label="Expense Account (Dr)" fullWidth value=${expForm.category} onChange=${(e) => setExpForm({ ...expForm, category: e.target.value })}>
                        ${accounts.filter((a) => a.type === 'EXPENSE').map((a) => html`<${MUI.MenuItem} key=${a.id} value=${a.id}>${a.code} — ${a.name}</${MUI.MenuItem}>`)}
                    </${MUI.TextField}>
                    <${MUI.TextField} select label="Disbursement Account (Cr)" fullWidth value=${expForm.payment_account} onChange=${(e) => setExpForm({ ...expForm, payment_account: e.target.value })}>
                        ${accounts.filter((a) => a.type === 'ASSET').map((a) => html`<${MUI.MenuItem} key=${a.id} value=${a.id}>${a.code} — ${a.name}</${MUI.MenuItem}>`)}
                    </${MUI.TextField}>
                    <${MUI.TextField} label="Payee" fullWidth value=${expForm.payee} onChange=${(e) => setExpForm({ ...expForm, payee: e.target.value })} />
                    <${MUI.TextField} label="Amount (KES)" type="number" fullWidth value=${expForm.amount} onChange=${(e) => setExpForm({ ...expForm, amount: e.target.value })} />
                    <${MUI.TextField} label="Description" fullWidth multiline rows=${2} value=${expForm.description} onChange=${(e) => setExpForm({ ...expForm, description: e.target.value })} />
                </${MUI.Stack}>
            </${ResponsiveDialog}>
        </${MUI.Box}>
    `;
}
