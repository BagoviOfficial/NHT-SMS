import os
import mimetypes
from django.views import View
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from .models import Document
from nht_sacco.apps.accounts.models import UserRole
from nht_sacco.apps.audit.models import AuditLog, AuditAction, AuditOutcome

DOCUMENT_STAFF_ROLES = {
    UserRole.SUPER_ADMIN,
    UserRole.COMPLIANCE_OFFICER,
    UserRole.RENEWAL_OFFICER,
    UserRole.SECRETARY,
    UserRole.CHAIRMAN,
    UserRole.AUDITOR,
}

class DocumentDownloadView(LoginRequiredMixin, View):
    """
    Secure controller for private regulatory documents.
    Enforces strict object-level authorization (IDOR prevention) before streaming file bytes.
    """
    def get(self, request, pk, *args, **kwargs):
        doc = get_object_or_404(Document, pk=pk)
        user = request.user

        # Authorization Logic (least-privilege staff roles + object-owning member/driver)
        is_staff_authorized = user.is_superuser or user.role in DOCUMENT_STAFF_ROLES
        is_owner_authorized = False

        if hasattr(user, 'member_profile'):
            member = user.member_profile
            if doc.vehicle and doc.vehicle.current_owner == member:
                is_owner_authorized = True
            elif doc.member and doc.member == member:
                is_owner_authorized = True

        if not is_owner_authorized and hasattr(user, 'driver_profile'):
            if doc.driver and doc.driver == user.driver_profile:
                is_owner_authorized = True

        if not (is_staff_authorized or is_owner_authorized):
            AuditLog.objects.create(
                actor=user,
                action=AuditAction.SYSTEM,
                entity_type='Document',
                entity_id=str(doc.pk),
                outcome=AuditOutcome.DENIED,
                change_details={'reason': 'Unauthorized document access attempt'}
            )
            return HttpResponseForbidden("Access Denied: You do not have permission to access this private document.")

        if not doc.file or not os.path.exists(doc.file.path):
            raise Http404("Document file was not found in the storage vault.")

        # Log authorized access
        AuditLog.objects.create(
            actor=user,
            action=AuditAction.SYSTEM,
            entity_type='Document',
            entity_id=str(doc.pk),
            outcome=AuditOutcome.SUCCESS,
            change_details={'action': 'file_download', 'filename': os.path.basename(doc.file.name)}
        )

        content_type, _ = mimetypes.guess_type(doc.file.path)
        response = FileResponse(open(doc.file.path, 'rb'), content_type=content_type or 'application/octet-stream')
        response['Content-Disposition'] = f'inline; filename="{os.path.basename(doc.file.name)}"'
        return response
