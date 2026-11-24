export const React = window.React;
export const ReactDOM = window.ReactDOM;
export const MUI = window.MaterialUI;
export const html = window.htm.bind(React.createElement);

let cachedCsrfToken = '';

export function getCookie(name) {
    const cookies = document.cookie ? document.cookie.split(';') : [];
    for (let i = 0; i < cookies.length; i++) {
        const c = cookies[i].trim();
        if (c.startsWith(name + '=')) {
            return decodeURIComponent(c.substring(name.length + 1));
        }
    }
    return '';
}

export function getCsrfToken() {
    if (cachedCsrfToken) return cachedCsrfToken;
    const cookieToken = getCookie('csrftoken');
    if (cookieToken) return cookieToken;
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? (meta.getAttribute('content') || '') : '';
}

export async function apiFetch(url, options = {}) {
    const opts = {
        credentials: 'same-origin',
        headers: { ...(options.headers || {}) },
        ...options,
    };

    const method = (opts.method || 'GET').toUpperCase();
    if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
        opts.headers['X-CSRFToken'] = getCsrfToken();
    }

    if (opts.body && !(opts.body instanceof FormData) && typeof opts.body !== 'string') {
        opts.headers['Content-Type'] = 'application/json';
        opts.body = JSON.stringify(opts.body);
    }

    const res = await fetch(url, opts);
    const contentType = res.headers.get('content-type') || '';
    const data = contentType.includes('application/json') ? await res.json() : await res.text();

    if (data && typeof data === 'object' && data.csrf_token) {
        cachedCsrfToken = data.csrf_token;
    }

    if (!res.ok) {
        let msg = `Request failed (${res.status})`;
        if (data && typeof data === 'object') {
            msg = data.error || data.detail || Object.values(data).flat().join(' ') || msg;
        }
        const err = new Error(msg);
        err.status = res.status;
        err.data = data;
        throw err;
    }
    return data;
}

export function extractList(data) {
    if (Array.isArray(data)) return data;
    if (data && Array.isArray(data.results)) return data.results;
    return [];
}

export function formatCurrency(amount, currency = null) {
    const curr = currency || (window.__NHT_BOOTSTRAP__ && window.__NHT_BOOTSTRAP__.currency) || 'KES';
    const num = Number(amount || 0);
    return `${curr} ${num.toLocaleString('en-KE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function formatDateTime(iso) {
    if (!iso) return '—';
    try {
        return new Date(iso).toLocaleString('en-KE', {
            year: 'numeric',
            month: 'short',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
        });
    } catch {
        return String(iso);
    }
}
