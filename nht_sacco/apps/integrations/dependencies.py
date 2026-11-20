import logging
from typing import Dict, Any, List
from django.utils import timezone

logger = logging.getLogger(__name__)


class ConfigurationDependencyRegistry:
    """
    Registry for evaluating operational dependencies and assessing risk impact
    before applying changes to critical system configurations.
    Enforces that business and financial policy changes do not silently alter historical records.
    """

    DEPENDENCY_RULES = {
        'business.currency': {
            'risk_level': 'CRITICAL',
            'requires_approval': True,
            'affected_modules': ['accounting', 'billing', 'payments', 'reports'],
            'warnings': [
                "Changing SACCO operating currency impacts financial statements, trial balances, and active invoices.",
                "Historical ledger journal entries will retain their original denomination.",
                "Verify currency code matches national regulations before activation."
            ],
        },
        'mpesa.business_shortcode': {
            'risk_level': 'CRITICAL',
            'requires_approval': True,
            'affected_modules': ['payments', 'daraja', 'billing'],
            'warnings': [
                "Changing M-Pesa Shortcode requires revalidation of Daraja STK Push and C2B callback URLs on Safaricom Developer Portal.",
                "In-flight payments using prior shortcode will not match incoming webhook notifications.",
            ],
        },
        'mpesa.environment': {
            'risk_level': 'CRITICAL',
            'requires_approval': True,
            'affected_modules': ['payments', 'daraja'],
            'warnings': [
                "Switching M-Pesa environment alters live financial gateway endpoints.",
                "Production mode strictly forbids simulated gateway responses.",
            ],
        },
        'sms.provider': {
            'risk_level': 'HIGH',
            'requires_approval': True,
            'affected_modules': ['notifications', 'accounts', 'renewals'],
            'warnings': [
                "Modifying SMS provider affects member OTP authentication and renewal reminders.",
                "Ensure valid API credentials and approved Sender ID exist before switching.",
            ],
        },
        'business.invoice_prefix': {
            'risk_level': 'HIGH',
            'requires_approval': False,
            'affected_modules': ['billing', 'accounting'],
            'warnings': [
                "Invoice numbering prefix change will apply to all subsequent generated bills.",
            ],
        },
        'business.default_interest_rate': {
            'risk_level': 'HIGH',
            'requires_approval': True,
            'affected_modules': ['accounting', 'loans'],
            'warnings': [
                "Interest rate modifications apply strictly to new loan contracts.",
                "Historical and active loan schedules remain fixed and immutable.",
            ],
        },
        'business.min_monthly_contribution': {
            'risk_level': 'MEDIUM',
            'requires_approval': False,
            'affected_modules': ['members', 'billing'],
            'warnings': [
                "New contribution minimums take effect prospectively in future billing cycles.",
                "Historical membership compliance records are preserved without retrospective penalty.",
            ],
        },
        'security.mfa_enforcement': {
            'risk_level': 'HIGH',
            'requires_approval': True,
            'affected_modules': ['accounts', 'security'],
            'warnings': [
                "Elevating MFA policy locks out staff/users lacking configured TOTP authenticator devices.",
            ],
        },
    }

    @classmethod
    def assess_impact(cls, key: str, proposed_value: Any) -> Dict[str, Any]:
        """
        Assesses the operational risk and dependencies for a proposed configuration mutation.
        Returns risk metadata, warnings, affected modules, and approval status.
        """
        rule = cls.DEPENDENCY_RULES.get(key, {
            'risk_level': 'LOW',
            'requires_approval': False,
            'affected_modules': [],
            'warnings': [],
        })

        warnings = list(rule.get('warnings', []))
        risk_level = rule.get('risk_level', 'LOW')
        requires_approval = rule.get('requires_approval', False)
        affected_modules = list(rule.get('affected_modules', []))

        # Dynamic validation for invoice prefix collisions
        if key == 'business.invoice_prefix':
            try:
                from nht_sacco.apps.billing.models import Invoice
                year = timezone.now().year
                prefix_query = f"{proposed_value}-{year}"
                if Invoice.objects.filter(invoice_number__startswith=prefix_query).exists():
                    warnings.append(
                        f"Notice: Invoices already exist with prefix '{proposed_value}' for year {year}. "
                        "Sequential numbering will resume from the highest existing sequence."
                    )
            except Exception as e:
                logger.warning(f"Error checking invoice prefix collision: {str(e)}")

        return {
            'key': key,
            'proposed_value': str(proposed_value),
            'risk_level': risk_level,
            'requires_approval': requires_approval,
            'affected_modules': affected_modules,
            'warnings': warnings,
            'timestamp': timezone.now().isoformat(),
        }
