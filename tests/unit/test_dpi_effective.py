from brochure.dpi import effective_dpi


def test_300_px_across_a_one_inch_slot_is_300_dpi():
    assert effective_dpi(300, 300, 25.4, 25.4) == 300
