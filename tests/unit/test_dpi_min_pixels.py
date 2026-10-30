from brochure.dpi import min_pixels


def test_216_mm_at_300_dpi_needs_2552_px():
    assert min_pixels(216, 300) == 2552


def test_exact_inch_multiple_is_not_rounded_up_by_float_error():
    # 38.1 mm is exactly 1.5 in, so exactly 450 px at 300 DPI; float maths gives 450.00000000000006
    assert min_pixels(38.1, 300) == 450


def test_303_mm_at_300_dpi_needs_3579_px():
    assert min_pixels(303, 300) == 3579
