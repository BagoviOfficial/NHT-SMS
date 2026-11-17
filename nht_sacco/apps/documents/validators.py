import os
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png'}

# File signature magic bytes
MAGIC_SIGNATURES = {
    b'%PDF': 'application/pdf',
    b'\xff\xd8\xff': 'image/jpeg',
    b'\x89PNG\r\n\x1a\n': 'image/png',
}


def validate_file_magic_bytes(file_obj):
    """
    Reads the initial bytes of a file to verify it matches an authorized binary signature.
    Prevents file disguised execution attacks (e.g. PHP/shell scripts renamed to .pdf).
    """
    initial_pos = file_obj.tell() if hasattr(file_obj, 'tell') else 0
    header = file_obj.read(16)
    if hasattr(file_obj, 'seek'):
        file_obj.seek(initial_pos)

    for signature in MAGIC_SIGNATURES:
        if header.startswith(signature):
            return True
    return False


def validate_regulatory_document(file_obj):
    """
    Comprehensive document security validator enforcing:
    1. Maximum file size (10 MB).
    2. Strict extension whitelist (.pdf, .jpg, .jpeg, .png).
    3. Magic byte header verification matching valid binary signatures.
    """
    if file_obj.size > MAX_FILE_SIZE_BYTES:
        raise ValidationError(
            _("File size %(size)s exceeds the maximum permitted limit of 10MB."),
            params={'size': f"{file_obj.size / (1024 * 1024):.2f}MB"}
        )

    base_name, ext = os.path.splitext(file_obj.name)
    if ext.lower() not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            _("File extension '%(ext)s' is prohibited. Allowed formats: PDF, JPG, PNG."),
            params={'ext': ext}
        )

    if not validate_file_magic_bytes(file_obj):
        raise ValidationError(
            _("File content signature does not match a valid PDF, JPEG, or PNG document.")
        )
