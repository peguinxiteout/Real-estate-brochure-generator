import pytest

from brochure.render.geometry import mm_to_pt

TOL_PT = 0.01


def test_mm_to_pt_uses_72_points_per_25_4_mm():
    assert mm_to_pt(25.4) == pytest.approx(72, abs=TOL_PT)
    assert mm_to_pt(1) == pytest.approx(2.8346, abs=TOL_PT)
    assert mm_to_pt(210) == pytest.approx(595.2756, abs=TOL_PT)
