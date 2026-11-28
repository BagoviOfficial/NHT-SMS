import io
import logging
from PIL import Image
from django.utils import timezone
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from openpyxl.drawing.image import Image as OpenpyxlImage
from openpyxl.styles import Alignment, Font, PatternFill

from .models import BrandingVersion, CompanyProfile

logger = logging.getLogger(__name__)


def _hex_to_rgb(hex_color: str, fallback=(16, 49, 92)):
    val = (hex_color or '').strip().lstrip('#')
    if len(val) == 3:
        val = ''.join(ch * 2 for ch in val)
    if len(val) != 6:
        return fallback
    try:
        return (int(val[0:2], 16), int(val[2:4], 16), int(val[4:6], 16))
    except ValueError:
        return fallback


def _sanitize_pdf_text(text) -> str:
    """
    fpdf2 standard built-in fonts (Helvetica/Times/Courier) use latin-1 encoding.
    Safely normalize characters outside latin-1 so PDF export never crashes.
    """
    if text is None:
        return ''
    return str(text).encode('latin-1', errors='replace').decode('latin-1')


class BrandedFPDF(FPDF):
    """
    FPDF subclass that automatically renders consistent branded footers and page numbers.
    """
    def __init__(self, branding_ctx=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.branding_ctx = branding_ctx or {}
        self.alias_nb_pages()

    def footer(self):
        self.set_y(-14)
        self.set_draw_color(203, 213, 225)
        self.line(10, self.get_y(), self.w - 10, self.get_y())
        self.set_y(-12)
        self.set_font('Helvetica', 'I', 7.5)
        self.set_text_color(100, 116, 139)
        footer_text = _sanitize_pdf_text(
            self.branding_ctx.get('footer_text')
            or f"{self.branding_ctx.get('legal_name', 'Northern Highways Transporters SACCO')} | Official Document"
        )
        ver = self.branding_ctx.get('version_number', 1)
        self.cell(self.w - 45, 8, f"{footer_text} (Brand v{ver})", align='L')
        self.cell(25, 8, f"Page {self.page_no()}/{{nb}}", align='R')


class DocumentBrandingService:
    """
    Central reusable document-branding service used across all PDF, Excel,
    printable card, receipt, invoice, and membership certificate generators.
    """

    @classmethod
    def _read_field_bytes(cls, file_field) -> bytes:
        if not file_field or not getattr(file_field, 'name', None):
            return b''
        try:
            file_field.open('rb')
            data = file_field.read()
            file_field.close()
            return data or b''
        except Exception as exc:
            logger.warning("Unable to read branding asset '%s': %s", getattr(file_field, 'name', ''), exc)
            return b''

    @classmethod
    def _normalize_image_bytes(cls, raw_bytes: bytes):
        if not raw_bytes:
            return b'', 0, 0
        try:
            with Image.open(io.BytesIO(raw_bytes)) as img:
                width, height = img.size
                fmt = 'PNG' if img.mode in ('RGBA', 'LA', 'P') or img.format == 'PNG' else 'JPEG'
                out = io.BytesIO()
                if fmt == 'PNG':
                    img.convert('RGBA').save(out, format='PNG')
                else:
                    img.convert('RGB').save(out, format='JPEG', quality=92)
                return out.getvalue(), width, height
        except Exception as exc:
            logger.warning("Failed to normalize logo image bytes: %s", exc)
            return b'', 0, 0

    @classmethod
    def get_branding_context(cls, branding_version=None) -> dict:
        """
        Resolves company profile metadata & proportional logo bytes.
        When `branding_version` is provided, uses that immutable historical snapshot
        so previously issued documents preserve their original branding.
        """
        if branding_version is not None and isinstance(branding_version, BrandingVersion):
            snap = dict(branding_version.profile_snapshot or {})
            raw_logo = cls._read_field_bytes(branding_version.logo_archive)
            version_number = branding_version.version_number
        else:
            profile = CompanyProfile.get_active()
            snap = profile.to_snapshot_dict()
            raw_logo = cls._read_field_bytes(profile.logo)
            version_number = profile.current_version

        logo_bytes, logo_w, logo_h = cls._normalize_image_bytes(raw_logo)
        primary_hex = snap.get('primary_color') or '#10315C'
        secondary_hex = snap.get('secondary_color') or '#FF8A00'

        return {
            'legal_name': snap.get('legal_name') or 'Northern Highways Transporters SACCO Limited',
            'trading_name': snap.get('trading_name') or 'Northern Highways Transporters SACCO',
            'short_name': snap.get('short_name') or 'NHT-SMS',
            'registration_number': snap.get('registration_number') or '',
            'tax_pin': snap.get('tax_pin') or '',
            'physical_address': snap.get('physical_address') or '',
            'postal_address': snap.get('postal_address') or '',
            'phone_numbers': snap.get('phone_numbers') or '',
            'official_email': snap.get('official_email') or '',
            'website': snap.get('website') or '',
            'public_base_url': snap.get('public_base_url') or '',
            'footer_text': snap.get('footer_text') or '',
            'primary_color': primary_hex,
            'secondary_color': secondary_hex,
            'primary_rgb': _hex_to_rgb(primary_hex, (16, 49, 92)),
            'secondary_rgb': _hex_to_rgb(secondary_hex, (255, 138, 0)),
            'version_number': version_number,
            'logo_bytes': logo_bytes,
            'logo_width': logo_w,
            'logo_height': logo_h,
            'has_logo': bool(logo_bytes and logo_w > 0 and logo_h > 0),
        }

    @classmethod
    def create_pdf(cls, orientation='P', format='A4', branding_version=None):
        ctx = cls.get_branding_context(branding_version=branding_version)
        pdf = BrandedFPDF(branding_ctx=ctx, orientation=orientation, unit='mm', format=format)
        pdf.set_auto_page_break(auto=True, margin=18)
        pdf.add_page()
        return pdf, ctx

    @classmethod
    def apply_pdf_header(cls, pdf: FPDF, ctx: dict, title: str, subtitle: str = '', meta_right: str = ''):
        """
        Draws a branded PDF top banner with proportional logo embedding (or clean
        text fallback when no logo is uploaded) and company contact metadata.
        """
        pr, pg, pb = ctx['primary_rgb']
        sr, sg, sb = ctx['secondary_rgb']
        page_w = pdf.w

        # Header band
        band_h = 30
        pdf.set_fill_color(pr, pg, pb)
        pdf.rect(0, 0, page_w, band_h, 'F')

        # Accent bottom border
        pdf.set_fill_color(sr, sg, sb)
        pdf.rect(0, band_h, page_w, 1.5, 'F')

        text_x = 12
        text_w = page_w - 24

        if ctx['has_logo']:
            target_h = 20.0
            aspect = ctx['logo_width'] / max(1, ctx['logo_height'])
            target_w = min(38.0, target_h * aspect)
            actual_h = target_w / aspect if aspect > 0 else target_h
            logo_y = (band_h - actual_h) / 2.0
            # Soft white backdrop pad so transparent/dark logos remain sharp
            pdf.set_fill_color(255, 255, 255)
            pdf.rect(10, logo_y - 1.5, target_w + 3, actual_h + 3, 'F')
            pdf.image(io.BytesIO(ctx['logo_bytes']), x=11.5, y=logo_y, w=target_w, h=actual_h)
            text_x = 11.5 + target_w + 6
            text_w = page_w - text_x - 10

        pdf.set_xy(text_x, 5.5)
        pdf.set_font('Helvetica', 'B', 13.5)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(text_w, 6.5, _sanitize_pdf_text(ctx['trading_name'].upper()), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_x(text_x)
        pdf.set_font('Helvetica', 'B', 9.5)
        pdf.set_text_color(sr, sg, sb)
        pdf.cell(text_w, 5, _sanitize_pdf_text(title.upper()), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        contact_parts = [p for p in [ctx['physical_address'], ctx['phone_numbers'], ctx['official_email']] if p]
        contact_line = " | ".join(contact_parts)[:110]
        if contact_line:
            pdf.set_x(text_x)
            pdf.set_font('Helvetica', '', 7.5)
            pdf.set_text_color(226, 232, 240)
            pdf.cell(text_w, 4.5, _sanitize_pdf_text(contact_line), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_y(band_h + 4.5)
        pdf.set_text_color(30, 41, 59)
        pdf.set_font('Helvetica', '', 8.5)
        gen_time = timezone.localtime(timezone.now()).strftime("%Y-%m-%d %H:%M EAT")
        left_note = subtitle or f"Reg No: {ctx['registration_number'] or 'N/A'}"
        right_note = meta_right or f"Generated: {gen_time}"
        half_w = (page_w - 20) / 2.0
        pdf.cell(half_w, 5, _sanitize_pdf_text(left_note), new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(half_w, 5, _sanitize_pdf_text(right_note), align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_draw_color(203, 213, 225)
        pdf.line(10, pdf.get_y() + 1, page_w - 10, pdf.get_y() + 1)
        pdf.ln(4)

    @classmethod
    def apply_excel_header(cls, ws, title: str, col_count: int = 8, branding_version=None, subtitle: str = '') -> int:
        """
        Applies proportional company logo and professional executive heading rows
        to an openpyxl worksheet. Preserves editable structure and returns the
        1-based row index where the data table header should start.
        """
        ctx = cls.get_branding_context(branding_version=branding_version)
        primary_hex = ctx['primary_color'].lstrip('#').upper()
        if len(primary_hex) != 6:
            primary_hex = '10315C'
        secondary_hex = ctx['secondary_color'].lstrip('#').upper()
        if len(secondary_hex) != 6:
            secondary_hex = 'FF8A00'

        max_col = max(4, col_count)
        banner_fill = PatternFill(start_color=primary_hex, end_color=primary_hex, fill_type='solid')
        sub_fill = PatternFill(start_color='F1F5F9', end_color='F1F5F9', fill_type='solid')

        ws.row_dimensions[1].height = 24
        ws.row_dimensions[2].height = 20
        ws.row_dimensions[3].height = 18
        ws.row_dimensions[4].height = 6

        for r in (1, 2):
            for c in range(1, max_col + 1):
                ws.cell(row=r, column=c).fill = banner_fill
        for c in range(1, max_col + 1):
            ws.cell(row=3, column=c).fill = sub_fill

        text_start_col = 1
        if ctx['has_logo']:
            ws.column_dimensions['A'].width = max(ws.column_dimensions['A'].width or 12, 16)
            xl_img = OpenpyxlImage(io.BytesIO(ctx['logo_bytes']))
            target_h = 54.0
            aspect = ctx['logo_width'] / max(1, ctx['logo_height'])
            xl_img.height = int(target_h)
            xl_img.width = max(24, int(target_h * aspect))
            ws.add_image(xl_img, 'A1')
            text_start_col = 2

        ws.merge_cells(start_row=1, start_column=text_start_col, end_row=1, end_column=max_col)
        c1 = ws.cell(row=1, column=text_start_col, value=ctx['legal_name'].upper())
        c1.font = Font(name='Calibri', size=14, bold=True, color='FFFFFF')
        c1.alignment = Alignment(horizontal='left', vertical='center')

        ws.merge_cells(start_row=2, start_column=text_start_col, end_row=2, end_column=max_col)
        c2 = ws.cell(row=2, column=text_start_col, value=title)
        c2.font = Font(name='Calibri', size=11, bold=True, color=secondary_hex)
        c2.alignment = Alignment(horizontal='left', vertical='center')

        gen_time = timezone.localtime(timezone.now()).strftime("%Y-%m-%d %H:%M EAT")
        meta_parts = [p for p in [subtitle, ctx['physical_address'], ctx['phone_numbers'], f"Generated: {gen_time}"] if p]
        ws.merge_cells(start_row=3, start_column=text_start_col, end_row=3, end_column=max_col)
        c3 = ws.cell(row=3, column=text_start_col, value=" | ".join(meta_parts))
        c3.font = Font(name='Calibri', size=9, italic=True, color='334155')
        c3.alignment = Alignment(horizontal='left', vertical='center')

        return 5

    @classmethod
    def generate_membership_certificate_pdf(cls, member, branding_version=None) -> bytes:
        pdf, ctx = cls.create_pdf(orientation='P', format='A4', branding_version=branding_version)
        cls.apply_pdf_header(
            pdf,
            ctx,
            title="OFFICIAL SACCO MEMBERSHIP CERTIFICATE",
            subtitle=f"Member Ref: {member.membership_number}",
        )
        pr, pg, pb = ctx['primary_rgb']
        sr, sg, sb = ctx['secondary_rgb']

        pdf.ln(4)
        pdf.set_draw_color(pr, pg, pb)
        pdf.set_line_width(0.6)
        pdf.rect(14, pdf.get_y(), 182, 118)
        pdf.set_draw_color(sr, sg, sb)
        pdf.set_line_width(0.3)
        pdf.rect(16, pdf.get_y() + 2, 178, 114)

        pdf.set_y(pdf.get_y() + 10)
        pdf.set_font('Helvetica', '', 11)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(0, 7, "THIS IS TO CERTIFY THAT", align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.ln(2)
        pdf.set_font('Helvetica', 'B', 18)
        pdf.set_text_color(pr, pg, pb)
        pdf.cell(0, 10, _sanitize_pdf_text(member.full_name.upper()), align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(sr, sg, sb)
        pdf.cell(0, 7, _sanitize_pdf_text(f"MEMBERSHIP NUMBER: {member.membership_number}"), align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.ln(4)
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(30, 41, 59)
        body = (
            f"is a duly registered member of {ctx['legal_name']} under the "
            f"{member.get_category_display()} category, operating within {member.county} County."
        )
        pdf.set_x(24)
        pdf.multi_cell(162, 6, _sanitize_pdf_text(body), align='C')

        pdf.ln(6)
        rows = [
            ("Membership Status", member.get_status_display()),
            ("Application Date", str(member.application_date)),
            ("Approval Date", member.approval_date.strftime("%Y-%m-%d") if member.approval_date else "Pending"),
            ("Approved By", member.approved_by.get_full_name() if member.approved_by else "SACCO Secretariat"),
        ]
        for lbl, val in rows:
            pdf.set_x(30)
            pdf.set_font('Helvetica', 'B', 9.5)
            pdf.cell(55, 7, _sanitize_pdf_text(lbl), border=1)
            pdf.set_font('Helvetica', '', 9.5)
            pdf.cell(95, 7, _sanitize_pdf_text(val), border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        return bytes(pdf.output())

    @classmethod
    def generate_receipt_pdf(cls, receipt) -> bytes:
        pdf, ctx = cls.create_pdf(orientation='P', format='A4', branding_version=receipt.branding_version)
        cls.apply_pdf_header(
            pdf,
            ctx,
            title="OFFICIAL PAYMENT RECEIPT",
            subtitle=f"Receipt No: {receipt.receipt_number}",
            meta_right=f"Issued: {timezone.localtime(receipt.issued_at).strftime('%Y-%m-%d %H:%M EAT')}",
        )
        payment = receipt.payment
        inv = payment.invoice
        member = payment.member

        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(95, 6, _sanitize_pdf_text(f"Received From: {member.full_name}"), new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(95, 6, _sanitize_pdf_text(f"Member No: {member.membership_number}"), align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_font('Helvetica', '', 9)
        pdf.cell(95, 6, _sanitize_pdf_text(f"Payment Method: {payment.get_method_display()}"), new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(95, 6, _sanitize_pdf_text(f"Provider Ref: {payment.provider_transaction_id or payment.payment_reference}"), align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(5)

        pdf.set_fill_color(241, 245, 249)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(90, 8, "Description", border=1, fill=True)
        pdf.cell(50, 8, "Invoice Reference", border=1, fill=True)
        pdf.cell(50, 8, "Amount Cleared (KES)", border=1, fill=True, align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_font('Helvetica', '', 9)
        pdf.cell(90, 8, "Settlement of SACCO Services & Fleet Dues", border=1)
        pdf.cell(50, 8, _sanitize_pdf_text(inv.invoice_number), border=1)
        pdf.cell(50, 8, f"{payment.amount:,.2f}", border=1, align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(140, 8, "TOTAL CLEARED (KES)", border=1, align='R')
        pdf.cell(50, 8, f"{payment.amount:,.2f}", border=1, align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_font('Helvetica', '', 9)
        pdf.cell(140, 7, "Remaining Invoice Balance (KES)", border=1, align='R')
        pdf.cell(50, 7, f"{inv.balance_due:,.2f}", border=1, align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        return bytes(pdf.output())

    @classmethod
    def generate_invoice_pdf(cls, invoice) -> bytes:
        pdf, ctx = cls.create_pdf(orientation='P', format='A4', branding_version=invoice.branding_version)
        cls.apply_pdf_header(
            pdf,
            ctx,
            title="OFFICIAL SACCO TAX / SERVICE INVOICE",
            subtitle=f"Invoice No: {invoice.invoice_number} | Status: {invoice.get_status_display()}",
            meta_right=f"Due Date: {invoice.due_date}",
        )
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(95, 6, _sanitize_pdf_text(f"Billed To: {invoice.member.full_name}"), new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(95, 6, _sanitize_pdf_text(f"Member No: {invoice.member.membership_number}"), align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if invoice.vehicle:
            pdf.set_font('Helvetica', '', 9)
            pdf.cell(190, 6, _sanitize_pdf_text(f"Vehicle: {invoice.vehicle.registration_number} ({invoice.vehicle.make} {invoice.vehicle.model})"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(4)

        pdf.set_fill_color(241, 245, 249)
        pdf.set_font('Helvetica', 'B', 8.5)
        pdf.cell(85, 7, "Service Description", border=1, fill=True)
        pdf.cell(30, 7, "Classification", border=1, fill=True, align='C')
        pdf.cell(15, 7, "Qty", border=1, fill=True, align='C')
        pdf.cell(30, 7, "Unit (KES)", border=1, fill=True, align='R')
        pdf.cell(30, 7, "Total (KES)", border=1, fill=True, align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_font('Helvetica', '', 8.5)
        for item in invoice.line_items.select_related('service_item').all():
            cls_label = "Statutory" if item.service_item.is_statutory else "SACCO Fee"
            pdf.cell(85, 7, _sanitize_pdf_text((item.description or item.service_item.name)[:48]), border=1)
            pdf.cell(30, 7, cls_label, border=1, align='C')
            pdf.cell(15, 7, str(item.quantity), border=1, align='C')
            pdf.cell(30, 7, f"{item.unit_price:,.2f}", border=1, align='R')
            pdf.cell(30, 7, f"{item.total_price:,.2f}", border=1, align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(160, 7, "SACCO Charges Subtotal", border=1, align='R')
        pdf.cell(30, 7, f"{invoice.subtotal:,.2f}", border=1, align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.cell(160, 7, "Statutory Regulatory Fees", border=1, align='R')
        pdf.cell(30, 7, f"{invoice.statutory_total:,.2f}", border=1, align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(160, 8, "TOTAL BILLED (KES)", border=1, align='R')
        pdf.cell(30, 8, f"{invoice.total_amount:,.2f}", border=1, align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.cell(160, 7, "Balance Due (KES)", border=1, align='R')
        pdf.cell(30, 7, f"{invoice.balance_due:,.2f}", border=1, align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        return bytes(pdf.output())

    @classmethod
    def generate_compliance_card_pdf(cls, card, verify_url: str, qr_png_bytes: bytes) -> bytes:
        """
        Generates a printable digital Vehicle Compliance Card PDF containing
        centralized company branding, vehicle details, certificate lifecycle dates,
        issuing officer, and secure QR code.
        """
        pdf, ctx = cls.create_pdf(orientation='P', format='A4', branding_version=card.branding_version)
        cls.apply_pdf_header(
            pdf,
            ctx,
            title="VEHICLE COMPLIANCE CERTIFICATE CARD",
            subtitle=f"Certificate No: {card.certificate_number}",
            meta_right=f"Status: {card.status}",
        )
        pr, pg, pb = ctx['primary_rgb']
        sr, sg, sb = ctx['secondary_rgb']

        # Framed Card Box
        top_y = pdf.get_y() + 2
        pdf.set_draw_color(pr, pg, pb)
        pdf.set_line_width(0.8)
        pdf.rect(12, top_y, 186, 112)

        # Plate Highlight Box
        pdf.set_fill_color(sr, sg, sb)
        pdf.set_xy(18, top_y + 8)
        pdf.set_font('Helvetica', 'B', 18)
        pdf.set_text_color(pr, pg, pb)
        pdf.cell(80, 12, _sanitize_pdf_text(card.vehicle.registration_number), border=0, fill=True, align='C')

        # Details column on left
        pdf.set_text_color(30, 41, 59)
        details = [
            ("Certificate Ref", card.certificate_number),
            ("Fleet / Ref No", card.fleet_number or "-"),
            ("Vehicle", f"{card.vehicle.make} {card.vehicle.model} ({card.vehicle.get_category_display()})"),
            ("Owner / Operator", card.owner_display_name or card.vehicle.current_owner.full_name),
            ("Assigned Route", card.assigned_route_name or "Unassigned"),
            ("Compliance Status", card.status),
            ("Issue Date", str(card.issue_date)),
            ("Expiry Date", str(card.expiry_date)),
            ("Issuing Officer", card.issued_by.get_full_name() if card.issued_by else "SACCO Compliance Desk"),
        ]
        y_cursor = top_y + 25
        for lbl, val in details:
            pdf.set_xy(18, y_cursor)
            pdf.set_font('Helvetica', 'B', 8.5)
            pdf.set_text_color(100, 116, 139)
            pdf.cell(38, 6.5, _sanitize_pdf_text(lbl + ":"))
            pdf.set_font('Helvetica', 'B' if lbl in ('Certificate Ref', 'Compliance Status') else '', 9)
            pdf.set_text_color(15, 23, 42)
            pdf.cell(75, 6.5, _sanitize_pdf_text(str(val)[:42]))
            y_cursor += 7.5

        # QR Code on right
        if qr_png_bytes:
            pdf.set_draw_color(203, 213, 225)
            pdf.set_line_width(0.3)
            pdf.rect(136, top_y + 12, 54, 68)
            pdf.image(io.BytesIO(qr_png_bytes), x=140, y=top_y + 15, w=46, h=46)
            pdf.set_xy(136, top_y + 63)
            pdf.set_font('Helvetica', 'B', 7.5)
            pdf.set_text_color(pr, pg, pb)
            pdf.cell(54, 4.5, "SCAN TO VERIFY LIVE STATUS", align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_x(136)
            pdf.set_font('Helvetica', '', 6.5)
            pdf.set_text_color(100, 116, 139)
            pdf.cell(54, 4, _sanitize_pdf_text(f"Token Ref: {card.token_hint}..."), align='C')

        pdf.set_y(top_y + 118)
        pdf.set_font('Helvetica', 'I', 8)
        pdf.set_text_color(100, 116, 139)
        pdf.multi_cell(
            186,
            5,
            _sanitize_pdf_text(
                f"Public Verification Endpoint: {verify_url}\n"
                "Authenticity is verified live against SACCO records. Revoked, suspended, expired, or superseded cards fail inspection immediately."
            ),
        )
        return bytes(pdf.output())
