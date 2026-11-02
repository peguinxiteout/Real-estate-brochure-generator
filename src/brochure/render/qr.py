"""QR codes as vector SVG, with the qrcode package: one path of square modules, no raster image."""
import re

import qrcode
import qrcode.image.svg

ERROR_CORRECTION = qrcode.constants.ERROR_CORRECT_M
QUIET_ZONE_MODULES = 4  # the minimum the QR standard asks for


def qr_svg(data: str, size_mm: float) -> str:
    """The code for data as an SVG string, size_mm wide and high, the quiet zone included. The same data always gives
    the same string."""
    code = qrcode.QRCode(error_correction=ERROR_CORRECTION, border=QUIET_ZONE_MODULES,
                         image_factory=qrcode.image.svg.SvgPathImage)
    code.add_data(data)
    code.make(fit=True)
    svg = code.make_image().to_string(encoding="unicode")
    size = f"{size_mm:g}mm"
    return re.sub(r'(<svg[^>]*?) width="[^"]*" height="[^"]*"', rf'\1 width="{size}" height="{size}"', svg, count=1)
