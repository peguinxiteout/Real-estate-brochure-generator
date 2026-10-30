from brochure.print_config import PRINT


def test_target_dpi_is_300():
    assert PRINT.target_dpi == 300


def test_warn_dpi_is_250():
    assert PRINT.warn_dpi == 250
