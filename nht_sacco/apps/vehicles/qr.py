import io
import base64
import qrcode
from qrcode.constants import ERROR_CORRECT_M


def generate_qr_png_bytes(data_url: str) -> bytes:
    """
    Generates a high-contrast PNG QR code and returns raw PNG bytes.
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=8,
        border=3,
    )
    qr.add_data(data_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#10315C", back_color="#FFFFFF")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def generate_qr_base64(data_url: str) -> str:
    """
    Generates a high-contrast PNG QR code and returns it as a base64 Data URI.
    """
    b64_str = base64.b64encode(generate_qr_png_bytes(data_url)).decode('utf-8')
    return f"data:image/png;base64,{b64_str}"
