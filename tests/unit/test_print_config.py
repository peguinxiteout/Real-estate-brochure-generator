from brochure.print_config import PRINT


def test_target_dpi_is_300():
    assert PRINT.target_dpi == 300
