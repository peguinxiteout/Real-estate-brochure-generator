from brochure.dpi import classify_dpi
from brochure.print_config import PrintConfig


def test_exactly_300_dpi_passes():
    assert classify_dpi(300) == "pass"


def test_299_99_dpi_warns():
    assert classify_dpi(299.99) == "warn"


def test_exactly_250_dpi_still_warns():
    assert classify_dpi(250) == "warn"


def test_249_99_dpi_fails():
    assert classify_dpi(249.99) == "fail"


def test_thresholds_come_from_the_print_config():
    relaxed = PrintConfig(target_dpi=200, warn_dpi=150)
    assert classify_dpi(180, relaxed) == "warn"
