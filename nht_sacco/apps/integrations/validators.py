import os
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from PIL import Image, UnidentifiedImageError

MAX_LOGO_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB
ALLOWED_LOGO_EXTENSIONS = {'.png', '.jpg', '.jpeg'}
ALLOWED_LOGO_MIME_TYPES = {'image/png', 'image/jpeg', 'image/jpg', 'image/pjpeg'}
MIN_LOGO_DIMENSION = 32
MAX_LOGO_DIMENSION = 4096
MAX_LOGO_PIXELS = 4096 * 4096

LOGO_MAGIC_SIGNATURES = {
    b'\x89PNG\r\n\x1a\n': 'PNG',
    b'\xff\xd8\xff': 'JPEG',
}


def validate_company_logo(file_obj):
    """
    Strict multi-layer validator for company logo uploads:
    1. Maximum file size (2 MB).
    2. Extension whitelist (.png, .jpg, .jpeg) - blocks SVG/HTML/executable uploads.
    3. MIME content-type check (when provided by upload handler).
    4. Binary magic-byte header signature verification.
    5. Safe Pillow image decode, verification, and dimension/pixel bounds.
    """
    if not file_obj:
        return

    if getattr(file_obj, 'size', 0) > MAX_LOGO_SIZE_BYTES:
        raise ValidationError(
            _("Logo file size (%(size)s) exceeds the 2 MB limit."),
            params={'size': f"{file_obj.size / (1024 * 1024):.2f} MB"},
        )

    if getattr(file_obj, 'size', 0) <= 0:
        raise ValidationError(_("Uploaded logo file is empty."))

    _stem, ext = os.path.splitext(getattr(file_obj, 'name', '') or '')
    if ext.lower() not in ALLOWED_LOGO_EXTENSIONS:
        raise ValidationError(
            _("Unsupported logo format '%(ext)s'. Only PNG and JPEG images are allowed."),
            params={'ext': ext or 'unknown'},
        )

    content_type = getattr(file_obj, 'content_type', None)
    if content_type and content_type.lower().split(';')[0].strip() not in ALLOWED_LOGO_MIME_TYPES:
        raise ValidationError(
            _("Unsupported MIME type '%(mime)s'. Expected image/png or image/jpeg."),
            params={'mime': content_type},
        )

    initial_pos = file_obj.tell() if hasattr(file_obj, 'tell') else 0
    if hasattr(file_obj, 'seek'):
        file_obj.seek(0)
    header = file_obj.read(16)
    if hasattr(file_obj, 'seek'):
        file_obj.seek(initial_pos)

    matched_format = None
    for signature, fmt in LOGO_MAGIC_SIGNATURES.items():
        if header.startswith(signature):
            matched_format = fmt
            break

    if not matched_format:
        raise ValidationError(
            _("File binary signature does not match a valid PNG or JPEG image.")
        )

    prev_max_pixels = Image.MAX_IMAGE_PIXELS
    try:
        Image.MAX_IMAGE_PIXELS = MAX_LOGO_PIXELS
        if hasattr(file_obj, 'seek'):
            file_obj.seek(0)
        with Image.open(file_obj) as img:
            img.verify()
        if hasattr(file_obj, 'seek'):
            file_obj.seek(0)
        with Image.open(file_obj) as img:
            img.load()
            width, height = img.size
            if img.format not in ('PNG', 'JPEG'):
                raise ValidationError(_("Decoded image format must be PNG or JPEG."))
            if width < MIN_LOGO_DIMENSION or height < MIN_LOGO_DIMENSION:
                raise ValidationError(
                    _("Logo dimensions (%(w)dx%(h)d) are too small; minimum is %(min)dx%(min)d px."),
                    params={'w': width, 'h': height, 'min': MIN_LOGO_DIMENSION},
                )
            if width > MAX_LOGO_DIMENSION or height > MAX_LOGO_DIMENSION:
                raise ValidationError(
                    _("Logo dimensions (%(w)dx%(h)d) exceed maximum %(max)dx%(max)d px."),
                    params={'w': width, 'h': height, 'max': MAX_LOGO_DIMENSION},
                )
    except ValidationError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError) as exc:
        raise ValidationError(
            _("Invalid or unsafe image file: %(err)s"),
            params={'err': str(exc)},
        )
    finally:
        Image.MAX_IMAGE_PIXELS = prev_max_pixels
        if hasattr(file_obj, 'seek'):
            file_obj.seek(initial_pos)
