from brochure.print_config import PRINT


def test_target_dpi_is_300():
    assert PRINT.target_dpi == 300


def test_warn_dpi_is_250():
    assert PRINT.warn_dpi == 250


def test_bleed_is_3_mm():
    assert PRINT.bleed_mm == 3


def test_page_is_a4_portrait():
    assert (PRINT.page_width_mm, PRINT.page_height_mm) == (210, 297)


def test_slug_is_10_mm_beyond_the_bleed():
    assert PRINT.slug_beyond_bleed_mm == 10


def test_crop_marks_start_5_mm_from_the_trim():
    assert PRINT.crop_mark_offset_mm == 5


def test_crop_marks_are_5_mm_long():
    assert PRINT.crop_mark_length_mm == 5


def test_crop_marks_are_0_25_pt_lines():
    assert PRINT.crop_mark_weight_pt == 0.25


def test_page_count_must_be_a_multiple_of_4():
    assert PRINT.page_count_multiple == 4
