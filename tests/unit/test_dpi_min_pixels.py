from brochure.dpi import min_pixels


def test_216_mm_at_300_dpi_needs_2552_px():
    assert min_pixels(216, 300) == 2552
