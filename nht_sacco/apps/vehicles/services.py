import logging
from datetime import timedelta
from django.db import transaction
from django.utils import timezone

from nht_sacco.apps.audit.models import AuditAction, AuditLog, AuditOutcome
from nht_sacco.apps.compliance.models import ComplianceStatus
from nht_sacco.apps.compliance.services import ComplianceService
from nht_sacco.apps.integrations.crypto import CryptoService
from nht_sacco.apps.integrations.models import CompanyProfile
from .models import ComplianceCardStatus, VehicleComplianceCard, VehicleStatus
from .qr import generate_qr_base64, generate_qr_png_bytes

logger = logging.getLogger(__name__)


class ComplianceCardService:
    """
    Lifecycle & Cryptographic QR Verification Service for VehicleComplianceCard.
    - Tokens are generated using `secrets.token_urlsafe(32)`.
    - Only SHA-256 hashes are indexed/validated on verification (`token_hash`).
    - Encrypted token copy (`encrypted_token`) is kept via AES-256 Fernet for authorized
      reprinting/PDF export and is immediately invalidated on `regenerate_qr`.
    """

    @staticmethod
    def resolve_public_base_url(request=None) -> str:
        """
        Resolves the internal verification base URL from the active request when
        available, returning '' (relative path) when no request is supplied.
        """
        if request is not None:
            return request.build_absolute_uri('/').rstrip('/')
        profile = CompanyProfile.get_active()
        base = (profile.public_base_url or '').strip().rstrip('/')
        if base and base != 'https://nhtsms.bagovi.com':
            return base
        return ''

    @classmethod
    def decrypt_token(cls, card: VehicleComplianceCard) -> str:
        if not card.encrypted_token:
            return ''
        return CryptoService.decrypt(card.encrypted_token)

    @classmethod
    def get_verify_url(cls, card: VehicleComplianceCard, raw_token: str = '', request=None) -> str:
        token = raw_token or cls.decrypt_token(card)
        if not token:
            return ''
        base = cls.resolve_public_base_url(request=request)
        if base:
            return f"{base}/verify/compliance/{token}/"
        return f"/verify/compliance/{token}/"

    @classmethod
    def get_qr_png_bytes(cls, card: VehicleComplianceCard, raw_token: str = '', request=None) -> bytes:
        url = cls.get_verify_url(card, raw_token=raw_token, request=request)
        if not url:
            return b''
        return generate_qr_png_bytes(url)

    @classmethod
    def get_qr_data_uri(cls, card: VehicleComplianceCard, raw_token: str = '', request=None) -> str:
        url = cls.get_verify_url(card, raw_token=raw_token, request=request)
        if not url:
            return ''
        return generate_qr_base64(url)

    @classmethod
    @transaction.atomic
    def issue_card(cls, vehicle, issued_by=None, expiry_date=None, fleet_number='', notes='', supersede_existing=True):
        today = timezone.localdate()
        if expiry_date is None:
            expiry_date = today + timedelta(days=365)

        raw_token = VehicleComplianceCard.generate_raw_token()
        token_hash = VehicleComplianceCard.hash_token(raw_token)
        encrypted_token = CryptoService.encrypt(raw_token)

        active_route = vehicle.route_allocations.filter(is_active=True).select_related('route').first()
        route_label = f"{active_route.route.route_code}: {active_route.route.name}" if (active_route and active_route.route) else "Unassigned"
        owner_name = vehicle.current_owner.full_name if vehicle.current_owner else ""
        branding_version = CompanyProfile.get_active().get_latest_version()

        card = VehicleComplianceCard.objects.create(
            vehicle=vehicle,
            certificate_number=VehicleComplianceCard.generate_certificate_number(),
            fleet_number=fleet_number or f"FLT-{vehicle.registration_number.replace(' ', '')}",
            owner_display_name=owner_name,
            assigned_route_name=route_label,
            token_hash=token_hash,
            token_hint=raw_token[:10],
            encrypted_token=encrypted_token,
            status=ComplianceCardStatus.VALID,
            issue_date=today,
            expiry_date=expiry_date,
            issued_by=issued_by if (issued_by and getattr(issued_by, 'is_authenticated', False)) else None,
            branding_version=branding_version,
            notes=notes,
        )

        if supersede_existing:
            VehicleComplianceCard.objects.filter(
                vehicle=vehicle,
                status=ComplianceCardStatus.VALID,
            ).exclude(pk=card.pk).update(
                status=ComplianceCardStatus.SUPERSEDED,
                superseded_by=card,
                updated_at=timezone.now(),
            )

        AuditLog.log_action(
            actor=issued_by,
            action=AuditAction.CREATE,
            entity_type='VehicleComplianceCard',
            entity_id=card.certificate_number,
            outcome=AuditOutcome.SUCCESS,
            notes=f"Issued compliance card {card.certificate_number} for {vehicle.registration_number} (exp {expiry_date})",
        )
        return card, raw_token

    @classmethod
    @transaction.atomic
    def renew_card(cls, old_card: VehicleComplianceCard, issued_by=None, expiry_date=None, notes=''):
        new_card, raw_token = cls.issue_card(
            vehicle=old_card.vehicle,
            issued_by=issued_by,
            expiry_date=expiry_date,
            fleet_number=old_card.fleet_number,
            notes=notes or f"Renewal of {old_card.certificate_number}",
            supersede_existing=False,
        )
        old_card.status = ComplianceCardStatus.SUPERSEDED
        old_card.superseded_by = new_card
        old_card.save(update_fields=['status', 'superseded_by', 'updated_at'])

        AuditLog.log_action(
            actor=issued_by,
            action=AuditAction.UPDATE,
            entity_type='VehicleComplianceCard',
            entity_id=old_card.certificate_number,
            outcome=AuditOutcome.SUCCESS,
            notes=f"Renewed {old_card.certificate_number} -> {new_card.certificate_number}",
        )
        return new_card, raw_token

    @classmethod
    @transaction.atomic
    def revoke_card(cls, card: VehicleComplianceCard, revoked_by=None, reason=''):
        card.status = ComplianceCardStatus.REVOKED
        card.revoked_by = revoked_by if (revoked_by and getattr(revoked_by, 'is_authenticated', False)) else None
        card.revoked_at = timezone.now()
        card.revocation_reason = reason or 'Administrative revocation'
        card.save(update_fields=['status', 'revoked_by', 'revoked_at', 'revocation_reason', 'updated_at'])

        AuditLog.log_action(
            actor=revoked_by,
            action=AuditAction.UPDATE,
            entity_type='VehicleComplianceCard',
            entity_id=card.certificate_number,
            outcome=AuditOutcome.SUCCESS,
            notes=f"Revoked compliance card {card.certificate_number}: {card.revocation_reason}",
        )
        return card

    @classmethod
    @transaction.atomic
    def suspend_card(cls, card: VehicleComplianceCard, actor=None, reason=''):
        card.status = ComplianceCardStatus.SUSPENDED
        if reason:
            card.notes = f"{card.notes}\nSuspended: {reason}".strip()
        card.save(update_fields=['status', 'notes', 'updated_at'])
        AuditLog.log_action(
            actor=actor,
            action=AuditAction.UPDATE,
            entity_type='VehicleComplianceCard',
            entity_id=card.certificate_number,
            outcome=AuditOutcome.SUCCESS,
            notes=f"Suspended compliance card {card.certificate_number}: {reason or 'Compliance hold'}",
        )
        return card

    @classmethod
    @transaction.atomic
    def reinstate_card(cls, card: VehicleComplianceCard, actor=None, notes=''):
        today = timezone.localdate()
        card.status = ComplianceCardStatus.EXPIRED if card.expiry_date < today else ComplianceCardStatus.VALID
        if notes:
            card.notes = f"{card.notes}\nReinstated: {notes}".strip()
        card.save(update_fields=['status', 'notes', 'updated_at'])
        AuditLog.log_action(
            actor=actor,
            action=AuditAction.UPDATE,
            entity_type='VehicleComplianceCard',
            entity_id=card.certificate_number,
            outcome=AuditOutcome.SUCCESS,
            notes=f"Reinstated compliance card {card.certificate_number} -> {card.status}",
        )
        return card

    @classmethod
    @transaction.atomic
    def regenerate_qr(cls, card: VehicleComplianceCard, actor=None):
        """
        Rotates the cryptographic QR verification token for a card, immediately
        invalidating any previously printed QR token.
        """
        raw_token = VehicleComplianceCard.generate_raw_token()
        card.token_hash = VehicleComplianceCard.hash_token(raw_token)
        card.token_hint = raw_token[:10]
        card.encrypted_token = CryptoService.encrypt(raw_token)
        card.save(update_fields=['token_hash', 'token_hint', 'encrypted_token', 'updated_at'])

        AuditLog.log_action(
            actor=actor,
            action=AuditAction.UPDATE,
            entity_type='VehicleComplianceCard',
            entity_id=card.certificate_number,
            outcome=AuditOutcome.SUCCESS,
            notes=f"Regenerated QR verification token for {card.certificate_number}",
        )
        return card, raw_token

    @classmethod
    def evaluate_live_status(cls, raw_token: str) -> dict:
        """
        Validates a raw verification token against live database records.
        Never trusts printed card data and returns strictly non-PII attributes.
        Outcomes: VALID, EXPIRED, REVOKED, SUSPENDED, SUPERSEDED, INVALID.
        """
        clean_token = (raw_token or '').strip()
        profile = CompanyProfile.get_active()
        sacco_logo_url = '/settings/api/v1/company-profile/logo-asset/' if (profile.logo and profile.logo.name) else ''
        base_meta = {
            'sacco_name': profile.trading_name,
            'sacco_legal_name': profile.legal_name,
            'sacco_logo_url': sacco_logo_url,
            'verified_at': timezone.now(),
        }

        if len(clean_token) < 16 or len(clean_token) > 128:
            return {
                **base_meta,
                'outcome': 'INVALID',
                'is_valid': False,
                'headline': 'Invalid Compliance Token',
                'detail': 'The scanned QR token does not match any active or historical NHT-SMS compliance certificate.',
                'card': None,
            }

        token_hash = VehicleComplianceCard.hash_token(clean_token)
        card = (
            VehicleComplianceCard.objects
            .select_related('vehicle', 'branding_version')
            .filter(token_hash=token_hash)
            .first()
        )
        if not card:
            return {
                **base_meta,
                'outcome': 'INVALID',
                'is_valid': False,
                'headline': 'Unrecognized Compliance Certificate',
                'detail': 'No compliance certificate was found for this QR verification token.',
                'card': None,
            }

        today = timezone.localdate()
        vehicle = card.vehicle
        comp = ComplianceService.get_vehicle_compliance_status(vehicle)

        if card.status == ComplianceCardStatus.REVOKED:
            outcome = 'REVOKED'
            headline = 'Certificate Revoked'
            detail = 'This compliance certificate has been officially revoked and is no longer valid.'
        elif card.status == ComplianceCardStatus.SUPERSEDED:
            outcome = 'SUPERSEDED'
            headline = 'Certificate Superseded'
            detail = 'This compliance card has been replaced by a newer certificate.'
        elif card.status == ComplianceCardStatus.SUSPENDED or vehicle.status == VehicleStatus.SUSPENDED:
            outcome = 'SUSPENDED'
            headline = 'Vehicle / Certificate Suspended'
            detail = 'This vehicle or compliance certificate is currently suspended from SACCO operations.'
        elif card.status == ComplianceCardStatus.EXPIRED or card.expiry_date < today or comp.get('expired_docs'):
            outcome = 'EXPIRED'
            headline = 'Certificate Expired'
            detail = 'The validity period or underlying regulatory permits for this certificate have expired.'
        elif vehicle.status != VehicleStatus.ACTIVE:
            outcome = 'SUSPENDED'
            headline = f'Vehicle {vehicle.get_status_display()}'
            detail = 'Vehicle is not currently active in SACCO service.'
        else:
            outcome = 'VALID'
            headline = 'Valid Compliance Certificate'
            detail = 'Verified live against SACCO registry. All certificate checks passed.'

        active_route = vehicle.route_allocations.filter(is_active=True).select_related('route').first()
        route_display = (
            f"{active_route.route.route_code}: {active_route.route.name}"
            if (active_route and active_route.route)
            else (card.assigned_route_name or 'Unassigned')
        )

        return {
            **base_meta,
            'outcome': outcome,
            'is_valid': outcome == 'VALID',
            'headline': headline,
            'detail': detail,
            'card': {
                'certificate_number': card.certificate_number,
                'registration_number': vehicle.registration_number,
                'make_model': f"{vehicle.make} {vehicle.model}",
                'category': vehicle.get_category_display(),
                'carrying_capacity': vehicle.carrying_capacity,
                'fleet_number': card.fleet_number,
                'assigned_route': route_display,
                'issue_date': card.issue_date,
                'expiry_date': card.expiry_date,
                'vehicle_status': vehicle.get_status_display(),
            },
        }
