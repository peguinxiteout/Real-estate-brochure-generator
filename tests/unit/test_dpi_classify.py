from brochure.dpi import classify_dpi


def test_exactly_300_dpi_passes():
    assert classify_dpi(300) == "pass"
