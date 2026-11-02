import pytest

from brochure.print_config import PRINT
from brochure.render.geometry import Box, mm_to_pt, page_geometry_mm

TOL_PT = 0.01


def test_mm_to_pt_uses_72_points_per_25_4_mm():
    assert mm_to_pt(25.4) == pytest.approx(72, abs=TOL_PT)
    assert mm_to_pt(1) == pytest.approx(2.8346, abs=TOL_PT)
    assert mm_to_pt(210) == pytest.approx(595.2756, abs=TOL_PT)


def test_trim_box_is_the_a4_page_with_its_origin_at_the_lower_left():
    assert page_geometry_mm().trim == Box(0, 0, PRINT.page_width_mm, PRINT.page_height_mm)
    assert (PRINT.page_width_mm, PRINT.page_height_mm) == (210, 297)


def test_bleed_box_is_exactly_3_mm_outside_the_trim_on_every_edge():
    g = page_geometry_mm()
    assert PRINT.bleed_mm == 3
    assert g.trim.left - g.bleed.left == 3
    assert g.trim.bottom - g.bleed.bottom == 3
    assert g.bleed.right - g.trim.right == 3
    assert g.bleed.top - g.trim.top == 3


def test_media_box_is_trim_plus_bleed_plus_slug_on_every_edge_236_by_323_mm():
    media = page_geometry_mm().media
    assert (media.width, media.height) == (236, 323)


def test_trim_is_centred_in_the_media_box():
    g = page_geometry_mm()
    margins = {g.trim.left - g.media.left, g.trim.bottom - g.media.bottom,
               g.media.right - g.trim.right, g.media.top - g.trim.top}
    assert margins == {PRINT.bleed_mm + PRINT.slug_beyond_bleed_mm}
