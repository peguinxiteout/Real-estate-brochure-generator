from brochure.print_config import PRINT


def test_target_dpi_is_300():
    assert PRINT.target_dpi == 300


def test_warn_dpi_is_250():
    assert PRINT.warn_dpi == 250


def test_bleed_is_3_mm():
    assert PRINT.bleed_mm == 3


def test_page_is_a4_portrait():
    assert (PRINT.page_width_mm, PRINT.page_height_mm) == (210, 297)
