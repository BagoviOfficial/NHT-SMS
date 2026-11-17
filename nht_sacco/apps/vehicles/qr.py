import io
import base64
import qrcode
from qrcode.constants import ERROR_CORRECT_M

def generate_qr_base64(data_url):
    """
    Generates a high-contrast PNG QR code and returns it as a base64 Data URI.
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=ERROR_CORRECT_M,
        box_size=8,
        border=3,
    )
    qr.add_data(data_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#10315C", back_color="#FFFFFF")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    b64_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
    return f"data:image/png;base64,{b64_str}"
