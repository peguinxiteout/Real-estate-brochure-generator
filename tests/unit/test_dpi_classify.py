from brochure.dpi import classify_dpi


def test_exactly_300_dpi_passes():
    assert classify_dpi(300) == "pass"


def test_299_99_dpi_warns():
    assert classify_dpi(299.99) == "warn"
