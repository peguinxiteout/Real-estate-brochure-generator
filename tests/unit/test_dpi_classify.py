from brochure.dpi import classify_dpi


def test_exactly_300_dpi_passes():
    assert classify_dpi(300) == "pass"


def test_299_99_dpi_warns():
    assert classify_dpi(299.99) == "warn"


def test_exactly_250_dpi_still_warns():
    assert classify_dpi(250) == "warn"


def test_249_99_dpi_fails():
    assert classify_dpi(249.99) == "fail"
