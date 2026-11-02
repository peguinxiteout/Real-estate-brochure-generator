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
