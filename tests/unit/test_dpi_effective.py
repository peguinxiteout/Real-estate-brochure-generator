from brochure.dpi import effective_dpi


def test_300_px_across_a_one_inch_slot_is_300_dpi():
    assert effective_dpi(300, 300, 25.4, 25.4) == 300


def test_the_scarcer_axis_decides_for_a_wide_image_in_a_square_slot():
    # object-fit: cover scales to the short axis, so 3000x1000 px into 1x1 in is 1000 DPI
    assert effective_dpi(3000, 1000, 25.4, 25.4) == 1000
