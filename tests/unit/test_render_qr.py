"""The RERA QR code as vector SVG: error correction M, a 4-module quiet zone, drawn at the slot's size."""
import re

from brochure.render.qr import qr_svg

URL = "https://example.com/rera/sample"  # 31 bytes


def view_box_size(svg: str) -> int:
    x, y, w, h = re.search(r'viewBox="([^"]+)"', svg).group(1).split()
    assert (x, y) == ("0", "0") and w == h
    return int(w)


def test_the_same_data_gives_the_same_svg():
    assert qr_svg(URL, 25) == qr_svg(URL, 25)


def test_different_data_gives_a_different_svg():
    assert qr_svg(URL, 25) != qr_svg(URL + "/2", 25)


def test_it_is_drawn_at_the_size_asked_for_in_mm():
    svg = qr_svg(URL, 25)
    assert re.search(r'<svg[^>]* width="25mm"', svg) and re.search(r'<svg[^>]* height="25mm"', svg)


def test_error_correction_is_m():
    # 31 bytes: L fits version 2 (25 modules), M and Q need version 3 (29). 42 bytes: L and M fit version 3, Q needs 4.
    # Only M gives 29 modules for both, so 29 + 2 x 4 quiet-zone modules = 37 across.
    assert view_box_size(qr_svg(URL, 25)) == 37
    assert view_box_size(qr_svg("x" * 42, 25)) == 37


def test_the_quiet_zone_is_4_modules_with_nothing_drawn_in_it():
    svg = qr_svg(URL, 25)
    n = view_box_size(svg)
    numbers = [float(v) for v in re.findall(r"\d+(?:\.\d+)?", re.search(r'<path[^>]* d="([^"]+)"', svg).group(1))]
    assert numbers and min(numbers) == 4 and max(numbers) == n - 4


def test_it_is_vector_with_no_raster_image():
    svg = qr_svg(URL, 25)
    assert "<path" in svg and "<image" not in svg and "base64" not in svg
