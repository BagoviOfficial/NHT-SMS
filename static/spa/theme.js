import { MUI } from './api.js';

export function createNhtTheme(branding = {}) {
    const primaryMain = branding.primary_color || '#10315C';
    const secondaryMain = branding.secondary_color || '#FF8A00';

    return MUI.createTheme({
        palette: {
            mode: 'light',
            primary: {
                main: primaryMain,
                light: '#1B4A8A',
                dark: '#091E38',
                contrastText: '#FFFFFF',
            },
            secondary: {
                main: secondaryMain,
                light: '#FFA733',
                dark: '#D97200',
                contrastText: '#FFFFFF',
            },
            background: {
                default: '#F4F7FA',
                paper: '#FFFFFF',
            },
            success: { main: '#15803D' },
            warning: { main: '#D97706' },
            error: { main: '#B91C1C' },
            info: { main: '#0284C7' },
        },
        typography: {
            fontFamily: "'Plus Jakarta Sans', 'Roboto', sans-serif",
            h4: { fontWeight: 800, letterSpacing: '-0.02em' },
            h5: { fontWeight: 700, letterSpacing: '-0.01em' },
            h6: { fontWeight: 700 },
            button: { textTransform: 'none', fontWeight: 600 },
        },
        shape: {
            borderRadius: 12,
        },
        components: {
            MuiCard: {
                styleOverrides: {
                    root: {
                        borderRadius: 14,
                        boxShadow: '0 2px 12px rgba(16, 49, 92, 0.06)',
                        border: '1px solid rgba(15, 23, 42, 0.06)',
                    },
                },
            },
            MuiButton: {
                styleOverrides: {
                    root: {
                        borderRadius: 10,
                        paddingLeft: 16,
                        paddingRight: 16,
                    },
                },
            },
            MuiChip: {
                styleOverrides: {
                    root: { fontWeight: 600 },
                },
            },
        },
    });
}
