import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from nht_sacco.apps.accounts.models import UserRole, LoginHistory
from nht_sacco.apps.audit.models import AuditLog, AuditAction, AuditOutcome

User = get_user_model()

@pytest.mark.django_db
class TestUserModel:
    def test_create_user_with_uuid(self):
        user = User.objects.create_user(
            username='officer1',
            email='officer1@nhttransporters.co.ke',
            password='StrongPassword123!',
            role=UserRole.COMPLIANCE_OFFICER,
            phone_number='+254712345678',
            national_id='12345678'
        )
        assert user.pk is not None
        assert str(user.pk) != ''
        assert user.role == UserRole.COMPLIANCE_OFFICER
        assert user.is_compliance_staff is True
        assert user.is_management_staff is True
        assert user.is_financial_staff is False
        assert user.is_member is False

    def test_member_role_flags(self):
        member_user = User.objects.create_user(
            username='member1',
            email='member1@nhttransporters.co.ke',
            password='MemberPassword123!',
            role=UserRole.MEMBER
        )
        assert member_user.is_member is True
        assert member_user.is_management_staff is False
        assert member_user.is_financial_staff is False

    def test_financial_role_flags(self):
        treasurer = User.objects.create_user(
            username='treasurer1',
            email='treasurer1@nhttransporters.co.ke',
            password='TreasurerPassword123!',
            role=UserRole.TREASURER
        )
        assert treasurer.is_financial_staff is True
        assert treasurer.is_management_staff is True


@pytest.mark.django_db
class TestAuditLog:
    def test_audit_log_creation(self):
        user = User.objects.create_user(
            username='admin1',
            email='admin1@nhttransporters.co.ke',
            password='AdminPassword123!',
            role=UserRole.SUPER_ADMIN
        )
        log = AuditLog.objects.create(
            actor=user,
            action=AuditAction.CREATE,
            entity_type='User',
            entity_id=str(user.pk),
            outcome=AuditOutcome.SUCCESS,
            change_details={'username': 'admin1'}
        )
        assert log.pk is not None
        assert log.actor_username == 'admin1'
        assert log.action == AuditAction.CREATE

    def test_audit_log_immutability_update_fails(self):
        user = User.objects.create_user(
            username='auditor1',
            email='auditor1@nhttransporters.co.ke',
            password='AuditorPassword123!',
            role=UserRole.AUDITOR
        )
        log = AuditLog.objects.create(
            actor=user,
            action=AuditAction.LOGIN,
            entity_type='Session',
            entity_id='session_1',
            outcome=AuditOutcome.SUCCESS
        )
        log.outcome = AuditOutcome.FAILED
        with pytest.raises(ValidationError):
            log.save()

    def test_audit_log_immutability_delete_fails(self):
        user = User.objects.create_user(
            username='auditor2',
            email='auditor2@nhttransporters.co.ke',
            password='AuditorPassword123!',
            role=UserRole.AUDITOR
        )
        log = AuditLog.objects.create(
            actor=user,
            action=AuditAction.LOGOUT,
            entity_type='Session',
            entity_id='session_2',
            outcome=AuditOutcome.SUCCESS
        )
        with pytest.raises(ValidationError):
            log.delete()


@pytest.mark.django_db
class TestHealthChecks:
    def test_health_live(self, client):
        response = client.get('/health/live/')
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'alive'
        assert data['service'] == 'NHT-SMS'

    def test_health_ready(self, client):
        response = client.get('/health/ready/')
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'ready'
        assert data['database'] == 'connected'


@pytest.mark.django_db
class TestAuthenticationViews:
    def test_login_page_renders(self, client):
        response = client.get(reverse('accounts:login'))
        assert response.status_code == 200
        assert 'NHT-SMS' in response.content.decode('utf-8')

    def test_successful_login_and_signal(self, client):
        user = User.objects.create_user(
            username='testuser',
            email='testuser@nhttransporters.co.ke',
            password='SecurePassword123!',
            role=UserRole.SUPER_ADMIN
        )
        response = client.post(reverse('accounts:login'), {
            'username': 'testuser',
            'password': 'SecurePassword123!'
        })
        assert response.status_code == 302
        # Verify LoginHistory recorded
        assert LoginHistory.objects.filter(username_attempted='testuser', status=LoginHistory.Status.SUCCESS).exists()

    def test_unauthenticated_profile_redirects(self, client):
        response = client.get(reverse('accounts:profile'))
        assert response.status_code == 302
        assert '/accounts/login/' in response.url

    def test_authenticated_profile_accessible(self, client):
        user = User.objects.create_user(
            username='member_user',
            email='member@nhttransporters.co.ke',
            password='MemberPassword123!',
            role=UserRole.MEMBER
        )
        client.force_login(user)
        response = client.get(reverse('accounts:profile'))
        assert response.status_code == 200
        assert 'member_user' in response.content.decode('utf-8')
